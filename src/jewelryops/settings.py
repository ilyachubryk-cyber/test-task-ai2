from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_iterations: int = 25
    openai_api_key: str | None = None
    openai_base_url: str | None = "https://api.openai.com/v1"

    tool_model: str = "gpt-4o-mini"
    tool_api_key: str | None = None
    tool_base_url: str | None = "https://api.openai.com/v1"
    tool_request_timeout_seconds: float = 60.0

    cors_origins: str = "*"

    redis_url: str | None = None
    context_ttl_seconds: int = 86400  # 24 hours

    agent_system_prompt: str = (
        "You are a senior support specialist at JewelryOps, a luxury jewelry "
        "retailer.\n\n"
        " Your Role\n"
        "You investigate customer service, order fulfillment, and inventory issues.\n"
        "You make multi-step investigations using available tools.\n"
        "You apply business judgment, policies, and customer context to propose actions.\n"
        "You always maintain clarity about what you've found and your reasoning.\n\n"
        " Analysis process: "
        " - Look at emails, notes for any open questions or issues.\n"
        " - Check customer and order details for relevant context.\n"
        " - Use tools to investigate and gather more information as needed.\n"
        " - Summarize your findings and propose next steps or resolutions.\n\n"
        " - Write responses to people if nesessary.\n\n"
        "Keep your answers precise and professional."
    )

    extract_entities_system_prompt: str = (
        "You are an entity extraction assistant. Extract customer IDs (cust_XXX), "
        "order IDs (ORD-XXXX), and SKU codes (WORD-XXX) from the given text. "
        "Return a JSON object with keys: customer_ids, order_ids, skus (all arrays). "
        "Only include IDs that are clearly present in the text."
    )
    summarize_state_system_prompt: str = (
        "You are a helpful assistant that creates concise summaries of support "
        "investigations. Analyze the conversation history and create a brief, clear "
        "summary of the investigation state. Return JSON with keys: summary (string), "
        "key_findings (array), open_items (array)."
    )
    check_requires_confirmation_system_prompt: str = (
        "You are a risk assessment assistant for support actions. Determine if an "
        "action requires explicit user confirmation. Return JSON with keys: "
        "requires_confirmation (bool), reason (string). Actions that modify data, "
        "cancel orders, refund money, or delete records typically require confirmation."
    )

    mcp_jewelryops_cmd: str | None = None
    mcp_notion_cmd: str | None = None
    mcp_gmail_cmd: str | None = None

    db_sqlite_path: Path = Path("data/jewelryops.db")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        env_map={
            "HOST": "host",
            "PORT": "port",
            "DEBUG": "debug",
            "LOG_LEVEL": "log_level",
            "MODEL": "model",
            "TEMPERATURE": "temperature",
            "MAX_ITERATIONS": "max_iterations",
            "OPENAI_API_KEY": "openai_api_key",
            "OPENAI_BASE_URL": "openai_base_url",
            "TOOL_MODEL": "tool_model",
            "TOOL_API_KEY": "tool_api_key",
            "TOOL_BASE_URL": "tool_base_url",
            "TOOL_REQUEST_TIMEOUT_SECONDS": "tool_request_timeout_seconds",
            "CORS_ORIGINS": "cors_origins",
            "REDIS_URL": "redis_url",
            "CONTEXT_TTL_SECONDS": "context_ttl_seconds",
            "AGENT_SYSTEM_PROMPT": "agent_system_prompt",
            "EXTRACT_ENTITIES_SYSTEM_PROMPT": "extract_entities_system_prompt",
            "SUMMARIZE_STATE_SYSTEM_PROMPT": "summarize_state_system_prompt",
            "CHECK_REQUIRES_CONFIRMATION_SYSTEM_PROMPT": "check_requires_confirmation_system_prompt",
            "MCP_JEWELRYOPS_CMD": "mcp_jewelryops_cmd",
            "MCP_NOTION_CMD": "mcp_notion_cmd",
            "MCP_GMAIL_CMD": "mcp_gmail_cmd",
            "DB_SQLITE_PATH": "db_sqlite_path",
        },
        extra="allow",
    )


def get_settings() -> Settings:
    """Return the application settings singleton (loaded from env / .env)."""
    global _SETTINGS
    try:
        return _SETTINGS
    except NameError:
        _SETTINGS = Settings()
        return _SETTINGS


