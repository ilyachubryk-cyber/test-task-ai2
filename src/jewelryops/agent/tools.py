import json
import logging
import re
from typing import Any, Dict, List

from openai import OpenAI

from ..settings import get_settings

logger = logging.getLogger(__name__)


def _make_tool_client() -> OpenAI:
    """Construct an OpenAI client for tool calls."""
    settings = get_settings()
    return OpenAI(
        api_key=settings.tool_api_key or settings.openai_api_key,
        base_url=settings.tool_base_url or settings.openai_base_url,
    )


def extract_entities(query: str) -> str:
    """Extract customer IDs, order IDs, and SKU codes from free text using LLM.

    Uses the configured `extract_entities_system_prompt` in settings.
    Returns a JSON string, typically:
        {
          "customer_ids": ["cust_001"],
          "order_ids": ["ORD-2038"],
          "skus": ["RING-101"]
        }
    """
    logger.info(f"Tool called: extract_entities with query={query[:100]}")
    settings = get_settings()
    client = _make_tool_client()

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
    )

    try:
        content = response.choices[0].message.content or ""
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            result = json_match.group(0)
            logger.info(f"Tool extract_entities completed successfully")
            return result
        logger.info(f"Tool extract_entities completed with content (no JSON): {content[:100]}")
        return content
    except Exception as e:
        logger.error(f"Tool extract_entities failed with error: {e}")
        return json.dumps(
            {
                "customer_ids": [],
                "order_ids": [],
                "skus": [],
                "error": str(e),
            }
        )


def summarize_state(history: str, current_notes: str = "") -> str:
    """Summarize the agent's current understanding using LLM.

    Uses the configured `summarize_state_system_prompt` in settings.
    Returns a JSON string with keys: summary, key_findings, open_items.
    """
    logger.info(f"Tool called: summarize_state with history={history[:100]}, notes={current_notes[:50]}")
    settings = get_settings()
    client = _make_tool_client()

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
    )

    try:
        content = response.choices[0].message.content or ""
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            result = json_match.group(0)
            logger.info(f"Tool summarize_state completed successfully")
            return result
        logger.info(f"Tool summarize_state completed with content (no JSON): {content[:100]}")
        return json.dumps(
            {"summary": content, "key_findings": [], "open_items": []}
        )
    except Exception as e:
        logger.error(f"Tool summarize_state failed with error: {e}")
        return json.dumps(
            {"error": str(e), "summary": "Unable to summarize"}
        )


def check_requires_confirmation(action_description: str) -> str:
    """Check if a proposed action needs explicit user approval using LLM.

    Uses the configured `check_requires_confirmation_system_prompt` in settings.
    Returns JSON:
        { "requires_confirmation": true/false, "reason": "..." }
    """
    logger.info(f"Tool called: check_requires_confirmation with action={action_description[:100]}")
    settings = get_settings()
    client = _make_tool_client()

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
    )

    try:
        content = response.choices[0].message.content or ""
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            result = json_match.group(0)
            logger.info(f"Tool check_requires_confirmation completed successfully")
            return result
        logger.info(f"Tool check_requires_confirmation completed with content (no JSON): {content[:100]}")
        return json.dumps(
            {
                "requires_confirmation": True,
                "reason": "Unable to determine - defaulting to safe choice",
            }
        )
    except Exception as e:
        logger.error(f"Tool check_requires_confirmation failed with error: {e}")
        return json.dumps(
            {
                "requires_confirmation": True,
                "reason": f"Error checking confirmation: {e}",
            }
        )


def get_custom_tool_schemas() -> List[Dict[str, Any]]:
    """Return OpenAI tool schemas for the custom function tools."""
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


def get_custom_function_map() -> Dict[str, Any]:
    """Return the function map used when registering tools with AutoGen."""
    return {
        "extract_entities": extract_entities,
        "summarize_state": summarize_state,
        "check_requires_confirmation": check_requires_confirmation,
    }

