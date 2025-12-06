"""Cache Package for Micro-Lending Application."""

from .redis_client import RedisClient, RedisConfig, get_redis_client
from .cache_patterns import (
    CacheKeyBuilder,
    CacheAside,
    WriteThrough,
    LoanCache,
    UserCache,
    AnalyticsCache,
    CacheMetrics,
    cached,
    cache_invalidate,
    get_cache_metrics,
    DEFAULT_TTL,
    LOAN_TTL,
    USER_TTL,
    ANALYTICS_TTL
)

__all__ = [
    'RedisClient',
    'RedisConfig',
    'get_redis_client',
    'CacheKeyBuilder',
    'CacheAside',
    'WriteThrough',
    'LoanCache',
    'UserCache',
    'AnalyticsCache',
    'CacheMetrics',
    'cached',
    'cache_invalidate',
    'get_cache_metrics',
    'DEFAULT_TTL',
    'LOAN_TTL',
    'USER_TTL',
    'ANALYTICS_TTL'
]
