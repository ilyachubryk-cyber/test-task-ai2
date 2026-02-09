import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .agent import get_mcp_tools_async, get_session, run_agent_stream
from .settings import get_settings


def setup_server_logging() -> logging.Logger:
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


LOGGER = setup_server_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load MCP tools at startup."""
    LOGGER.info("Loading MCP tools at startup...")
    try:
        await get_mcp_tools_async()
        LOGGER.info("MCP tools loaded successfully")
    except Exception as e:
        LOGGER.error(f"Failed to load MCP tools: {e}")
    yield
    LOGGER.info("Shutting down...")


app = FastAPI(
    title="JewelryOps AutoGen Agent",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok"}


@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint.
    """
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        try:
            payload = json.loads(raw)
            session_id = str(payload.get("session_id") or "default")
            message = str(payload.get("message") or "").strip()
        except Exception as e:  # noqa: BLE001
            LOGGER.error("Invalid WS payload: %s", e)
            await websocket.send_json({"type": "error", "data": "Invalid JSON payload"})
            await websocket.close()
            return

        if not message:
            await websocket.send_json({"type": "error", "data": "Empty message"})
            await websocket.close()
            return

        LOGGER.info("WS chat start session_id=%s", session_id)

        # Stream AutoGen agent output
        try:
            async for token in run_agent_stream(session_id=session_id, user_message=message):
                if token:
                    await websocket.send_json({"type": "token", "data": token})
        except Exception as e:  # noqa: BLE001
            LOGGER.exception("Error during agent streaming: %s", e)
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
    except Exception as e:  # noqa: BLE001
        LOGGER.exception("Unexpected WS error: %s", e)
        try:
            await websocket.send_json({"type": "error", "data": str(e)})
        except Exception:  # noqa: BLE001
            pass
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass


