"""Tests for the CRUD endpoints."""
import pytest

from inventory.app import create_app
from inventory.store import InventoryStore


@pytest.fixture
def client():
    app = create_app(InventoryStore())  # fresh seed data per test
    return app.test_client()


def test_list_items(client):
    res = client.get("/inventory")
    assert res.status_code == 200
    assert len(res.get_json()) == 3


def test_list_items_filter_by_name(client):
    res = client.get("/inventory?name=almond")
    assert [i["product_name"] for i in res.get_json()] == ["Organic Almond Milk"]


def test_get_item(client):
    res = client.get("/inventory/1")
    assert res.status_code == 200
    assert res.get_json()["brands"] == "Silk"


def test_get_item_not_found(client):
    res = client.get("/inventory/999")
    assert res.status_code == 404
    assert "error" in res.get_json()


def test_create_item(client):
    payload = {"product_name": "Peanut Butter", "price": 4.5, "stock": 10, "brands": "Skippy"}
    res = client.post("/inventory", json=payload)
    assert res.status_code == 201
    body = res.get_json()
    assert body["id"] == 4
    assert client.get("/inventory/4").get_json()["product_name"] == "Peanut Butter"


@pytest.mark.parametrize(
    "payload",
    [
        {"price": 1, "stock": 1},  # missing name
        {"product_name": "X", "stock": 1},  # missing price
        {"product_name": "X", "price": -1, "stock": 1},  # negative price
        {"product_name": "X", "price": 1, "stock": 1.5},  # non-int stock
        {"product_name": "X", "price": 1, "stock": 1, "color": "red"},  # unknown field
        {"product_name": "  ", "price": 1, "stock": 1},  # blank name
    ],
)
def test_create_item_invalid(client, payload):
    assert client.post("/inventory", json=payload).status_code == 400


def test_create_item_non_json_body(client):
    assert client.post("/inventory", data="nope").status_code == 400


def test_patch_item(client):
    res = client.patch("/inventory/1", json={"price": 4.25, "stock": 7})
    assert res.status_code == 200
    body = res.get_json()
    assert body["price"] == 4.25 and body["stock"] == 7
    assert body["product_name"] == "Organic Almond Milk"  # untouched


def test_patch_item_not_found(client):
    assert client.patch("/inventory/999", json={"price": 1}).status_code == 404


def test_patch_item_invalid(client):
    assert client.patch("/inventory/1", json={"price": "free"}).status_code == 400


def test_delete_item(client):
    assert client.delete("/inventory/2").status_code == 200
    assert client.get("/inventory/2").status_code == 404
    assert len(client.get("/inventory").get_json()) == 2


def test_delete_item_not_found(client):
    assert client.delete("/inventory/999").status_code == 404


def test_ids_not_reused_after_delete(client):
    client.delete("/inventory/3")
    res = client.post("/inventory", json={"product_name": "New", "price": 1, "stock": 1})
    assert res.get_json()["id"] == 4


def test_unknown_route_returns_json_404(client):
    res = client.get("/nope")
    assert res.status_code == 404 and "error" in res.get_json()
