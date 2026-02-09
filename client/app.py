import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterator

import streamlit as st
from websocket import create_connection


def setup_client_logging() -> logging.Logger:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("jewelryops.streamlit")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    fh = RotatingFileHandler(logs_dir / "client.log", maxBytes=2_000_000, backupCount=3)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


LOGGER = setup_client_logging()


def ws_token_stream(ws_url: str, session_id: str, message: str) -> Iterator[str]:
    """Connect to backend WS, send message, yield assistant tokens.
    
    Filters out leading JSON objects in the agent's response (used for
    internal tool metadata) and replaces them with a human-readable
    summary such as called tools and model thoughts.

    This happens entirely on the client so the backend can keep sending
    raw model output.
    """
    LOGGER.info("Connecting ws_url=%s session_id=%s", ws_url, session_id)
    ws = create_connection(ws_url, timeout=60)
    try:
        ws.send(json.dumps({"session_id": session_id, "message": message}))
        prefix_buffer = ""
        in_prefix = True
        
        while True:
            raw = ws.recv()
            payload = json.loads(raw)
            t = payload.get("type")
            if t == "token":
                token = payload.get("data") or ""
                if in_prefix:
                    prefix_buffer += token
                    replacement, remaining, still_prefix = _process_leading_json(prefix_buffer)
                    in_prefix = still_prefix

                    if not in_prefix:
                        if replacement:
                            for ch in replacement:
                                yield ch
                        if remaining:
                            for ch in remaining:
                                yield ch
                else:
                    for ch in token:
                        yield ch

            elif t == "done":
                if in_prefix and prefix_buffer:
                    for ch in prefix_buffer:
                        yield ch
                LOGGER.info(
                    "WS done session_id=%s tool_calls=%s",
                    payload.get("session_id"),
                    payload.get("tool_calls_count"),
                )
                return
            elif t == "error":
                err = payload.get("data") or "Unknown error"
                LOGGER.error("WS error: %s", err)
                raise RuntimeError(err)
    finally:
        ws.close()


def _is_json_object(s: str) -> bool:
    """Check if a string is a JSON object (not necessarily well-formed)."""
    s = s.strip()
    return s.startswith("{") and s.endswith("}")


def _format_json_prefix(obj: dict) -> str:
    """Turn a leading JSON object into human-readable text.

    We look for common keys like tools/tool_calls and thoughts/analysis.
    If we don't recognize the structure, we simply omit the JSON.
    """
    if not isinstance(obj, dict):
        return ""

    tools = (
        obj.get("tools")
        or obj.get("tool_calls")
        or obj.get("called_tools")
        or obj.get("tools_used")
    )
    thoughts = (
        obj.get("thoughts")
        or obj.get("analysis")
        or obj.get("reasoning")
        or obj.get("plan")
    )

    parts: list[str] = []

    if tools:
        parts.append("Investigation Steps:\n")
        if isinstance(tools, list):
            for idx, t in enumerate(tools, 1):
                if isinstance(t, str):
                    name = t
                elif isinstance(t, dict):
                    name = t.get("name") or t.get("tool") or json.dumps(t)
                else:
                    name = str(t)
                parts.append(f"{idx}. {name}\n")
        else:
            parts.append(f"- Tools: {tools}\n")

    if thoughts:
        parts.append("\nThoughts:\n")
        parts.append(str(thoughts).strip() + "\n\n")

    return "".join(parts)


def _process_leading_json(prefix_buffer: str) -> tuple[str, str, bool]:
    """Detect and strip a leading JSON object from the buffer, if present.

    Returns (replacement_text, remaining_text, still_in_prefix).
    - replacement_text: human-readable text to emit instead of JSON
    - remaining_text: any non-JSON content that follows immediately
    - still_in_prefix: whether we are still unsure and should keep buffering
    """
    s = prefix_buffer.lstrip()
    if not s:
        return "", "", True

    if not s.startswith("{"):
        return "", prefix_buffer, False

    last_brace = s.rfind("}")
    if last_brace == -1:
        return "", "", True

    candidate = s[: last_brace + 1]
    try:
        obj = json.loads(candidate)
    except Exception:
        return "", "", True

    replacement = _format_json_prefix(obj)
    remaining = s[last_brace + 1 :]
    return replacement, remaining, False


st.set_page_config(page_title="JewelryOps Agent", page_icon="💎", layout="centered")

st.title("JewelryOps Agent")

with st.sidebar:
    st.subheader("Connection")
    default_ws = "ws://localhost:8000/ws/chat"
    ws_url = st.text_input("WebSocket URL", value=default_ws)
    session_id = st.text_input("Session ID", value=st.session_state.get("session_id", "streamlit-demo"))
    st.session_state["session_id"] = session_id
    st.markdown("---")
    if st.button("Clear chat"):
        st.session_state["messages"] = []

if "messages" not in st.session_state:
    st.session_state["messages"] = []

for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("Ask about an order, customer, or inventory issue…")
if prompt:
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            full = st.write_stream(ws_token_stream(ws_url, session_id, prompt))
        except Exception as e:
            full = f"Error: {e}"
            st.error(full)

    st.session_state["messages"].append({"role": "assistant", "content": full})
