"""Flask REST API for the inventory management system.

Storage is a plain in-memory list that simulates a database. Each item looks like
an OpenFoodFacts response, plus our own ``id``, ``price`` and ``stock`` fields:

    {
      "id": 1,
      "barcode": "5449000000996",
      "price": 1.50,
      "stock": 40,
      "status": 1,
      "product": {"product_name": ..., "brands": ..., "ingredients_text": ...}
    }
"""
import copy

from flask import Flask, jsonify, request

import off_client

SEED_ITEMS = [
    {
        "id": 1,
        "barcode": "5449000000996",
        "price": 1.50,
        "stock": 40,
        "status": 1,
        "product": {
            "product_name": "Coca-Cola",
            "brands": "Coca-Cola",
            "ingredients_text": "Carbonated water, sugar, colour (caramel E150d), acid (phosphoric acid), natural flavourings",
            "categories": "Beverages, Sodas",
            "quantity": "330 ml",
        },
    },
    {
        "id": 2,
        "barcode": "3017620422003",
        "price": 4.25,
        "stock": 12,
        "status": 1,
        "product": {
            "product_name": "Nutella",
            "brands": "Ferrero",
            "ingredients_text": "Sugar, palm oil, hazelnuts, skimmed milk powder, fat-reduced cocoa, lecithin, vanillin",
            "categories": "Spreads, Sweet spreads",
            "quantity": "400 g",
        },
    },
    {
        "id": 3,
        "barcode": "0000000000003",
        "price": 3.99,
        "stock": 25,
        "status": 1,
        "product": {
            "product_name": "Organic Almond Milk",
            "brands": "Silk",
            "ingredients_text": "Filtered water, almonds, cane sugar, sea salt, sunflower lecithin",
            "categories": "Beverages, Plant-based milks",
            "quantity": "1 l",
        },
    },
]

PRODUCT_FIELDS = ("product_name", "brands", "ingredients_text", "categories", "quantity")


def _parse_price(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("price must be a number")
    if value < 0:
        raise ValueError("price must not be negative")
    return round(float(value), 2)


def _parse_stock(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("stock must be an integer")
    if value < 0:
        raise ValueError("stock must not be negative")
    return value


def _error(message, status):
    return jsonify({"error": message}), status


def create_app(seed=True):
    app = Flask(__name__)
    store = {
        "items": copy.deepcopy(SEED_ITEMS) if seed else [],
        "next_id": (max(i["id"] for i in SEED_ITEMS) + 1) if seed else 1,
    }
    app.config["STORE"] = store

    def find_item(item_id):
        return next((i for i in store["items"] if i["id"] == item_id), None)

    def json_body():
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else None

    # ---- CRUD -----------------------------------------------------------

    @app.get("/inventory")
    def list_items():
        return jsonify(store["items"]), 200

    @app.get("/inventory/<int:item_id>")
    def get_item(item_id):
        item = find_item(item_id)
        if item is None:
            return _error(f"Item {item_id} not found", 404)
        return jsonify(item), 200

    @app.post("/inventory")
    def add_item():
        data = json_body()
        if data is None:
            return _error("Request body must be a JSON object", 400)

        try:
            price = _parse_price(data.get("price", 0))
            stock = _parse_stock(data.get("stock", 0))
        except ValueError as exc:
            return _error(str(exc), 400)

        product = {f: data[f] for f in PRODUCT_FIELDS if data.get(f)}
        barcode = str(data["barcode"]).strip() if data.get("barcode") else ""

        # Enrich with OpenFoodFacts data when a barcode is supplied.
        if barcode:
            try:
                found = off_client.fetch_by_barcode(barcode)
            except ValueError as exc:
                return _error(str(exc), 400)
            except off_client.OFFError as exc:
                found = None
                if not product.get("product_name"):
                    return _error(str(exc), 502)
            else:
                if found is None and not product.get("product_name"):
                    return _error(f"Barcode {barcode} not found on OpenFoodFacts", 404)
            if found:
                # Values the user typed win; the API fills the gaps.
                product = {**{k: v for k, v in found["product"].items() if v}, **product}

        if not product.get("product_name"):
            return _error("product_name is required (or supply a valid barcode)", 400)

        item = {
            "id": store["next_id"],
            "barcode": barcode,
            "price": price,
            "stock": stock,
            "status": 1,
            "product": product,
        }
        store["next_id"] += 1
        store["items"].append(item)
        return jsonify(item), 201

    @app.patch("/inventory/<int:item_id>")
    def update_item(item_id):
        item = find_item(item_id)
        if item is None:
            return _error(f"Item {item_id} not found", 404)

        data = json_body()
        if not data:
            return _error("Request body must be a non-empty JSON object", 400)

        updates = {}
        try:
            if "price" in data:
                updates["price"] = _parse_price(data["price"])
            if "stock" in data:
                updates["stock"] = _parse_stock(data["stock"])
        except ValueError as exc:
            return _error(str(exc), 400)

        product_updates = {f: data[f] for f in PRODUCT_FIELDS if f in data}
        if "product_name" in product_updates and not product_updates["product_name"]:
            return _error("product_name must not be empty", 400)
        if "barcode" in data:
            updates["barcode"] = str(data["barcode"]).strip()

        if not updates and not product_updates:
            return _error("No updatable fields supplied", 400)

        item.update(updates)
        item["product"].update(product_updates)
        return jsonify(item), 200

    @app.delete("/inventory/<int:item_id>")
    def delete_item(item_id):
        item = find_item(item_id)
        if item is None:
            return _error(f"Item {item_id} not found", 404)
        store["items"].remove(item)
        return jsonify({"message": f"Item {item_id} deleted"}), 200

    # ---- External API lookup -------------------------------------------

    @app.get("/lookup")
    def lookup():
        barcode = request.args.get("barcode")
        name = request.args.get("name")
        try:
            if barcode:
                found = off_client.fetch_by_barcode(barcode)
                if found is None:
                    return _error(f"Barcode {barcode} not found on OpenFoodFacts", 404)
                return jsonify({"results": [found]}), 200
            if name:
                return jsonify({"results": off_client.search_by_name(name)}), 200
        except ValueError as exc:
            return _error(str(exc), 400)
        except off_client.OFFError as exc:
            return _error(str(exc), 502)
        return _error("Provide a 'barcode' or 'name' query parameter", 400)

    @app.errorhandler(404)
    def not_found(_):
        return _error("Resource not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(_):
        return _error("Method not allowed", 405)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
