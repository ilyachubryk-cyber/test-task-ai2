from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jewelryops.services.context_service import ContextService
from jewelryops.models import SessionState
from jewelryops.services.redis import RedisCrudService


@pytest.fixture
def mock_redis_crud() -> MagicMock:
    """Mock Redis CRUD with async get/set/delete."""
    m = MagicMock(spec=RedisCrudService)
    m.get = AsyncMock(return_value=None)
    m.set = AsyncMock(return_value=True)
    m.delete = AsyncMock(return_value=True)
    return m


@pytest.fixture
def context_service(mock_redis_crud: MagicMock) -> ContextService:
    """ContextService with mocked Redis and TTL 3600."""
    return ContextService(redis_crud=mock_redis_crud, ttl_seconds=3600)


@pytest.mark.asyncio
async def test_get_context_missing(context_service: ContextService) -> None:
    """get_context returns None when key is not in Redis."""
    context_service._redis.get.return_value = None
    result = await context_service.get_context("session-1")
    assert result is None
    context_service._redis.get.assert_called_once_with("context:session-1")


@pytest.mark.asyncio
async def test_get_context_present(context_service: ContextService) -> None:
    """get_context returns SessionState when valid JSON is stored."""
    import json

    state = {
        "session_id": "s1",
        "messages": [{"role": "user", "content": "hi"}],
        "investigation_summary": "summary",
        "tool_calls_count": 2,
    }
    context_service._redis.get.return_value = json.dumps(state)
    result = await context_service.get_context("s1")
    assert result is not None
    assert result.session_id == "s1"
    assert len(result.messages) == 1
    assert result.messages[0]["content"] == "hi"
    assert result.investigation_summary == "summary"
    assert result.tool_calls_count == 2


@pytest.mark.asyncio
async def test_get_context_invalid_json(context_service: ContextService) -> None:
    """get_context returns None when stored value is invalid JSON."""
    context_service._redis.get.return_value = "not json"
    result = await context_service.get_context("s1")
    assert result is None


@pytest.mark.asyncio
async def test_save_context(context_service: ContextService) -> None:
    """save_context serializes SessionState and calls Redis set with TTL."""
    state = SessionState(
        session_id="s1",
        messages=[{"role": "assistant", "content": "Hello"}],
        investigation_summary="Done",
        tool_calls_count=1,
    )
    ok = await context_service.save_context("s1", state)
    assert ok is True
    context_service._redis.set.assert_called_once()
    call_args = context_service._redis.set.call_args
    assert call_args[0][0] == "context:s1"
    assert "s1" in call_args[0][1]
    assert call_args[1]["ttl_seconds"] == 3600


@pytest.mark.asyncio
async def test_delete_context(context_service: ContextService) -> None:
    """delete_context calls Redis delete with correct key."""
    ok = await context_service.delete_context("session-x")
    assert ok is True
    context_service._redis.delete.assert_called_once_with("context:session-x")
