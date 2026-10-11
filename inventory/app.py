"""Flask REST API for the inventory management system."""
from flask import Flask, jsonify, request

from .store import InventoryStore

# Fields a client may set on an item.
ALLOWED_FIELDS = {"barcode", "product_name", "brands", "ingredients_text", "price", "stock"}


def validate_item(data, partial=False):
    """Return (clean_data, error_message). `partial` is True for PATCH."""
    if not isinstance(data, dict):
        return None, "Request body must be a JSON object"
    unknown = set(data) - ALLOWED_FIELDS
    if unknown:
        return None, f"Unknown field(s): {', '.join(sorted(unknown))}"
    if not partial:
        for required in ("product_name", "price", "stock"):
            if required not in data:
                return None, f"Missing required field: {required}"
    if "product_name" in data and (not isinstance(data["product_name"], str) or not data["product_name"].strip()):
        return None, "product_name must be a non-empty string"
    if "price" in data:
        p = data["price"]
        if isinstance(p, bool) or not isinstance(p, (int, float)) or p < 0:
            return None, "price must be a non-negative number"
    if "stock" in data:
        s = data["stock"]
        if isinstance(s, bool) or not isinstance(s, int) or s < 0:
            return None, "stock must be a non-negative integer"
    return data, None


def create_app(store=None):
    app = Flask(__name__)
    app.store = store if store is not None else InventoryStore()

    def error(message, status):
        return jsonify({"error": message}), status

    @app.get("/inventory")
    def list_items():
        return jsonify(app.store.all(name=request.args.get("name")))

    @app.get("/inventory/<int:item_id>")
    def get_item(item_id):
        item = app.store.get(item_id)
        if item is None:
            return error("Item not found", 404)
        return jsonify(item)

    @app.post("/inventory")
    def create_item():
        data, err = validate_item(request.get_json(silent=True))
        if err:
            return error(err, 400)
        return jsonify(app.store.add(data)), 201

    @app.patch("/inventory/<int:item_id>")
    def update_item(item_id):
        data, err = validate_item(request.get_json(silent=True), partial=True)
        if err:
            return error(err, 400)
        item = app.store.update(item_id, data)
        if item is None:
            return error("Item not found", 404)
        return jsonify(item)

    @app.delete("/inventory/<int:item_id>")
    def delete_item(item_id):
        item = app.store.delete(item_id)
        if item is None:
            return error("Item not found", 404)
        return jsonify({"message": "Item deleted", "item": item})

    @app.errorhandler(404)
    def not_found(_):
        return error("Resource not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(_):
        return error("Method not allowed", 405)

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
