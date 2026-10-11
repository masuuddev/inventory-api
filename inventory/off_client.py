"""Small client for the OpenFoodFacts API (https://world.openfoodfacts.org)."""
import requests

BASE_URL = "https://world.openfoodfacts.org"
# OpenFoodFacts asks API users to identify their app with a User-Agent.
HEADERS = {"User-Agent": "InventoryManagementLab/1.0 (student project)"}
TIMEOUT = 10


class ExternalAPIError(Exception):
    """Raised when OpenFoodFacts cannot be reached or returns bad data."""


def _normalize(product):
    """Reduce an OpenFoodFacts product to the fields we store."""
    return {
        "barcode": str(product.get("code") or product.get("_id") or ""),
        "product_name": (product.get("product_name") or "").strip(),
        "brands": product.get("brands") or "",
        "ingredients_text": product.get("ingredients_text") or "",
    }


def _get_json(url, params=None):
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        res.raise_for_status()
        return res.json()
    except requests.RequestException as exc:
        raise ExternalAPIError(f"OpenFoodFacts request failed: {exc}") from exc
    except ValueError as exc:  # invalid JSON
        raise ExternalAPIError("OpenFoodFacts returned invalid JSON") from exc


def get_product_by_barcode(barcode):
    """Return a normalized product dict, or None if the barcode is unknown."""
    data = _get_json(f"{BASE_URL}/api/v0/product/{barcode}.json")
    if data.get("status") != 1 or "product" not in data:
        return None
    product = data["product"]
    product.setdefault("code", barcode)
    return _normalize(product)


def search_products(name, limit=5):
    """Search by product name. Returns a (possibly empty) list of normalized products."""
    data = _get_json(
        f"{BASE_URL}/cgi/search.pl",
        params={
            "search_terms": name,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": limit,
        },
    )
    results = [_normalize(p) for p in data.get("products", [])]
    return [r for r in results if r["product_name"]][:limit]
