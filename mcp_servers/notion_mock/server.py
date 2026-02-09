import json
from pathlib import Path
from typing import List, Dict, Any

try:
    from fastmcp import FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP


_DATA_DIR = Path(__file__).resolve().parent / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_ISSUES_PATH = _DATA_DIR / "issues.json"


def _load_issues() -> List[Dict[str, Any]]:
    if not _ISSUES_PATH.exists():
        _ISSUES_PATH.write_text("[]", encoding="utf-8")
    with open(_ISSUES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save_issues(issues: List[Dict[str, Any]]) -> None:
    with open(_ISSUES_PATH, "w", encoding="utf-8") as f:
        json.dump(issues, f, indent=2)


def _ensure_seed_data() -> None:
    if _ISSUES_PATH.exists():
        return
    seed = [
        {
            "id": "ISSUE-1",
            "title": "Investigate shipping delays for ORD-2038",
            "status": "open",
            "priority": "high",
            "tags": ["shipping", "sla"],
        },
        {
            "id": "ISSUE-2",
            "title": "Inventory discrepancy for BRAC-301",
            "status": "in_progress",
            "priority": "medium",
            "tags": ["inventory"],
        },
    ]
    _save_issues(seed)


_ensure_seed_data()

mcp = FastMCP("Notion Mock (Issues)", json_response=True)


@mcp.tool()
def get_issue(issue_id: str) -> str:
    """Get a single issue by ID (e.g. ISSUE-1)."""
    issues = _load_issues()
    for issue in issues:
        if issue["id"] == issue_id:
            return json.dumps(issue, indent=2)
    return json.dumps({"error": f"Issue not found: {issue_id}"}, indent=2)


@mcp.tool()
def list_issues(status: str = "", limit: int = 20) -> str:
    """List issues, optionally filtered by status (open, in_progress, closed)."""
    issues = _load_issues()
    if status:
        issues = [i for i in issues if i.get("status") == status]
    return json.dumps(issues[:limit], indent=2)


@mcp.tool()
def create_issue(title: str, priority: str = "medium") -> str:
    """Create a new mock issue. Side effect: persists to the local JSON file."""
    issues = _load_issues()
    new_id = f"ISSUE-{len(issues) + 1}"
    issue = {
        "id": new_id,
        "title": title,
        "status": "open",
        "priority": priority,
    }
    issues.append(issue)
    _save_issues(issues)
    return json.dumps({"ok": True, "issue": issue}, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")


