from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SessionState:
    """Per-session conversation state (messages, summary, tool call count)."""

    session_id: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    investigation_summary: str = ""
    tool_calls_count: int = 0
