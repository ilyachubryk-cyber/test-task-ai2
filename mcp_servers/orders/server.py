"""JewelryOps Orders & Inventory MCP server."""

import json
from pathlib import Path

try:
    from fastmcp import FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

_DATA_DIR = Path(__file__).resolve().parent / "data"
_ORDERS_PATH = _DATA_DIR / "orders.json"
_INVENTORY_PATH = _DATA_DIR / "inventory.json"


def _load_orders() -> list[dict]:
    with open(_ORDERS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_inventory() -> list[dict]:
    with open(_INVENTORY_PATH, encoding="utf-8") as f:
        return json.load(f)


mcp = FastMCP("JewelryOps Orders & Inventory", json_response=True)


@mcp.tool()
def get_order(order_id: str) -> str:
    """Get a single order by ID (e.g. ORD-2038, ORD-2041)."""
    orders = _load_orders()
    for o in orders:
        if o["id"] == order_id:
            return json.dumps(o, indent=2)
    return json.dumps({"error": f"Order not found: {order_id}"})


@mcp.tool()
def list_orders(status: str = "", limit: int = 20) -> str:
    """List orders, optionally filtered by status (pending, processing, shipped, delivered, cancelled).

    Note: pass an empty string for `status` to get all orders. This avoids
    optional/union types in the schema so that MCP → function-calling
    adapters (like OpenAI tools) see a simple string parameter.
    """
    orders = _load_orders()
    if status:
        orders = [o for o in orders if o["status"] == status.lower()]
    return json.dumps(orders[:limit], indent=2)


@mcp.tool()
def get_inventory_item(sku: str) -> str:
    """Get inventory for a single SKU (e.g. RING-101, BRAC-301)."""
    inv = _load_inventory()
    for item in inv:
        if item["sku"] == sku:
            return json.dumps(item, indent=2)
    return json.dumps({"error": f"SKU not found: {sku}"})


@mcp.tool()
def list_inventory(limit: int = 50) -> str:
    """List all inventory items with quantity and reserved counts."""
    inv = _load_inventory()
    return json.dumps(inv[:limit], indent=2)


@mcp.tool()
def check_stock(sku: str, quantity: int = 1) -> str:
    """Check if a SKU has at least the given quantity available (quantity - reserved)."""
    inv = _load_inventory()
    for item in inv:
        if item["sku"] == sku:
            available = item["quantity"] - item.get("reserved", 0)
            ok = available >= quantity
            return json.dumps(
                {
                    "sku": sku,
                    "available": available,
                    "requested": quantity,
                    "in_stock": ok,
                },
                indent=2,
            )
    return json.dumps({"error": f"SKU not found: {sku}"})


if __name__ == "__main__":
    mcp.run(transport="stdio")
