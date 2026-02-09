import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "jewelryops.db"


def init_database():
    """Initialize database schema and load mock data."""
    conn = sqlite3.connect(DB_PATH)
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

        cur.execute("SELECT COUNT(*) FROM customers")
        if cur.fetchone()[0] > 0:
            print("✓ Database already initialized with data")
            return

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
                now.replace(day=1, hour=10).isoformat(),
                now.replace(day=5).isoformat(),
                2499.00,
            ),
            (
                "ORD-2041",
                "cust_002",
                "BRAC-301",
                "delivered",
                now.replace(day=1, hour=8).isoformat(),
                now.replace(day=4).isoformat(),
                3299.00,
            ),
            (
                "ORD-2050",
                "cust_003",
                "NECK-210",
                "processing",
                now.replace(day=7, hour=14).isoformat(),
                now.replace(day=12).isoformat(),
                4599.00,
            ),
            (
                "ORD-2035",
                "cust_004",
                "BRAC-302",
                "returned",
                now.replace(day=25, hour=9).isoformat(),
                now.replace(day=28).isoformat(),
                5299.00,
            ),
            (
                "ORD-2055",
                "cust_005",
                "RING-102",
                "processing",
                now.replace(day=8, hour=11).isoformat(),
                now.replace(day=15).isoformat(),
                8999.00,
            ),
            (
                "ORD-2052",
                "cust_001",
                "EARR-401",
                "processing",
                now.replace(day=6, hour=15).isoformat(),
                now.replace(day=11).isoformat(),
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

        conn.commit()
        print("✓ Database initialized successfully")
        print(f"  - Customers: {len(customers)}")
        print(f"  - Orders: {len(orders)}")
        print(f"  - Inventory: {len(inventory)}")
        print(f"  - Notes: {len(notes)}")

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    init_database()
