"""In-memory inventory storage (a simple list that simulates a database)."""
import copy

# Mock database. Fields mirror what OpenFoodFacts returns (product_name,
# brands, ingredients_text, barcode) plus our own business fields (price, stock).
SEED_ITEMS = [
    {
        "id": 1,
        "barcode": "0000000000001",
        "product_name": "Organic Almond Milk",
        "brands": "Silk",
        "ingredients_text": "Filtered water, almonds, cane sugar, sea salt",
        "price": 3.99,
        "stock": 40,
    },
    {
        "id": 2,
        "barcode": "0000000000002",
        "product_name": "Whole Grain Oat Cereal",
        "brands": "Nature's Path",
        "ingredients_text": "Whole grain oats, honey, sunflower oil",
        "price": 5.49,
        "stock": 25,
    },
    {
        "id": 3,
        "barcode": "0000000000003",
        "product_name": "Dark Chocolate 70%",
        "brands": "Lindt",
        "ingredients_text": "Cocoa mass, sugar, cocoa butter, vanilla",
        "price": 2.79,
        "stock": 100,
    },
]


class InventoryStore:
    """CRUD operations over a list of item dicts, each with a unique int id."""

    def __init__(self, items=None):
        self.items = copy.deepcopy(SEED_ITEMS if items is None else items)
        self._next_id = max((i["id"] for i in self.items), default=0) + 1

    def all(self, name=None):
        """Return all items, optionally filtered by a name substring."""
        if name:
            needle = name.lower()
            return [i for i in self.items if needle in i["product_name"].lower()]
        return list(self.items)

    def get(self, item_id):
        return next((i for i in self.items if i["id"] == item_id), None)

    def add(self, data):
        item = {"id": self._next_id, **data}
        self._next_id += 1
        self.items.append(item)
        return item

    def update(self, item_id, changes):
        item = self.get(item_id)
        if item is None:
            return None
        item.update(changes)
        return item

    def delete(self, item_id):
        item = self.get(item_id)
        if item is None:
            return None
        self.items.remove(item)
        return item
