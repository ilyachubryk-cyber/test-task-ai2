import logging
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from ..settings import get_settings

logger = logging.getLogger(__name__)


class RedisCrudService:
    """Async CRUD operations against a Redis instance."""

    def __init__(self, url: str) -> None:
        """Create a Redis client for the given URL (e.g. redis://localhost:6379/0)."""
        self._url = url
        self._client: Redis[bytes] | None = None

    async def connect(self) -> None:
        """Establish connection to Redis. Idempotent."""
        if self._client is not None:
            return
        self._client = Redis.from_url(
            self._url,
            decode_responses=True,
        )
        try:
            await self._client.ping()
            logger.info("Redis connection established: %s", self._url.split("@")[-1])
        except (RedisConnectionError, RedisTimeoutError) as e:
            logger.warning("Redis ping failed: %s", e)
            await self._client.aclose()
            self._client = None
            raise

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.debug("Redis connection closed")

    @property
    def client(self) -> Redis[Any] | None:
        """Return the underlying Redis client, or None if not connected."""
        return self._client

    async def get(self, key: str) -> str | None:
        """Return the value for key, or None if missing or on error."""
        if self._client is None:
            return None
        try:
            value = await self._client.get(key)
            return value if value is None else str(value)
        except (RedisConnectionError, RedisTimeoutError) as e:
            logger.warning("Redis get %s failed: %s", key, e)
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Set key to value. If ttl_seconds is set, the key will expire. Returns True on success."""
        if self._client is None:
            return False
        try:
            if ttl_seconds is not None and ttl_seconds > 0:
                await self._client.setex(key, ttl_seconds, value)
            else:
                await self._client.set(key, value)
            return True
        except (RedisConnectionError, RedisTimeoutError) as e:
            logger.warning("Redis set %s failed: %s", key, e)
            return False

    async def delete(self, key: str) -> bool:
        """Delete key. Returns True if key was deleted or did not exist."""
        if self._client is None:
            return False
        try:
            await self._client.delete(key)
            return True
        except (RedisConnectionError, RedisTimeoutError) as e:
            logger.warning("Redis delete %s failed: %s", key, e)
            return False

    async def exists(self, key: str) -> bool:
        """Return True if key exists."""
        if self._client is None:
            return False
        try:
            n = await self._client.exists(key)
            return bool(n)
        except (RedisConnectionError, RedisTimeoutError) as e:
            logger.warning("Redis exists %s failed: %s", key, e)
            return False


def get_redis_crud_service() -> RedisCrudService | None:
    """Return a Redis CRUD service if redis_url is configured, else None."""
    settings = get_settings()
    if not settings.redis_url or not settings.redis_url.strip():
        return None
    return RedisCrudService(settings.redis_url.strip())
