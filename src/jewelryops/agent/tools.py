import json
import logging
import re
from functools import lru_cache
from typing import Any, Dict, List

from openai import OpenAI

from ..settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _tool_timeout() -> float:
    """Lazy-read timeout from settings (avoids import cycle at module load).
    
    Returns:
        float: Tool request timeout in seconds.
    """
    return get_settings().tool_request_timeout_seconds


def _make_tool_client() -> OpenAI:
    """Construct an OpenAI client for tool calls (uses tool_* settings and timeout)."""
    settings = get_settings()
    return OpenAI(
        api_key=settings.tool_api_key or settings.openai_api_key,
        base_url=settings.tool_base_url or settings.openai_base_url,
        timeout=settings.tool_request_timeout_seconds,
    )


def extract_entities(query: str) -> str:
    """Extract customer IDs, order IDs, and SKU codes from free text using LLM.

    Uses the configured `extract_entities_system_prompt` in settings.
    
    Args:
        query: Free text query to extract entities from (str).
        
    Returns:
        JSON string, typically:
            {
              "customer_ids": ["cust_001"],
              "order_ids": ["ORD-2038"],
              "skus": ["RING-101"]
            }
    """
    settings = get_settings()
    client = _make_tool_client()

    try:
        response = client.chat.completions.create(
            model=settings.tool_model,
            messages=[
                {
                    "role": "system",
                    "content": settings.extract_entities_system_prompt,
                },
                {"role": "user", "content": f"Extract entities from: {query}"},
            ],
            temperature=0.0,
            timeout=_tool_timeout(),
        )
    except (TimeoutError, ConnectionError) as e:
        logger.error("Tool extract_entities request failed: %s", e)
        return json.dumps(
            {"customer_ids": [], "order_ids": [], "skus": [], "error": str(e)}
        )

    try:
        content = response.choices[0].message.content or ""
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json_match.group(0)
        return content
    except (AttributeError, KeyError, IndexError) as e:
        logger.error("Tool extract_entities response parse failed: %s", e)
        return json.dumps(
            {"customer_ids": [], "order_ids": [], "skus": [], "error": str(e)}
        )


def summarize_state(history: str, current_notes: str = "") -> str:
    """Summarize the agent's current understanding using LLM.

    Uses the configured `summarize_state_system_prompt` in settings.
    
    Args:
        history: Text representation of the conversation and tool results (str).
        current_notes: Optional notes to fold into the summary (str, default: "").
        
    Returns:
        JSON string with keys: summary, key_findings, open_items.
    """
    settings = get_settings()
    client = _make_tool_client()

    try:
        response = client.chat.completions.create(
            model=settings.tool_model,
            messages=[
                {
                    "role": "system",
                    "content": settings.summarize_state_system_prompt,
                },
                {
                    "role": "user",
                    "content": (
                        "Summarize this investigation:\n\n"
                        f"History:\n{history}\n\n"
                        f"Additional notes:\n{current_notes}"
                    ),
                },
            ],
            temperature=0.0,
            timeout=_tool_timeout(),
        )
    except (TimeoutError, ConnectionError) as e:
        logger.error("Tool summarize_state request failed: %s", e)
        return json.dumps({"error": str(e), "summary": "Unable to summarize"})

    try:
        content = response.choices[0].message.content or ""
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json_match.group(0)
        return json.dumps(
            {"summary": content, "key_findings": [], "open_items": []}
        )
    except (AttributeError, KeyError, IndexError) as e:
        logger.error("Tool summarize_state response parse failed: %s", e)
        return json.dumps({"error": str(e), "summary": "Unable to summarize"})


def check_requires_confirmation(action_description: str) -> str:
    """Check if a proposed action needs explicit user approval using LLM.

    Uses the configured `check_requires_confirmation_system_prompt` in settings.
    
    Args:
        action_description: Description of the action to check (str).
        
    Returns:
        JSON string: { "requires_confirmation": true/false, "reason": "..." }
    """
    settings = get_settings()
    client = _make_tool_client()

    try:
        response = client.chat.completions.create(
            model=settings.tool_model,
            messages=[
                {
                    "role": "system",
                    "content": settings.check_requires_confirmation_system_prompt,
                },
                {
                    "role": "user",
                    "content": (
                        "Does this action require user confirmation? "
                        f"{action_description}"
                    ),
                },
            ],
            temperature=0.0,
            timeout=_tool_timeout(),
        )
    except (TimeoutError, ConnectionError) as e:
        logger.error("Tool check_requires_confirmation request failed: %s", e)
        return json.dumps(
            {
                "requires_confirmation": True,
                "reason": f"Error checking confirmation: {e}",
            }
        )

    try:
        content = response.choices[0].message.content or ""
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json_match.group(0)
        return json.dumps(
            {
                "requires_confirmation": True,
                "reason": "Unable to determine - defaulting to safe choice",
            }
        )
    except (AttributeError, KeyError, IndexError) as e:
        logger.error("Tool check_requires_confirmation response parse failed: %s", e)
        return json.dumps(
            {
                "requires_confirmation": True,
                "reason": f"Error checking confirmation: {e}",
            }
        )


@lru_cache(maxsize=1)
def get_custom_tool_schemas() -> List[Dict[str, Any]]:
    """Return OpenAI tool schemas for the custom function tools (cached).
    
    Returns:
        List[Dict[str, Any]]: Cached list of tool schemas in OpenAI function format.
    """
    return [
            {
                "type": "function",
                "function": {
                    "name": "extract_entities",
                    "description": "Extract customer IDs, order IDs, and SKU codes from text",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The text to extract entities from",
                            }
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "summarize_state",
                    "description": "Summarize the current investigation state",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "history": {
                                "type": "string",
                                "description": "A text representation of the conversation and tool results",
                            },
                            "current_notes": {
                                "type": "string",
                                "description": "Optional notes to fold into the summary",
                            },
                        },
                        "required": ["history"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_requires_confirmation",
                    "description": "Check if an action requires explicit user confirmation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action_description": {
                                "type": "string",
                                "description": "Description of the action to check",
                            }
                        },
                        "required": ["action_description"],
                    },
                },
            },
        ]


@lru_cache(maxsize=1)
def _get_cached_function_map() -> Dict[str, Any]:
    """Internal implementation for get_custom_function_map (cached).
    
    Returns:
        Dict[str, Any]: Map of function names to callable functions.
    """
    return {
        "extract_entities": extract_entities,
        "summarize_state": summarize_state,
        "check_requires_confirmation": check_requires_confirmation,
    }


def get_custom_function_map() -> Dict[str, Any]:
    """Return the function map used when registering tools with AutoGen (cached).
    
    Returns:
        Dict[str, Any]: Map of tool names to functions.
    """
    return _get_cached_function_map()
