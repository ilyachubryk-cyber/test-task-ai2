import json
import logging
from typing import Any, Dict

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from ..models import SessionState
from ..services.redis import RedisCrudService
from ..settings import get_settings
from .redis import get_redis_crud_service

logger = logging.getLogger(__name__)

CONTEXT_KEY_PREFIX = "context:"


def _session_to_dict(state: SessionState) -> Dict[str, Any]:
    """Serialize SessionState to a JSON-serializable dict."""
    return {
        "session_id": state.session_id,
        "messages": state.messages,
        "investigation_summary": state.investigation_summary,
        "tool_calls_count": state.tool_calls_count,
    }


def _dict_to_session(data: Dict[str, Any]) -> SessionState:
    """Build SessionState from a dict (e.g. from Redis)."""
    return SessionState(
        session_id=data.get("session_id", ""),
        messages=data.get("messages", []),
        investigation_summary=data.get("investigation_summary", ""),
        tool_calls_count=int(data.get("tool_calls_count", 0)),
    )


class ContextService:
    """Manages agent chat context using Redis with TTL."""

    def __init__(
        self,
        redis_crud: RedisCrudService,
        ttl_seconds: int,
    ) -> None:
        self._redis = redis_crud
        self._ttl = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"{CONTEXT_KEY_PREFIX}{session_id}"

    async def get_context(self, session_id: str) -> SessionState | None:
        """Load context for session_id from Redis. Returns None if missing or on error."""
        key = self._key(session_id)
        raw = await self._redis.get(key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return _dict_to_session(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Invalid context data for %s: %s", session_id, e)
            return None

    async def save_context(self, session_id: str, state: SessionState) -> bool:
        """Persist context for session_id with TTL. Returns True on success."""
        key = self._key(session_id)
        data = _session_to_dict(state)
        try:
            payload = json.dumps(data)
        except (TypeError, ValueError) as e:
            logger.warning("Context serialization failed for %s: %s", session_id, e)
            return False
        return await self._redis.set(key, payload, ttl_seconds=self._ttl)

    async def delete_context(self, session_id: str) -> bool:
        """Remove context for session_id. Returns True on success."""
        return await self._redis.delete(self._key(session_id))


def get_context_service() -> ContextService | None:
    """Build ContextService if Redis is configured and connected; else return None."""
    redis_crud = get_redis_crud_service()
    if redis_crud is None:
        return None
    settings = get_settings()
    return ContextService(
        redis_crud=redis_crud,
        ttl_seconds=settings.context_ttl_seconds,
    )


# Lazy singleton for optional async init (connect to Redis)
_context_service_instance: ContextService | None = None


async def get_context_service_async() -> ContextService | None:
    """Return the context service after ensuring Redis is connected. Cached."""
    global _context_service_instance
    redis_crud = get_redis_crud_service()
    if redis_crud is None:
        return None
    if _context_service_instance is None:
        try:
            await redis_crud.connect()
            settings = get_settings()
            _context_service_instance = ContextService(
                redis_crud=redis_crud,
                ttl_seconds=settings.context_ttl_seconds,
            )
        except (RedisConnectionError, RedisTimeoutError, ConnectionError, TimeoutError) as e:
            logger.warning("Context service unavailable (Redis): %s", e)
            return None
    return _context_service_instance


async def close_context_service() -> None:
    """Close the Redis connection used by the context service. Idempotent."""
    global _context_service_instance
    if _context_service_instance is not None:
        await _context_service_instance._redis.close()
        _context_service_instance = None
        logger.debug("Context service (Redis) closed")
