"""Cache Patterns for Micro-Lending Application."""

import json
import logging
import hashlib
from functools import wraps
from typing import Any, Callable, Optional, Union
from datetime import datetime

from cache.redis_client import get_redis_client, RedisClient

logger = logging.getLogger(__name__)

DEFAULT_TTL = 300
LOAN_TTL = 600
USER_TTL = 900
ANALYTICS_TTL = 1800


class CacheKeyBuilder:
    PREFIX = 'ml'

    @classmethod
    def build(cls, namespace: str, *args, **kwargs) -> str:
        parts = [cls.PREFIX, namespace]
        parts.extend(str(a) for a in args)
        if kwargs:
            sorted_items = sorted(kwargs.items())
            parts.append(hashlib.md5(str(sorted_items).encode()).hexdigest()[:8])
        return ':'.join(parts)

    @classmethod
    def user(cls, user_id: int) -> str:
        return cls.build('user', user_id)

    @classmethod
    def loan(cls, loan_id: int) -> str:
        return cls.build('loan', loan_id)

    @classmethod
    def wallet(cls, user_id: int) -> str:
        return cls.build('wallet', user_id)

    @classmethod
    def analytics(cls, report_name: str, date: str = None) -> str:
        return cls.build('analytics', report_name, date or datetime.now().strftime('%Y%m%d'))

    @classmethod
    def query(cls, query_hash: str) -> str:
        return cls.build('query', query_hash)


class CacheAside:
    def __init__(self, redis_client: RedisClient = None):
        self._redis = redis_client or get_redis_client()

    def get_or_set(self, key: str, fetch_fn: Callable, ttl: int = DEFAULT_TTL) -> Optional[Any]:
        cached = self._redis.get_json(key)
        if cached is not None:
            logger.debug(f"Cache HIT: {key}")
            return cached

        logger.debug(f"Cache MISS: {key}")
        data = fetch_fn()
        if data is not None:
            self._redis.set_json(key, data, ttl)
        return data

    def invalidate(self, key: str) -> bool:
        logger.debug(f"Cache INVALIDATE: {key}")
        return self._redis.delete(key) > 0

    def invalidate_pattern(self, pattern: str) -> int:
        keys = self._redis.keys(pattern)
        if keys:
            return self._redis.delete(*keys)
        return 0


class WriteThrough:
    def __init__(self, redis_client: RedisClient = None):
        self._redis = redis_client or get_redis_client()

    def write(self, key: str, data: Any, persist_fn: Callable, ttl: int = DEFAULT_TTL) -> bool:
        try:
            persist_fn(data)
            self._redis.set_json(key, data, ttl)
            logger.debug(f"Write-through: {key}")
            return True
        except Exception as e:
            logger.error(f"Write-through failed for {key}: {e}")
            self._redis.delete(key)
            raise


def cached(ttl: int = DEFAULT_TTL, key_prefix: str = None):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            prefix = key_prefix or func.__name__
            cache_key = CacheKeyBuilder.build(prefix, *args[1:] if args else args, **kwargs)
            
            redis_client = get_redis_client()
            cached_value = redis_client.get_json(cache_key)
            
            if cached_value is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_value
            
            logger.debug(f"Cache MISS: {cache_key}")
            result = func(*args, **kwargs)
            
            if result is not None:
                redis_client.set_json(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


def cache_invalidate(key_pattern: str):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            redis_client = get_redis_client()
            
            if '{' in key_pattern:
                actual_key = key_pattern.format(*args[1:] if args else args, **kwargs)
            else:
                actual_key = key_pattern
            
            redis_client.delete(actual_key)
            logger.debug(f"Cache invalidated: {actual_key}")
            
            return result
        return wrapper
    return decorator


class AnalyticsCache:
    def __init__(self, redis_client: RedisClient = None):
        self._redis = redis_client or get_redis_client()
        self._cache = CacheAside(self._redis)

    def get_daily_summary(self, date: str, fetch_fn: Callable) -> Optional[dict]:
        key = CacheKeyBuilder.analytics('daily_summary', date)
        return self._cache.get_or_set(key, fetch_fn, ANALYTICS_TTL)

    def get_portfolio_snapshot(self, fetch_fn: Callable) -> Optional[dict]:
        key = CacheKeyBuilder.analytics('portfolio_snapshot')
        return self._cache.get_or_set(key, fetch_fn, ANALYTICS_TTL)

    def get_credit_distribution(self, fetch_fn: Callable) -> Optional[dict]:
        key = CacheKeyBuilder.analytics('credit_distribution')
        return self._cache.get_or_set(key, fetch_fn, ANALYTICS_TTL)

    def invalidate_analytics(self) -> int:
        return self._cache.invalidate_pattern('ml:analytics:*')


class LoanCache:
    def __init__(self, redis_client: RedisClient = None):
        self._redis = redis_client or get_redis_client()
        self._cache = CacheAside(self._redis)

    def get_loan(self, loan_id: int, fetch_fn: Callable) -> Optional[dict]:
        key = CacheKeyBuilder.loan(loan_id)
        return self._cache.get_or_set(key, fetch_fn, LOAN_TTL)

    def invalidate_loan(self, loan_id: int) -> bool:
        return self._cache.invalidate(CacheKeyBuilder.loan(loan_id))

    def get_user_loans(self, user_id: int, fetch_fn: Callable) -> Optional[list]:
        key = CacheKeyBuilder.build('user_loans', user_id)
        return self._cache.get_or_set(key, fetch_fn, LOAN_TTL)


class UserCache:
    def __init__(self, redis_client: RedisClient = None):
        self._redis = redis_client or get_redis_client()
        self._cache = CacheAside(self._redis)

    def get_user(self, user_id: int, fetch_fn: Callable) -> Optional[dict]:
        key = CacheKeyBuilder.user(user_id)
        return self._cache.get_or_set(key, fetch_fn, USER_TTL)

    def invalidate_user(self, user_id: int) -> bool:
        return self._cache.invalidate(CacheKeyBuilder.user(user_id))

    def get_wallet(self, user_id: int, fetch_fn: Callable) -> Optional[dict]:
        key = CacheKeyBuilder.wallet(user_id)
        return self._cache.get_or_set(key, fetch_fn, USER_TTL)

    def invalidate_wallet(self, user_id: int) -> bool:
        return self._cache.invalidate(CacheKeyBuilder.wallet(user_id))
