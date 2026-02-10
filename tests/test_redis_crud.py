from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jewelryops.services.redis import RedisCrudService, get_redis_crud_service


@pytest.fixture
def mock_redis() -> MagicMock:
    """Mock Redis client with async methods."""
    m = MagicMock()
    m.get = AsyncMock(return_value=None)
    m.set = AsyncMock(return_value=True)
    m.setex = AsyncMock(return_value=True)
    m.delete = AsyncMock(return_value=1)
    m.exists = AsyncMock(return_value=0)
    m.ping = AsyncMock(return_value=True)
    m.aclose = AsyncMock(return_value=None)
    return m


@pytest.mark.asyncio
async def test_redis_crud_get_missing(mock_redis: MagicMock) -> None:
    """get returns None when key is missing."""
    mock_redis.get.return_value = None
    with patch("jewelryops.services.redis.Redis") as redis_cls:
        redis_cls.from_url.return_value = mock_redis
        svc = RedisCrudService("redis://localhost:6379/0")
        svc._client = mock_redis
        val = await svc.get("missing")
        assert val is None
        mock_redis.get.assert_called_once_with("missing")


@pytest.mark.asyncio
async def test_redis_crud_get_present(mock_redis: MagicMock) -> None:
    """get returns string value when key exists."""
    mock_redis.get.return_value = "stored_value"
    svc = RedisCrudService("redis://localhost:6379/0")
    svc._client = mock_redis
    val = await svc.get("key")
    assert val == "stored_value"


@pytest.mark.asyncio
async def test_redis_crud_set_no_ttl(mock_redis: MagicMock) -> None:
    """set without ttl calls set()."""
    svc = RedisCrudService("redis://localhost:6379/0")
    svc._client = mock_redis
    ok = await svc.set("k", "v")
    assert ok is True
    mock_redis.set.assert_called_once_with("k", "v")
    mock_redis.setex.assert_not_called()


@pytest.mark.asyncio
async def test_redis_crud_set_with_ttl(mock_redis: MagicMock) -> None:
    """set with ttl_seconds calls setex()."""
    svc = RedisCrudService("redis://localhost:6379/0")
    svc._client = mock_redis
    ok = await svc.set("k", "v", ttl_seconds=60)
    assert ok is True
    mock_redis.setex.assert_called_once_with("k", 60, "v")
    mock_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_redis_crud_delete(mock_redis: MagicMock) -> None:
    """delete calls Redis delete."""
    svc = RedisCrudService("redis://localhost:6379/0")
    svc._client = mock_redis
    ok = await svc.delete("key")
    assert ok is True
    mock_redis.delete.assert_called_once_with("key")


@pytest.mark.asyncio
async def test_redis_crud_exists(mock_redis: MagicMock) -> None:
    """exists returns True when key exists."""
    mock_redis.exists.return_value = 1
    svc = RedisCrudService("redis://localhost:6379/0")
    svc._client = mock_redis
    assert await svc.exists("x") is True
    mock_redis.exists.return_value = 0
    assert await svc.exists("y") is False


@pytest.mark.asyncio
async def test_redis_crud_get_when_not_connected() -> None:
    """get returns None when client is None."""
    svc = RedisCrudService("redis://localhost:6379/0")
    assert svc._client is None
    val = await svc.get("any")
    assert val is None


def test_get_redis_crud_service_returns_none_when_no_url() -> None:
    """get_redis_crud_service returns None when redis_url is not set."""
    with patch("jewelryops.services.redis.get_settings") as get_settings:
        get_settings.return_value = MagicMock(redis_url=None)
        assert get_redis_crud_service() is None
        get_settings.return_value = MagicMock(redis_url="")
        assert get_redis_crud_service() is None


def test_get_redis_crud_service_returns_instance_when_url_set() -> None:
    """get_redis_crud_service returns RedisCrudService when redis_url is set."""
    with patch("jewelryops.services.redis.get_settings") as get_settings:
        get_settings.return_value = MagicMock(redis_url="redis://localhost:6379/0")
        svc = get_redis_crud_service()
        assert svc is not None
        assert isinstance(svc, RedisCrudService)
