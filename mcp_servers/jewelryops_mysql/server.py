import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

try:
    from fastmcp import FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP


DB_PATH = Path(__file__).resolve().parent / "jewelryops.db"


def _get_conn() -> sqlite3.Connection:
    """Create a new SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_schema_and_data() -> None:
    """Create tables if needed and insert mock data when empty."""
    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              email TEXT NOT NULL,
              phone TEXT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
              id TEXT PRIMARY KEY,
              customer_id TEXT NOT NULL,
              sku TEXT NOT NULL,
              status TEXT NOT NULL,
              placed_at TEXT NOT NULL,
              expected_delivery TEXT NULL,
              total_amount REAL NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
              sku TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              quantity INTEGER NOT NULL,
              reserved INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              entity_type TEXT NOT NULL,
              entity_id TEXT NOT NULL,
              author TEXT NOT NULL,
              body TEXT NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )

        cur.execute("SELECT COUNT(*) AS c FROM customers")
        row = cur.fetchone()
        count = row[0] if row else 0
        if count == 0:
            _insert_mock_data(cur)
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _insert_mock_data(cur) -> None:
    """Insert a realistic set of mock customers, orders, inventory, and notes."""
    customers = [
        ("cust_001", "Lisa Park", "lisa.park@example.com", "+1-555-0101"),
        ("cust_002", "Daniel Kim", "daniel.kim@example.com", "+1-555-0102"),
        ("cust_003", "Amelia Stone", "amelia.stone@example.com", "+1-555-0103"),
        ("cust_004", "Marcus Rivera", "marcus.rivera@example.com", "+1-555-0104"),
        ("cust_005", "Sarah Chen", "sarah.chen@example.com", "+1-555-0105"),
    ]
    cur.executemany(
        "INSERT INTO customers (id, name, email, phone) VALUES (?, ?, ?, ?)",
        customers,
    )

    inventory = [
        ("RING-101", "18K Rose Gold Engagement Ring", 8, 3),
        ("RING-102", "Platinum Solitaire Diamond Ring", 2, 2),
        ("BRAC-301", "Platinum Tennis Bracelet", 4, 2),
        ("BRAC-302", "18K White Gold Diamond Bracelet", 0, 0),
        ("NECK-210", "White Gold Diamond Necklace", 2, 1),
        ("NECK-211", "Rose Gold Pearl Pendant", 6, 0),
        ("EARR-401", "Diamond Stud Earrings 2ct", 5, 1),
    ]
    cur.executemany(
        "INSERT INTO inventory (sku, name, quantity, reserved) VALUES (?, ?, ?, ?)",
        inventory,
    )

    now = datetime(2025, 2, 9, 12, 0, 0, tzinfo=timezone.utc)
    orders = [
        (
            "ORD-2038",
            "cust_001",
            "RING-101",
            "shipped",
            now.replace(day=1, hour=10),
            now.replace(day=5),
            2499.00,
        ),
        (
            "ORD-2041",
            "cust_002",
            "BRAC-301",
            "delivered",
            now.replace(day=1, hour=8),
            now.replace(day=4),
            3299.00,
        ),
        (
            "ORD-2050",
            "cust_003",
            "NECK-210",
            "processing",
            now.replace(day=7, hour=14),
            now.replace(day=12),
            4599.00,
        ),
        (
            "ORD-2035",
            "cust_004",
            "BRAC-302",
            "returned",
            now.replace(day=25, hour=9),
            now.replace(day=30),
            5299.00,
        ),
        (
            "ORD-2055",
            "cust_005",
            "RING-102",
            "processing",
            now.replace(day=8, hour=11),
            now.replace(day=15),
            8999.00,
        ),
        (
            "ORD-2052",
            "cust_001",
            "EARR-401",
            "processing",
            now.replace(day=6, hour=15),
            now.replace(day=11),
            1899.00,
        ),
    ]
    cur.executemany(
        """
        INSERT INTO orders
          (id, customer_id, sku, status, placed_at, expected_delivery, total_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        orders,
    )

    created = now.isoformat(sep=" ", timespec="seconds")
    notes = [
        (
            "order",
            "ORD-2038",
            "Support",
            "Customer (Lisa Park) reported order is 4 days late. Carrier tracking shows package delayed at distribution center.",
            created,
        ),
        (
            "customer",
            "cust_001",
            "Support",
            "High-value customer, repeat buyer. Prefers concise email communication. Previous issue: 2025-01-15 late shipment resolved with $200 credit.",
            created,
        ),
        (
            "order",
            "ORD-2035",
            "Support",
            "Customer returned bracelet due to sizing issue. Return received 2025-02-08. Refund authorization pending.",
            created,
        ),
        (
            "customer",
            "cust_004",
            "Support",
            "First-time customer, high-value purchase ($5,299). Return within 14 days for full refund per policy. No prior complaints.",
            created,
        ),
        (
            "inventory",
            "BRAC-302",
            "Ops",
            "Out of stock. 2 units ordered from supplier on 2025-02-05, ETA 2025-02-20. 1 unit reserved for return processing.",
            created,
        ),
        (
            "inventory",
            "RING-102",
            "Ops",
            "Low stock (2 units). Both units reserved: 1 for ORD-2055, 1 hold for quality check. Next shipment ETA 2025-02-28.",
            created,
        ),
        (
            "order",
            "ORD-2052",
            "Support",
            "Earrings in high demand. Currently low stock (5 total, 1 reserved). Customer notified of 3-5 day processing delay.",
            created,
        ),
    ]
    cur.executemany(
        """
        INSERT INTO notes (entity_type, entity_id, author, body, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        notes,
    )


_init_schema_and_data()

mcp = FastMCP("JewelryOps SQLite", json_response=True)




@mcp.tool()
def get_customer(customer_id: str) -> str:
    """Get a single customer by ID (e.g. cust_001)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        row = cur.fetchone()
        if not row:
            return json.dumps({"error": f"Customer not found: {customer_id}"}, indent=2)
        return json.dumps(dict(row), indent=2, default=str)
    finally:
        conn.close()


@mcp.tool()
def list_customers(limit: int = 20) -> str:
    """List customers, limited by count."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM customers ORDER BY id LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        return json.dumps(rows, indent=2, default=str)
    finally:
        conn.close()


@mcp.tool()
def search_customers(query: str) -> str:
    """Search customers by name or email (case-insensitive partial match)."""
    like = f"%{query.lower()}%"
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM customers
            WHERE LOWER(name) LIKE ? OR LOWER(email) LIKE ?
            ORDER BY id
            """,
            (like, like),
        )
        rows = [dict(r) for r in cur.fetchall()]
        return json.dumps(rows, indent=2, default=str)
    finally:
        conn.close()




@mcp.tool()
def get_order(order_id: str) -> str:
    """Get a single order by ID (e.g. ORD-2038)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cur.fetchone()
        if not row:
            return json.dumps({"error": f"Order not found: {order_id}"}, indent=2)
        return json.dumps(dict(row), indent=2, default=str)
    finally:
        conn.close()


@mcp.tool()
def list_orders(status: str = "", limit: int = 20) -> str:
    """List orders, optionally filtered by status (pending, processing, shipped, delivered, cancelled)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        if status:
            cur.execute(
                "SELECT * FROM orders WHERE status = ? ORDER BY placed_at DESC LIMIT ?",
                (status.lower(), limit),
            )
        else:
            cur.execute(
                "SELECT * FROM orders ORDER BY placed_at DESC LIMIT ?", (limit,)
            )
        rows = [dict(r) for r in cur.fetchall()]
        return json.dumps(rows, indent=2, default=str)
    finally:
        conn.close()


@mcp.tool()
def get_inventory_item(sku: str) -> str:
    """Get inventory for a single SKU (e.g. RING-101, BRAC-301)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventory WHERE sku = ?", (sku,))
        row = cur.fetchone()
        if not row:
            return json.dumps({"error": f"SKU not found: {sku}"}, indent=2)
        return json.dumps(dict(row), indent=2, default=str)
    finally:
        conn.close()


@mcp.tool()
def list_inventory(limit: int = 50) -> str:
    """List all inventory items with quantity and reserved counts."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventory ORDER BY sku LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        return json.dumps(rows, indent=2, default=str)
    finally:
        conn.close()


@mcp.tool()
def check_stock(sku: str, quantity: int = 1) -> str:
    """Check if a SKU has at least the given quantity available (quantity - reserved)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventory WHERE sku = ?", (sku,))
        row = cur.fetchone()
        if not row:
            return json.dumps({"error": f"SKU not found: {sku}"}, indent=2)

        row_d = dict(row)
        available = int(row_d["quantity"]) - int(row_d.get("reserved", 0))
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
    finally:
        conn.close()




@mcp.tool()
def get_notes(entity_type: str, entity_id: str) -> str:
    """Get all internal notes for an entity (order, customer, or inventory)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, entity_type, entity_id, author, body, created_at
            FROM notes
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY created_at
            """,
            (entity_type, entity_id),
        )
        rows = [dict(r) for r in cur.fetchall()]
        return json.dumps(rows, indent=2, default=str)
    finally:
        conn.close()


@mcp.tool()
def add_note(entity_type: str, entity_id: str, body: str, author: str = "Agent") -> str:
    """Add an internal note to an entity (order, customer, or inventory). Has side effects: persists the note."""
    now = datetime.now(timezone.utc)
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO notes (entity_type, entity_id, author, body, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (entity_type, entity_id, author, body, now.isoformat()),
        )
        note_id = cur.lastrowid
        conn.commit()
        cur.execute(
            """
            SELECT id, entity_type, entity_id, author, body, created_at
            FROM notes WHERE id = ?
            """,
            (note_id,),
        )
        row = cur.fetchone()
        return json.dumps({"ok": True, "note": dict(row)}, indent=2, default=str)
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")


