"""Tests for the OpenFoodFacts client and the routes that use it (all HTTP mocked)."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from inventory import off_client
from inventory.app import create_app
from inventory.store import InventoryStore

BARCODE_RESPONSE = {
    "status": 1,
    "product": {
        "code": "3017620422003",
        "product_name": "Nutella",
        "brands": "Ferrero",
        "ingredients_text": "Sugar, palm oil, hazelnuts",
    },
}
SEARCH_RESPONSE = {
    "products": [
        {"code": "1", "product_name": "Oat Milk", "brands": "Oatly"},
        {"code": "2", "product_name": ""},  # unnamed products are dropped
        {"code": "3", "product_name": "Oat Drink", "brands": "Alpro"},
    ]
}


def fake_response(payload, status=200):
    res = MagicMock()
    res.json.return_value = payload
    if status >= 400:
        res.raise_for_status.side_effect = requests.HTTPError(f"{status}")
    return res


@pytest.fixture
def client():
    return create_app(InventoryStore()).test_client()


# ---- off_client ----

@patch("inventory.off_client.requests.get")
def test_get_product_by_barcode(mock_get):
    mock_get.return_value = fake_response(BARCODE_RESPONSE)
    product = off_client.get_product_by_barcode("3017620422003")
    assert product["product_name"] == "Nutella"
    assert product["brands"] == "Ferrero"
    assert product["barcode"] == "3017620422003"
    assert "3017620422003" in mock_get.call_args[0][0]


@patch("inventory.off_client.requests.get")
def test_get_product_unknown_barcode(mock_get):
    mock_get.return_value = fake_response({"status": 0, "status_verbose": "product not found"})
    assert off_client.get_product_by_barcode("0") is None


@patch("inventory.off_client.requests.get")
def test_search_products_filters_unnamed_and_limits(mock_get):
    mock_get.return_value = fake_response(SEARCH_RESPONSE)
    results = off_client.search_products("oat", limit=5)
    assert [r["product_name"] for r in results] == ["Oat Milk", "Oat Drink"]
    assert mock_get.call_args.kwargs["params"]["search_terms"] == "oat"


@patch("inventory.off_client.requests.get", side_effect=requests.ConnectionError("down"))
def test_network_failure_raises_external_error(_):
    with pytest.raises(off_client.ExternalAPIError):
        off_client.get_product_by_barcode("123")


@patch("inventory.off_client.requests.get")
def test_http_error_raises_external_error(mock_get):
    mock_get.return_value = fake_response({}, status=500)
    with pytest.raises(off_client.ExternalAPIError):
        off_client.search_products("x")


@patch("inventory.off_client.requests.get")
def test_invalid_json_raises_external_error(mock_get):
    res = fake_response({})
    res.json.side_effect = ValueError("bad json")
    mock_get.return_value = res
    with pytest.raises(off_client.ExternalAPIError):
        off_client.get_product_by_barcode("123")


# ---- routes ----

@patch("inventory.app.off_client.get_product_by_barcode")
def test_external_barcode_route(mock_fn, client):
    mock_fn.return_value = {"barcode": "1", "product_name": "Nutella", "brands": "", "ingredients_text": ""}
    res = client.get("/external/barcode/1")
    assert res.status_code == 200 and res.get_json()["product_name"] == "Nutella"


@patch("inventory.app.off_client.get_product_by_barcode", return_value=None)
def test_external_barcode_not_found(_, client):
    assert client.get("/external/barcode/0").status_code == 404


@patch("inventory.app.off_client.get_product_by_barcode", side_effect=off_client.ExternalAPIError("boom"))
def test_external_barcode_api_failure_is_502(_, client):
    assert client.get("/external/barcode/1").status_code == 502


@patch("inventory.app.off_client.search_products", return_value=[{"product_name": "Oat Milk"}])
def test_external_search_route(mock_fn, client):
    res = client.get("/external/search?name=oat")
    assert res.status_code == 200 and res.get_json()[0]["product_name"] == "Oat Milk"


def test_external_search_requires_name(client):
    assert client.get("/external/search").status_code == 400


@patch("inventory.app.off_client.get_product_by_barcode")
def test_import_by_barcode_adds_to_inventory(mock_fn, client):
    mock_fn.return_value = {
        "barcode": "3017620422003", "product_name": "Nutella",
        "brands": "Ferrero", "ingredients_text": "Sugar",
    }
    res = client.post("/inventory/import", json={"barcode": "3017620422003", "price": 6.5, "stock": 12})
    assert res.status_code == 201
    body = res.get_json()
    assert body["id"] == 4 and body["price"] == 6.5 and body["stock"] == 12
    assert client.get("/inventory/4").get_json()["brands"] == "Ferrero"


@patch("inventory.app.off_client.search_products")
def test_import_by_name_uses_first_result(mock_fn, client):
    mock_fn.return_value = [{"barcode": "1", "product_name": "Oat Milk", "brands": "Oatly", "ingredients_text": ""}]
    res = client.post("/inventory/import", json={"name": "oat"})
    assert res.status_code == 201
    assert res.get_json()["product_name"] == "Oat Milk"
    assert res.get_json()["price"] == 0  # default until the employee sets one


@patch("inventory.app.off_client.get_product_by_barcode", return_value=None)
def test_import_not_found(_, client):
    assert client.post("/inventory/import", json={"barcode": "0"}).status_code == 404


@patch("inventory.app.off_client.get_product_by_barcode", side_effect=off_client.ExternalAPIError("down"))
def test_import_api_failure_is_502(_, client):
    assert client.post("/inventory/import", json={"barcode": "1"}).status_code == 502


def test_import_validation(client):
    assert client.post("/inventory/import", json={}).status_code == 400
    assert client.post("/inventory/import", json={"barcode": "1", "price": -5}).status_code == 400
