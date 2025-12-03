"""Redis Connectivity Test Script."""

import sys
import time
from datetime import datetime

sys.path.insert(0, '.')

from cache.redis_client import get_redis_client, RedisConfig
from cache.cache_patterns import (
    CacheKeyBuilder, CacheAside, LoanCache, UserCache, 
    AnalyticsCache, cached, DEFAULT_TTL
)


def print_header(title: str):
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print('=' * 60)


def print_result(test: str, passed: bool, detail: str = ''):
    status = '✓ PASS' if passed else '✗ FAIL'
    print(f"  {status}: {test}")
    if detail:
        print(f"         {detail}")


def test_connection():
    print_header("TEST 1: Redis Connection")
    client = get_redis_client()
    
    result = client.ping()
    print_result("Ping Redis server", result)
    
    info = client.info()
    if info:
        print_result("Get server info", True, f"Redis v{info.get('redis_version', 'unknown')}")
    else:
        print_result("Get server info", False)
    
    return result


def test_basic_operations():
    print_header("TEST 2: Basic Operations")
    client = get_redis_client()
    
    test_key = 'test:basic:key'
    test_value = 'test_value_123'
    
    set_result = client.set(test_key, test_value, ttl=60)
    print_result("SET operation", set_result)
    
    get_result = client.get(test_key)
    print_result("GET operation", get_result == test_value, f"Got: {get_result}")
    
    exists_result = client.exists(test_key)
    print_result("EXISTS operation", exists_result)
    
    ttl_result = client.ttl(test_key)
    print_result("TTL operation", ttl_result > 0, f"TTL: {ttl_result}s")
    
    del_result = client.delete(test_key)
    print_result("DELETE operation", del_result > 0)
    
    return all([set_result, get_result == test_value, exists_result, del_result > 0])


def test_json_operations():
    print_header("TEST 3: JSON Operations")
    client = get_redis_client()
    
    test_key = 'test:json:key'
    test_data = {
        'user_id': 1,
        'name': 'Test User',
        'balance': 1500.50,
        'active': True,
        'created_at': datetime.now().isoformat()
    }
    
    set_result = client.set_json(test_key, test_data, ttl=60)
    print_result("SET JSON", set_result)
    
    get_result = client.get_json(test_key)
    print_result("GET JSON", get_result is not None)
    
    if get_result:
        match = get_result.get('user_id') == test_data['user_id']
        print_result("JSON data integrity", match, f"user_id: {get_result.get('user_id')}")
    
    client.delete(test_key)
    return set_result and get_result is not None


def test_hash_operations():
    print_header("TEST 4: Hash Operations")
    client = get_redis_client()
    
    hash_name = 'test:hash:user'
    
    client.hset(hash_name, 'name', 'John Doe')
    client.hset(hash_name, 'email', 'john@example.com')
    client.hset(hash_name, 'role', 'borrower')
    print_result("HSET multiple fields", True)
    
    name = client.hget(hash_name, 'name')
    print_result("HGET single field", name == 'John Doe', f"Got: {name}")
    
    all_data = client.hgetall(hash_name)
    print_result("HGETALL", len(all_data) == 3, f"Fields: {list(all_data.keys())}")
    
    client.delete(hash_name)
    return name == 'John Doe' and len(all_data) == 3


def test_cache_patterns():
    print_header("TEST 5: Cache-Aside Pattern")
    cache = CacheAside()
    
    fetch_count = 0
    def mock_fetch():
        nonlocal fetch_count
        fetch_count += 1
        return {'data': 'from_database', 'fetch_count': fetch_count}
    
    key = 'test:cache:aside'
    
    result1 = cache.get_or_set(key, mock_fetch, ttl=60)
    print_result("First call (cache miss)", fetch_count == 1, "Fetched from source")
    
    result2 = cache.get_or_set(key, mock_fetch, ttl=60)
    print_result("Second call (cache hit)", fetch_count == 1, "Served from cache")
    
    invalidated = cache.invalidate(key)
    print_result("Cache invalidation", invalidated, "Key removed")
    
    result3 = cache.get_or_set(key, mock_fetch, ttl=60)
    print_result("After invalidation", fetch_count == 2, "Fetched again")
    
    cache.invalidate(key)
    return fetch_count == 2


def test_domain_caches():
    print_header("TEST 6: Domain-Specific Caches")
    
    loan_cache = LoanCache()
    def fetch_loan():
        return {'loan_id': 101, 'amount': 5000, 'status': 'active'}
    
    loan = loan_cache.get_loan(101, fetch_loan)
    print_result("LoanCache.get_loan", loan is not None, f"Loan: {loan.get('loan_id')}")
    loan_cache.invalidate_loan(101)
    
    user_cache = UserCache()
    def fetch_user():
        return {'user_id': 1, 'name': 'Test User', 'role': 'borrower'}
    
    user = user_cache.get_user(1, fetch_user)
    print_result("UserCache.get_user", user is not None, f"User: {user.get('name')}")
    user_cache.invalidate_user(1)
    
    analytics_cache = AnalyticsCache()
    def fetch_summary():
        return {'total_loans': 150, 'active': 120, 'defaulted': 5}
    
    summary = analytics_cache.get_daily_summary('20251202', fetch_summary)
    print_result("AnalyticsCache.get_daily_summary", summary is not None)
    analytics_cache.invalidate_analytics()
    
    return loan is not None and user is not None and summary is not None


def test_key_builder():
    print_header("TEST 7: Cache Key Builder")
    
    user_key = CacheKeyBuilder.user(123)
    print_result("User key format", user_key == 'ml:user:123', f"Key: {user_key}")
    
    loan_key = CacheKeyBuilder.loan(456)
    print_result("Loan key format", loan_key == 'ml:loan:456', f"Key: {loan_key}")
    
    analytics_key = CacheKeyBuilder.analytics('summary', '20251202')
    print_result("Analytics key format", 'ml:analytics:summary' in analytics_key, f"Key: {analytics_key}")
    
    custom_key = CacheKeyBuilder.build('custom', 'a', 'b', param1='x')
    print_result("Custom key with kwargs", custom_key.startswith('ml:custom:a:b:'), f"Key: {custom_key}")
    
    return True


def test_decorator():
    print_header("TEST 8: @cached Decorator")
    
    call_count = 0
    
    @cached(ttl=60, key_prefix='test_func')
    def expensive_operation(x, y):
        nonlocal call_count
        call_count += 1
        return x + y
    
    result1 = expensive_operation(5, 3)
    print_result("First decorated call", call_count == 1 and result1 == 8)
    
    result2 = expensive_operation(5, 3)
    print_result("Second decorated call (cached)", call_count == 1 and result2 == 8)
    
    result3 = expensive_operation(10, 20)
    print_result("Different args (new cache)", call_count == 2 and result3 == 30)
    
    client = get_redis_client()
    client.delete(*client.keys('ml:test_func:*'))
    
    return call_count == 2


def run_all_tests():
    print("\n" + "=" * 60)
    print(" REDIS CONNECTIVITY & CACHE PATTERN TESTS")
    print("=" * 60)
    print(f" Host: {RedisConfig.HOST}:{RedisConfig.PORT}")
    print(f" Time: {datetime.now().isoformat()}")
    
    tests = [
        ("Connection", test_connection),
        ("Basic Ops", test_basic_operations),
        ("JSON Ops", test_json_operations),
        ("Hash Ops", test_hash_operations),
        ("Cache-Aside", test_cache_patterns),
        ("Domain Caches", test_domain_caches),
        ("Key Builder", test_key_builder),
        ("Decorator", test_decorator),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            results.append((name, test_fn()))
        except Exception as e:
            print(f"\n  ✗ EXCEPTION in {name}: {e}")
            results.append((name, False))
    
    print_header("SUMMARY")
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = '✓' if result else '✗'
        print(f"  {status} {name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    print("=" * 60)
    
    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
