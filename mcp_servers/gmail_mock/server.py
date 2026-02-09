import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

try:
    from fastmcp import FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP


_DATA_DIR = Path(__file__).resolve().parent / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_EMAILS_PATH = _DATA_DIR / "emails.json"


def _load_emails() -> List[Dict[str, Any]]:
    if not _EMAILS_PATH.exists():
        _EMAILS_PATH.write_text("[]", encoding="utf-8")
    with open(_EMAILS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save_emails(emails: List[Dict[str, Any]]) -> None:
    with open(_EMAILS_PATH, "w", encoding="utf-8") as f:
        json.dump(emails, f, indent=2)


def _ensure_seed_emails() -> None:
    if _EMAILS_PATH.exists():
        return
    now = datetime(2025, 2, 1, 13, 0, 0, tzinfo=timezone.utc).isoformat()
    seed = [
        {
            "id": "EMAIL-1",
            "direction": "in",
            "from": "lisa.park@example.com",
            "to": "support@jewelryops.test",
            "subject": "Re: Order ORD-2038 still not delivered",
            "body": "Hi, my order ORD-2038 is still late. Can you check what happened?",
            "created_at": now,
        },
        {
            "id": "EMAIL-2",
            "direction": "out",
            "from": "support@jewelryops.test",
            "to": "ops-team@jewelryops.test",
            "subject": "Inventory discrepancy BRAC-301",
            "body": "We saw a discrepancy for BRAC-301. Please confirm latest physical count.",
            "created_at": now,
        },
    ]
    _save_emails(seed)


_ensure_seed_emails()

mcp = FastMCP("Gmail Mock", json_response=True)


@mcp.tool()
def list_emails(direction: str = "", limit: int = 20) -> str:
    """List mock emails, optionally filtered by direction ('in' or 'out')."""
    emails = _load_emails()
    if direction:
        emails = [e for e in emails if e.get("direction") == direction]
    emails_sorted = sorted(emails, key=lambda e: e.get("created_at", ""), reverse=True)
    return json.dumps(emails_sorted[:limit], indent=2)


@mcp.tool()
def search_emails(query: str, limit: int = 20) -> str:
    """Search emails by subject or body (case-insensitive)."""
    emails = _load_emails()
    q = query.lower()
    matches = [
        e
        for e in emails
        if q in e.get("subject", "").lower() or q in e.get("body", "").lower()
    ]
    matches_sorted = sorted(matches, key=lambda e: e.get("created_at", ""), reverse=True)
    return json.dumps(matches_sorted[:limit], indent=2)


@mcp.tool()
def send_email(to: str, subject: str, body: str, sender: str = "support@jewelryops.test") -> str:
    """Send a mock email (adds an 'out' email record)."""
    emails = _load_emails()
    new_id = f"EMAIL-{len(emails) + 1}"
    now = datetime.now(timezone.utc).isoformat()
    email = {
        "id": new_id,
        "direction": "out",
        "from": sender,
        "to": to,
        "subject": subject,
        "body": body,
        "created_at": now,
    }
    emails.append(email)
    _save_emails(emails)
    return json.dumps({"ok": True, "email": email}, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")


