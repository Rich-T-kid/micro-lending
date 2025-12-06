"""Cache Patterns for Micro-Lending Application."""

import os
import json
import logging
import hashlib
from functools import wraps
from typing import Any, Callable, Optional, Union
from datetime import datetime

from cache.redis_client import get_redis_client, RedisClient

logger = logging.getLogger(__name__)

# TTL values loaded from environment or use defaults
# These can be overridden via CACHE_*_TTL environment variables
DEFAULT_TTL = int(os.getenv('CACHE_DEFAULT_TTL', 300))
LOAN_TTL = int(os.getenv('CACHE_LOAN_TTL', 600))
USER_TTL = int(os.getenv('CACHE_USER_TTL', 900))
ANALYTICS_TTL = int(os.getenv('CACHE_ANALYTICS_TTL', 1800))


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


class CacheMetrics:
    """Time-series metrics for cache telemetry (hits, misses, latency)."""
    
    METRICS_TTL = 86400  # 24 hours
    METRICS_PREFIX = 'ml:metrics'
    
    def __init__(self, redis_client: RedisClient = None):
        self._redis = redis_client or get_redis_client()
    
    def _get_minute_key(self) -> str:
        """Get current minute timestamp for bucketing."""
        return datetime.now().strftime('%Y%m%d%H%M')
    
    def _get_hour_key(self) -> str:
        """Get current hour timestamp for hourly aggregates."""
        return datetime.now().strftime('%Y%m%d%H')
    
    def record_hit(self, operation: str = 'general', latency_ms: float = 0) -> None:
        """Record a cache hit with optional latency."""
        minute_key = self._get_minute_key()
        hour_key = self._get_hour_key()
        
        # Increment hit counters
        self._redis._client.hincrby(f'{self.METRICS_PREFIX}:hits:minute:{minute_key}', operation, 1)
        self._redis._client.hincrby(f'{self.METRICS_PREFIX}:hits:hour:{hour_key}', operation, 1)
        self._redis._client.hincrby(f'{self.METRICS_PREFIX}:hits:total', operation, 1)
        
        # Set TTL on minute/hour keys
        self._redis.expire(f'{self.METRICS_PREFIX}:hits:minute:{minute_key}', self.METRICS_TTL)
        self._redis.expire(f'{self.METRICS_PREFIX}:hits:hour:{hour_key}', self.METRICS_TTL)
        
        # Record latency if provided
        if latency_ms > 0:
            self._redis._client.lpush(f'{self.METRICS_PREFIX}:latency:cache:{minute_key}', latency_ms)
            self._redis._client.ltrim(f'{self.METRICS_PREFIX}:latency:cache:{minute_key}', 0, 999)
            self._redis.expire(f'{self.METRICS_PREFIX}:latency:cache:{minute_key}', self.METRICS_TTL)
    
    def record_miss(self, operation: str = 'general', latency_ms: float = 0) -> None:
        """Record a cache miss with optional latency."""
        minute_key = self._get_minute_key()
        hour_key = self._get_hour_key()
        
        # Increment miss counters
        self._redis._client.hincrby(f'{self.METRICS_PREFIX}:misses:minute:{minute_key}', operation, 1)
        self._redis._client.hincrby(f'{self.METRICS_PREFIX}:misses:hour:{hour_key}', operation, 1)
        self._redis._client.hincrby(f'{self.METRICS_PREFIX}:misses:total', operation, 1)
        
        # Set TTL
        self._redis.expire(f'{self.METRICS_PREFIX}:misses:minute:{minute_key}', self.METRICS_TTL)
        self._redis.expire(f'{self.METRICS_PREFIX}:misses:hour:{hour_key}', self.METRICS_TTL)
        
        # Record DB latency if provided
        if latency_ms > 0:
            self._redis._client.lpush(f'{self.METRICS_PREFIX}:latency:db:{minute_key}', latency_ms)
            self._redis._client.ltrim(f'{self.METRICS_PREFIX}:latency:db:{minute_key}', 0, 999)
            self._redis.expire(f'{self.METRICS_PREFIX}:latency:db:{minute_key}', self.METRICS_TTL)
    
    def record_error(self, operation: str = 'general', error_type: str = 'unknown') -> None:
        """Record a cache error."""
        minute_key = self._get_minute_key()
        hour_key = self._get_hour_key()
        
        # Increment error counters
        self._redis._client.hincrby(f'{self.METRICS_PREFIX}:errors:minute:{minute_key}', operation, 1)
        self._redis._client.hincrby(f'{self.METRICS_PREFIX}:errors:hour:{hour_key}', operation, 1)
        self._redis._client.hincrby(f'{self.METRICS_PREFIX}:errors:total', operation, 1)
        
        # Log error type
        self._redis._client.hincrby(f'{self.METRICS_PREFIX}:error_types:{hour_key}', error_type, 1)
        
        # Set TTL
        self._redis.expire(f'{self.METRICS_PREFIX}:errors:minute:{minute_key}', self.METRICS_TTL)
        self._redis.expire(f'{self.METRICS_PREFIX}:errors:hour:{hour_key}', self.METRICS_TTL)
        self._redis.expire(f'{self.METRICS_PREFIX}:error_types:{hour_key}', self.METRICS_TTL)
    
    def record_invalidation(self, operation: str = 'general', keys_invalidated: int = 1) -> None:
        """Record cache invalidation event."""
        minute_key = self._get_minute_key()
        
        self._redis._client.hincrby(f'{self.METRICS_PREFIX}:invalidations:minute:{minute_key}', operation, keys_invalidated)
        self._redis._client.hincrby(f'{self.METRICS_PREFIX}:invalidations:total', operation, keys_invalidated)
        self._redis.expire(f'{self.METRICS_PREFIX}:invalidations:minute:{minute_key}', self.METRICS_TTL)
    
    def get_current_stats(self) -> dict:
        """Get current minute's statistics."""
        minute_key = self._get_minute_key()
        hour_key = self._get_hour_key()
        
        hits_minute = self._redis.hgetall(f'{self.METRICS_PREFIX}:hits:minute:{minute_key}') or {}
        misses_minute = self._redis.hgetall(f'{self.METRICS_PREFIX}:misses:minute:{minute_key}') or {}
        errors_minute = self._redis.hgetall(f'{self.METRICS_PREFIX}:errors:minute:{minute_key}') or {}
        
        hits_total = self._redis.hgetall(f'{self.METRICS_PREFIX}:hits:total') or {}
        misses_total = self._redis.hgetall(f'{self.METRICS_PREFIX}:misses:total') or {}
        errors_total = self._redis.hgetall(f'{self.METRICS_PREFIX}:errors:total') or {}
        
        # Calculate totals
        total_hits_min = sum(int(v) for v in hits_minute.values())
        total_misses_min = sum(int(v) for v in misses_minute.values())
        total_errors_min = sum(int(v) for v in errors_minute.values())
        
        total_hits = sum(int(v) for v in hits_total.values())
        total_misses = sum(int(v) for v in misses_total.values())
        total_errors = sum(int(v) for v in errors_total.values())
        
        # Calculate hit ratio
        total_requests = total_hits + total_misses
        hit_ratio = round(total_hits / total_requests * 100, 2) if total_requests > 0 else 0
        
        # Get average latencies
        cache_latencies = self._redis._client.lrange(f'{self.METRICS_PREFIX}:latency:cache:{minute_key}', 0, -1)
        db_latencies = self._redis._client.lrange(f'{self.METRICS_PREFIX}:latency:db:{minute_key}', 0, -1)
        
        avg_cache_latency = 0
        avg_db_latency = 0
        if cache_latencies:
            avg_cache_latency = round(sum(float(l) for l in cache_latencies) / len(cache_latencies), 2)
        if db_latencies:
            avg_db_latency = round(sum(float(l) for l in db_latencies) / len(db_latencies), 2)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'minute_key': minute_key,
            'current_minute': {
                'hits': total_hits_min,
                'misses': total_misses_min,
                'errors': total_errors_min,
                'requests': total_hits_min + total_misses_min,
                'hit_ratio': round(total_hits_min / (total_hits_min + total_misses_min) * 100, 2) if (total_hits_min + total_misses_min) > 0 else 0
            },
            'totals': {
                'hits': total_hits,
                'misses': total_misses,
                'errors': total_errors,
                'requests': total_requests,
                'hit_ratio': hit_ratio
            },
            'latency': {
                'avg_cache_ms': avg_cache_latency,
                'avg_db_ms': avg_db_latency,
                'speedup_factor': round(avg_db_latency / avg_cache_latency, 2) if avg_cache_latency > 0 else 0
            },
            'errors_per_minute': total_errors_min
        }
    
    def get_hourly_stats(self, hours: int = 24) -> list:
        """Get hourly statistics for the last N hours."""
        stats = []
        now = datetime.now()
        
        for i in range(hours):
            hour = now.replace(minute=0, second=0, microsecond=0)
            hour_key = hour.strftime('%Y%m%d%H')
            
            hits = self._redis.hgetall(f'{self.METRICS_PREFIX}:hits:hour:{hour_key}') or {}
            misses = self._redis.hgetall(f'{self.METRICS_PREFIX}:misses:hour:{hour_key}') or {}
            errors = self._redis.hgetall(f'{self.METRICS_PREFIX}:errors:hour:{hour_key}') or {}
            
            total_hits = sum(int(v) for v in hits.values())
            total_misses = sum(int(v) for v in misses.values())
            total_errors = sum(int(v) for v in errors.values())
            total_requests = total_hits + total_misses
            
            stats.append({
                'hour': hour_key,
                'hits': total_hits,
                'misses': total_misses,
                'errors': total_errors,
                'requests': total_requests,
                'hit_ratio': round(total_hits / total_requests * 100, 2) if total_requests > 0 else 0,
                'error_rate': round(total_errors / total_requests * 100, 4) if total_requests > 0 else 0
            })
            
            now = now.replace(hour=now.hour - 1 if now.hour > 0 else 23)
        
        return stats
    
    def reset_metrics(self) -> int:
        """Reset all metrics (for testing)."""
        keys = self._redis.keys(f'{self.METRICS_PREFIX}:*')
        if keys:
            return self._redis.delete(*keys)
        return 0


# Singleton instance for easy access
_metrics_instance = None

def get_cache_metrics() -> CacheMetrics:
    """Get singleton CacheMetrics instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = CacheMetrics()
    return _metrics_instance
