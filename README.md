# Inventory Management System (Flask + OpenFoodFacts)

An administrator portal backend for a small retail company: a Flask REST API for
managing inventory, enrichment from the [OpenFoodFacts API](https://openfoodfacts.github.io/openfoodfacts-server/api/),
a CLI to drive it, and a pytest suite.

Storage is an in-memory Python list (seeded with 3 sample products), so data resets
whenever the server restarts.

## Project structure

```
inventory/
  app.py          Flask app factory + routes
  store.py        In-memory storage (mock database array + CRUD helpers)
  off_client.py   OpenFoodFacts client (barcode lookup, name search)
  cli.py          Command-line interface (talks to the API over HTTP)
tests/
  test_api.py       CRUD endpoint tests
  test_external.py  OpenFoodFacts client + helper route tests (HTTP mocked)
  test_cli.py       CLI tests (HTTP mocked)
```

## Installation

```bash
git clone <your-repo-url> && cd inventory-api
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run the API

```bash
python -m inventory.app          # http://127.0.0.1:5000 (debug mode on)
```

## Item model

```json
{
  "id": 1,
  "barcode": "0000000000001",
  "product_name": "Organic Almond Milk",
  "brands": "Silk",
  "ingredients_text": "Filtered water, almonds, cane sugar, sea salt",
  "price": 3.99,
  "stock": 40
}
```

`product_name`, `price` (>= 0) and `stock` (integer >= 0) are required on create.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/inventory` | List all items (optional `?name=` substring filter) |
| GET | `/inventory/<id>` | Get one item |
| POST | `/inventory` | Create an item (JSON body) -> 201 |
| PATCH | `/inventory/<id>` | Partially update an item |
| DELETE | `/inventory/<id>` | Delete an item |
| GET | `/external/barcode/<barcode>` | Look up a product on OpenFoodFacts (not saved) |
| GET | `/external/search?name=<text>` | Search OpenFoodFacts by name (not saved) |
| POST | `/inventory/import` | Fetch from OpenFoodFacts and add to inventory. Body: `{"barcode": "..."}` or `{"name": "..."}`, plus optional `price`, `stock` |

Errors are JSON: `{"error": "..."}` with status 400 (invalid input), 404 (not found)
or 502 (OpenFoodFacts unreachable).

```bash
curl localhost:5000/inventory
curl -X POST localhost:5000/inventory -H "Content-Type: application/json" \
     -d '{"product_name": "Rice", "price": 2.5, "stock": 30}'
curl -X PATCH localhost:5000/inventory/1 -H "Content-Type: application/json" -d '{"price": 4.25}'
curl -X DELETE localhost:5000/inventory/1
curl -X POST localhost:5000/inventory/import -H "Content-Type: application/json" \
     -d '{"barcode": "3017620422003", "price": 6.5, "stock": 12}'
```

## CLI

With the server running in one terminal, use the CLI from another
(set `INVENTORY_API_URL` if the server is not at `http://127.0.0.1:5000`):

```bash
python -m inventory.cli list [--name almond]          # view all / filter
python -m inventory.cli view 1                        # full details of one item
python -m inventory.cli add "Oat Milk" 3.50 20 --brands Oatly --barcode 123
python -m inventory.cli update 1 --price 4.25 --stock 15
python -m inventory.cli delete 1
python -m inventory.cli find --barcode 3017620422003  # look up on OpenFoodFacts
python -m inventory.cli find --name "oat milk"
python -m inventory.cli import --barcode 3017620422003 --price 6.5 --stock 12
python -m inventory.cli import --name "oat milk" --price 3 --stock 8
```

Invalid input (non-numeric price, negative stock, unknown ID, server down, API failure)
prints an `Error: ...` message and exits with status 1.

## Tests

```bash
python -m pytest -v
```

All external HTTP calls are mocked with `unittest.mock`, so tests run offline.

## Debugging

The server runs in Flask debug mode by default. Postman (or curl) can be pointed at
the endpoints above for manual validation.

## Git workflow

Each feature was developed on its own branch (`feature/crud-api`,
`feature/openfoodfacts`, `feature/cli`, `docs/readme`) and merged into `main`
with `--no-ff` merge commits.

Author: Masuud Adan
