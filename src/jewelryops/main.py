import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .agent import get_mcp_tools_async, get_session, run_agent_stream
from .services.context_service import close_context_service, get_context_service_async
from .settings import get_settings


def setup_server_logging() -> logging.Logger:
    """Configure and return the server logger."""
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("jewelryops.server")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    fh = RotatingFileHandler(logs_dir / "server.log", maxBytes=5_000_000, backupCount=3)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


def _cors_origins_list(origins: str) -> list[str]:
    """Parse CORS_ORIGINS into a list."""
    if not origins or origins.strip() == "*":
        return ["*"]
    return [o.strip() for o in origins.split(",") if o.strip()]


LOGGER = setup_server_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load MCP tools and optional Redis context at startup; close Redis on shutdown."""
    LOGGER.info("Loading MCP tools at startup...")
    try:
        await get_mcp_tools_async()
        LOGGER.info("MCP tools loaded successfully")
    except (OSError, ConnectionError, TimeoutError) as e:
        LOGGER.warning("MCP tools partially or fully unavailable: %s", e)
    except (ValueError, RuntimeError) as e:
        LOGGER.exception("Failed to load MCP tools: %s", e)
    except Exception as e:
        LOGGER.exception("Unexpected error loading MCP tools: %s", e)

    # Optional: connect Redis for context persistence (context_ttl_seconds)
    try:
        await get_context_service_async()
        LOGGER.info("Context service (Redis) ready")
    except Exception as e:
        LOGGER.debug("Context service not available: %s", e)

    yield

    LOGGER.info("Shutting down...")
    await close_context_service()


app = FastAPI(
    title="JewelryOps AutoGen Agent",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins_list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, Any]:
    """Health check for load balancers and monitoring.
    
    Returns:
        dict[str, Any]: JSON response with status field.
    """
    return {"status": "ok"}


@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket) -> None:
    """WebSocket chat endpoint: client sends { session_id, message }, server streams tokens then done.
    
    Args:
        websocket: WebSocket connection from client.
        
    Expected Input (JSON):
        {
            "session_id": str - unique session identifier,
            "message": str - user query text
        }
        
    Response Format:
        Streams JSON objects with fields:
        - {"type": "token", "data": str} - individual response tokens
        - {"type": "done", "session_id": str, "tool_calls_count": int} - completion message
        - {"type": "error", "data": str} - error message if applicable
    """
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            LOGGER.error("Invalid WS payload (not JSON): %s", e)
            await websocket.send_json({"type": "error", "data": "Invalid JSON payload"})
            await websocket.close()
            return

        session_id = str(payload.get("session_id") or "default")
        message = str(payload.get("message") or "").strip()

        if not message:
            await websocket.send_json({"type": "error", "data": "Empty message"})
            await websocket.close()
            return

        LOGGER.info("WS chat start session_id=%s", session_id)

        try:
            async for token in run_agent_stream(session_id=session_id, user_message=message):
                if token:
                    await websocket.send_json({"type": "token", "data": token})
        except (TimeoutError, ConnectionError) as e:
            LOGGER.exception("Network error during agent streaming: %s", e)
            await websocket.send_json({"type": "error", "data": str(e)})
            await websocket.close()
            return
        except ValueError as e:
            LOGGER.exception("Agent configuration or state error: %s", e)
            await websocket.send_json({"type": "error", "data": str(e)})
            await websocket.close()
            return

        session = get_session(session_id)
        await websocket.send_json(
            {
                "type": "done",
                "session_id": session_id,
                "tool_calls_count": session.tool_calls_count,
            }
        )

    except WebSocketDisconnect:
        LOGGER.info("WS disconnect")
    except (ConnectionError, TimeoutError, RuntimeError) as e:
        LOGGER.exception("Unexpected WS error: %s", e)
        try:
            await websocket.send_json({"type": "error", "data": str(e)})
        except (OSError, RuntimeError, ValueError, TypeError):
            pass
        try:
            await websocket.close()
        except (OSError, RuntimeError):
            pass


