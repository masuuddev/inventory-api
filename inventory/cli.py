"""Command-line interface for the inventory API.

Start the server first (`python -m inventory.app`), then e.g.:
    python -m inventory.cli list
    python -m inventory.cli add "Oat Milk" 3.5 20 --brands Oatly
"""
import argparse
import os
import sys

import requests

API_URL = os.environ.get("INVENTORY_API_URL", "http://127.0.0.1:5000")


class CLIError(Exception):
    """A user-facing error (bad input, API error, server unreachable)."""


def api(method, path, **kwargs):
    """Call the inventory API and return decoded JSON, or raise CLIError."""
    try:
        res = requests.request(method, f"{API_URL}{path}", timeout=15, **kwargs)
    except requests.RequestException as exc:
        raise CLIError(f"Cannot reach the API at {API_URL}. Is the server running? ({exc})")
    try:
        body = res.json()
    except ValueError:
        raise CLIError(f"API returned a non-JSON response (HTTP {res.status_code})")
    if res.status_code >= 400:
        raise CLIError(body.get("error", f"HTTP {res.status_code}"))
    return body


def non_negative_float(value):
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a number")
    if number < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return number


def non_negative_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a whole number")
    if number < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return number


def format_item(item):
    return (
        f"[{item['id']}] {item['product_name']}"
        f" | brand: {item.get('brands') or '-'}"
        f" | price: ${item.get('price', 0):.2f}"
        f" | stock: {item.get('stock', 0)}"
    )


def print_item_details(item):
    print(format_item(item))
    print(f"    barcode:     {item.get('barcode') or '-'}")
    print(f"    ingredients: {item.get('ingredients_text') or '-'}")


def cmd_list(args):
    items = api("GET", "/inventory", params={"name": args.name} if args.name else None)
    if not items:
        print("No items found.")
    for item in items:
        print(format_item(item))


def cmd_view(args):
    print_item_details(api("GET", f"/inventory/{args.id}"))


def cmd_add(args):
    payload = {"product_name": args.name, "price": args.price, "stock": args.stock}
    if args.brands:
        payload["brands"] = args.brands
    if args.barcode:
        payload["barcode"] = args.barcode
    item = api("POST", "/inventory", json=payload)
    print("Added:", format_item(item))


def cmd_update(args):
    changes = {}
    if args.price is not None:
        changes["price"] = args.price
    if args.stock is not None:
        changes["stock"] = args.stock
    if not changes:
        raise CLIError("Nothing to update: pass --price and/or --stock")
    item = api("PATCH", f"/inventory/{args.id}", json=changes)
    print("Updated:", format_item(item))


def cmd_delete(args):
    result = api("DELETE", f"/inventory/{args.id}")
    print("Deleted:", format_item(result["item"]))


def cmd_find(args):
    """Look up a product on OpenFoodFacts by barcode or name (does not save it)."""
    if args.barcode:
        results = [api("GET", f"/external/barcode/{args.barcode}")]
    else:
        results = api("GET", "/external/search", params={"name": args.name})
    if not results:
        print("No products found on OpenFoodFacts.")
    for p in results:
        print(f"{p['product_name']} | brand: {p.get('brands') or '-'} | barcode: {p.get('barcode') or '-'}")
        if p.get("ingredients_text"):
            print(f"    ingredients: {p['ingredients_text']}")


def cmd_import(args):
    """Fetch a product from OpenFoodFacts and add it to the inventory."""
    payload = {"price": args.price, "stock": args.stock}
    if args.barcode:
        payload["barcode"] = args.barcode
    else:
        payload["name"] = args.name
    item = api("POST", "/inventory/import", json=payload)
    print("Imported:", format_item(item))


def build_parser():
    parser = argparse.ArgumentParser(prog="inventory", description="Inventory management CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="List all items")
    p.add_argument("--name", help="Filter by name substring")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("view", help="Show one item's details")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_view)

    p = sub.add_parser("add", help="Add an item manually")
    p.add_argument("name")
    p.add_argument("price", type=non_negative_float)
    p.add_argument("stock", type=non_negative_int)
    p.add_argument("--brands")
    p.add_argument("--barcode")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("update", help="Update an item's price and/or stock")
    p.add_argument("id", type=int)
    p.add_argument("--price", type=non_negative_float)
    p.add_argument("--stock", type=non_negative_int)
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("delete", help="Delete an item")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_delete)

    for name, func, help_text in (
        ("find", cmd_find, "Find a product on OpenFoodFacts (not saved)"),
        ("import", cmd_import, "Fetch a product from OpenFoodFacts and add it to inventory"),
    ):
        p = sub.add_parser(name, help=help_text)
        group = p.add_mutually_exclusive_group(required=True)
        group.add_argument("--barcode")
        group.add_argument("--name")
        if name == "import":
            p.add_argument("--price", type=non_negative_float, default=0)
            p.add_argument("--stock", type=non_negative_int, default=0)
        p.set_defaults(func=func)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except CLIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
