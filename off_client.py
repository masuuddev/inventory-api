"""Thin client for the OpenFoodFacts API.

Only the fields the inventory system cares about are returned, in a shape that
mirrors the OpenFoodFacts ``product`` object.
"""
import requests

BASE_URL = "https://world.openfoodfacts.org"
TIMEOUT = 10
HEADERS = {"User-Agent": "InventoryManager/1.0 (student lab project)"}
FIELDS = "code,product_name,brands,ingredients_text,categories,quantity"


class OFFError(Exception):
    """Raised when the OpenFoodFacts API cannot be reached or misbehaves."""


def _get(url, params=None):
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise OFFError(f"OpenFoodFacts request failed: {exc}") from exc
    except ValueError as exc:
        raise OFFError("OpenFoodFacts returned invalid JSON") from exc


def _simplify(product):
    """Reduce a raw OpenFoodFacts product to the fields we store."""
    return {
        "product_name": product.get("product_name") or "",
        "brands": product.get("brands") or "",
        "ingredients_text": product.get("ingredients_text") or "",
        "categories": product.get("categories") or "",
        "quantity": product.get("quantity") or "",
    }


def fetch_by_barcode(barcode):
    """Return ``{"barcode": ..., "product": {...}}`` or ``None`` if not found.

    Raises ``ValueError`` for a malformed barcode and ``OFFError`` for API failures.
    """
    barcode = str(barcode).strip()
    if not barcode.isdigit() or not 8 <= len(barcode) <= 14:
        raise ValueError("barcode must be 8-14 digits")

    data = _get(f"{BASE_URL}/api/v2/product/{barcode}.json", params={"fields": FIELDS})
    if data.get("status") != 1 or not data.get("product"):
        return None
    return {"barcode": barcode, "product": _simplify(data["product"])}


def search_by_name(name, limit=5):
    """Return a list of ``{"barcode": ..., "product": {...}}`` matches (may be empty)."""
    name = (name or "").strip()
    if not name:
        raise ValueError("name must not be empty")

    data = _get(
        f"{BASE_URL}/cgi/search.pl",
        params={
            "search_terms": name,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": limit,
            "fields": FIELDS,
        },
    )
    results = []
    for raw in data.get("products", [])[:limit]:
        results.append({"barcode": raw.get("code", ""), "product": _simplify(raw)})
    return results
