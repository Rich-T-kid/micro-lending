"""Redis Client Wrapper for Micro-Lending Cache Layer."""

import os
import json
import logging
from typing import Any, Optional, Union
from datetime import timedelta

import redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError

logger = logging.getLogger(__name__)


class RedisConfig:
    HOST = os.getenv('REDIS_HOST', 'localhost')
    PORT = int(os.getenv('REDIS_PORT', 6379))
    DB = int(os.getenv('REDIS_DB', 0))
    PASSWORD = os.getenv('REDIS_PASSWORD', None)
    SOCKET_TIMEOUT = 5
    SOCKET_CONNECT_TIMEOUT = 5
    RETRY_ON_TIMEOUT = True
    DECODE_RESPONSES = True


class RedisClient:
    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._pool = redis.ConnectionPool(
            host=RedisConfig.HOST,
            port=RedisConfig.PORT,
            db=RedisConfig.DB,
            password=RedisConfig.PASSWORD,
            socket_timeout=RedisConfig.SOCKET_TIMEOUT,
            socket_connect_timeout=RedisConfig.SOCKET_CONNECT_TIMEOUT,
            retry_on_timeout=RedisConfig.RETRY_ON_TIMEOUT,
            decode_responses=RedisConfig.DECODE_RESPONSES
        )
        self._client = redis.Redis(connection_pool=self._pool)

    @property
    def client(self) -> redis.Redis:
        return self._client

    def ping(self) -> bool:
        try:
            return self._client.ping()
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    def get(self, key: str) -> Optional[str]:
        try:
            return self._client.get(key)
        except RedisError as e:
            logger.error(f"Redis GET failed for {key}: {e}")
            return None

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        try:
            if ttl:
                return self._client.setex(key, ttl, value)
            return self._client.set(key, value)
        except RedisError as e:
            logger.error(f"Redis SET failed for {key}: {e}")
            return False

    def delete(self, *keys: str) -> int:
        try:
            return self._client.delete(*keys)
        except RedisError as e:
            logger.error(f"Redis DELETE failed: {e}")
            return 0

    def exists(self, key: str) -> bool:
        try:
            return self._client.exists(key) > 0
        except RedisError as e:
            logger.error(f"Redis EXISTS failed for {key}: {e}")
            return False

    def expire(self, key: str, ttl: int) -> bool:
        try:
            return self._client.expire(key, ttl)
        except RedisError as e:
            logger.error(f"Redis EXPIRE failed for {key}: {e}")
            return False

    def ttl(self, key: str) -> int:
        try:
            return self._client.ttl(key)
        except RedisError as e:
            logger.error(f"Redis TTL failed for {key}: {e}")
            return -2

    def get_json(self, key: str) -> Optional[Any]:
        value = self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON for key {key}")
        return None

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        try:
            return self.set(key, json.dumps(value, default=str), ttl)
        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization failed for {key}: {e}")
            return False

    def hget(self, name: str, key: str) -> Optional[str]:
        try:
            return self._client.hget(name, key)
        except RedisError as e:
            logger.error(f"Redis HGET failed for {name}:{key}: {e}")
            return None

    def hset(self, name: str, key: str, value: str) -> int:
        try:
            return self._client.hset(name, key, value)
        except RedisError as e:
            logger.error(f"Redis HSET failed for {name}:{key}: {e}")
            return 0

    def hgetall(self, name: str) -> dict:
        try:
            return self._client.hgetall(name)
        except RedisError as e:
            logger.error(f"Redis HGETALL failed for {name}: {e}")
            return {}

    def keys(self, pattern: str = '*') -> list:
        try:
            return self._client.keys(pattern)
        except RedisError as e:
            logger.error(f"Redis KEYS failed for pattern {pattern}: {e}")
            return []

    def flushdb(self) -> bool:
        try:
            return self._client.flushdb()
        except RedisError as e:
            logger.error(f"Redis FLUSHDB failed: {e}")
            return False

    def info(self) -> dict:
        try:
            return self._client.info()
        except RedisError as e:
            logger.error(f"Redis INFO failed: {e}")
            return {}

    def close(self):
        if self._pool:
            self._pool.disconnect()


def get_redis_client() -> RedisClient:
    return RedisClient()
