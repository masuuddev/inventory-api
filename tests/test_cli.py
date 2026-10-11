"""Tests for CLI commands. HTTP calls to the API are mocked."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from inventory import cli

ITEM = {
    "id": 1, "product_name": "Oat Milk", "brands": "Oatly", "price": 3.5,
    "stock": 20, "barcode": "123", "ingredients_text": "Oats, water",
}


def resp(body, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body
    return r


@pytest.fixture
def mock_request():
    with patch("inventory.cli.requests.request") as m:
        yield m


def test_list(mock_request, capsys):
    mock_request.return_value = resp([ITEM])
    assert cli.main(["list"]) == 0
    assert "[1] Oat Milk" in capsys.readouterr().out
    assert mock_request.call_args[0][:2] == ("GET", f"{cli.API_URL}/inventory")


def test_list_empty(mock_request, capsys):
    mock_request.return_value = resp([])
    cli.main(["list", "--name", "zzz"])
    assert "No items found" in capsys.readouterr().out
    assert mock_request.call_args.kwargs["params"] == {"name": "zzz"}


def test_view(mock_request, capsys):
    mock_request.return_value = resp(ITEM)
    assert cli.main(["view", "1"]) == 0
    out = capsys.readouterr().out
    assert "Oats, water" in out and "123" in out


def test_view_not_found(mock_request, capsys):
    mock_request.return_value = resp({"error": "Item not found"}, 404)
    assert cli.main(["view", "9"]) == 1
    assert "Item not found" in capsys.readouterr().err


def test_add_sends_payload(mock_request, capsys):
    mock_request.return_value = resp(ITEM, 201)
    assert cli.main(["add", "Oat Milk", "3.5", "20", "--brands", "Oatly"]) == 0
    assert mock_request.call_args.args[0] == "POST"
    assert mock_request.call_args.kwargs["json"] == {
        "product_name": "Oat Milk", "price": 3.5, "stock": 20, "brands": "Oatly",
    }
    assert "Added:" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [["add", "X", "abc", "1"], ["add", "X", "1", "1.5"], ["add", "X", "-1", "1"]])
def test_add_rejects_invalid_numbers(argv, mock_request):
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2
    mock_request.assert_not_called()


def test_update_price_and_stock(mock_request, capsys):
    mock_request.return_value = resp({**ITEM, "price": 4.0, "stock": 5})
    assert cli.main(["update", "1", "--price", "4", "--stock", "5"]) == 0
    assert mock_request.call_args.args[0] == "PATCH"
    assert mock_request.call_args.kwargs["json"] == {"price": 4.0, "stock": 5}
    assert "Updated:" in capsys.readouterr().out


def test_update_requires_a_change(mock_request, capsys):
    assert cli.main(["update", "1"]) == 1
    assert "Nothing to update" in capsys.readouterr().err
    mock_request.assert_not_called()


def test_delete(mock_request, capsys):
    mock_request.return_value = resp({"message": "Item deleted", "item": ITEM})
    assert cli.main(["delete", "1"]) == 0
    assert mock_request.call_args.args[0] == "DELETE"
    assert "Deleted:" in capsys.readouterr().out


def test_find_by_barcode(mock_request, capsys):
    mock_request.return_value = resp({"barcode": "123", "product_name": "Nutella", "brands": "Ferrero", "ingredients_text": "Sugar"})
    assert cli.main(["find", "--barcode", "123"]) == 0
    assert mock_request.call_args.args[1].endswith("/external/barcode/123")
    assert "Nutella" in capsys.readouterr().out


def test_find_by_name(mock_request, capsys):
    mock_request.return_value = resp([{"barcode": "1", "product_name": "Oat Drink", "brands": "Alpro"}])
    cli.main(["find", "--name", "oat"])
    assert mock_request.call_args.kwargs["params"] == {"name": "oat"}
    assert "Oat Drink" in capsys.readouterr().out


def test_find_requires_barcode_or_name():
    with pytest.raises(SystemExit):
        cli.main(["find"])


def test_import_by_barcode(mock_request, capsys):
    mock_request.return_value = resp(ITEM, 201)
    assert cli.main(["import", "--barcode", "123", "--price", "2", "--stock", "9"]) == 0
    assert mock_request.call_args.kwargs["json"] == {"price": 2.0, "stock": 9, "barcode": "123"}
    assert "Imported:" in capsys.readouterr().out


def test_external_api_failure_reported(mock_request, capsys):
    mock_request.return_value = resp({"error": "OpenFoodFacts request failed"}, 502)
    assert cli.main(["import", "--barcode", "1"]) == 1
    assert "OpenFoodFacts request failed" in capsys.readouterr().err


def test_server_unreachable(mock_request, capsys):
    mock_request.side_effect = requests.ConnectionError("refused")
    assert cli.main(["list"]) == 1
    assert "Is the server running" in capsys.readouterr().err


def test_non_json_response(mock_request, capsys):
    r = resp(None, 500)
    r.json.side_effect = ValueError
    mock_request.return_value = r
    assert cli.main(["list"]) == 1
    assert "non-JSON" in capsys.readouterr().err
