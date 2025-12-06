# Cache Design Document

## MicroLending Platform
Saksham Mehta, Jose Lamela, Richard Baah  
5th December 2025

---

## Introduction

This document describes our Redis caching implementation for the MicroLending analytics platform. We use caching to speed up the GUI—dropdown menus load from cache instead of hitting the database every time, and the data grid uses look-ahead paging to make scrolling feel instant.

The cache is a performance optimization, not a requirement for the app to function. If Redis goes down, everything still works; it just falls back to database queries.

---

## Redis Setup

We run Redis in Docker using the official Alpine image. Here's our docker-compose configuration:

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: microlending-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
```

A few notes on these choices:
- **Alpine image** — It's tiny (~7MB) and has everything we need. No point using the full Debian-based image.
- **appendonly yes** — This enables Redis persistence. Without it, cached data would be lost on restart. With AOF (append-only file), Redis logs every write and can recover data after a crash.
- **Health check** — Docker uses this to know if Redis is actually ready, not just running.

To start: `docker-compose up -d`

---

## Caching Pattern: Cache-Aside

We use the cache-aside pattern (also called lazy loading). The flow is:

```
1. Application receives request
2. Check Redis for cached data
3. If found (cache HIT) → return cached data
4. If not found (cache MISS):
   a. Query the database
   b. Store result in Redis with TTL
   c. Return data to caller
```

In code:

```python
def get_reference_data(ref_type):
    cache_key = f"ml:reference:{ref_type}"
    
    # Check cache first
    cached = redis.get_json(cache_key)
    if cached is not None:
        return {"data": cached, "cached": True}
    
    # Cache miss - load from database
    data = load_from_database(ref_type)
    
    # Store in cache for next time
    redis.set_json(cache_key, data, ttl=3600)
    
    return {"data": data, "cached": False}
```

### Why Cache-Aside?

We considered write-through caching (update cache on every database write) but rejected it:
- Our data is read-heavy. The analytics dashboard gets way more reads than writes.
- Write-through adds complexity to every write operation.
- With cache-aside, the cache populates itself on first read. Simple and automatic.

The tradeoff is that the first request after cache expiration is slower (has to hit the database). But subsequent requests are fast, which is what matters for a dashboard that gets refreshed constantly.

---

## Key Structure

All cache keys follow a consistent naming pattern:

```
ml:{category}:{identifier}
```

For example, `ml:reference:currencies` holds the list of currencies for dropdowns, `ml:reference:loan_types` has the loan product types, and `ml:reference:regions` stores geographic regions. For paginated transaction data, we use keys like `ml:transactions:p1:s10` (page 1, 10 items per page) and `ml:transactions:p2:s10` (page 2, same page size).

The prefix `ml:` (for microlending) namespaces our keys so they don't collide with anything else that might be in the same Redis instance.

### Value Format

Values are stored as JSON strings. We use Python's json module for serialization:

```python
def set_json(self, key, data, ttl):
    json_str = json.dumps(data)
    self.redis.setex(key, ttl, json_str)

def get_json(self, key):
    json_str = self.redis.get(key)
    if json_str is None:
        return None
    return json.loads(json_str)
```

We could use Redis hashes or sorted sets for more complex data, but JSON strings have a big advantage: they're human-readable. You can debug by just running `redis-cli GET ml:reference:currencies` and reading the output.

---

## TTL Strategy

Different types of data get different expiration times based on how often they change. Reference data like currencies and regions gets a 1-hour TTL (3600 seconds) since this stuff almost never changes. Transaction pages get a shorter 5-minute TTL (300 seconds) because they're more dynamic—new transactions come in throughout the day, and we want reasonably fresh data without hammering the database on every request. Analytics aggregates sit in the middle at 30 minutes (1800 seconds) since they're pre-computed and change at a moderate rate.

The TTLs are configurable via environment variables:

```python
REFERENCE_TTL = int(os.getenv('CACHE_REFERENCE_TTL', 3600))
TRANSACTION_TTL = int(os.getenv('CACHE_TRANSACTION_TTL', 300))
```

### Cache Invalidation

When data changes, we need to clear the stale cache. There are two approaches:

1. **Wait for TTL** — The cached data eventually expires. Simple, but there's a window where the cache is stale.

2. **Explicit invalidation** — Call a delete endpoint when data changes.

We support explicit invalidation via DELETE endpoints:

```bash
# Invalidate one type
curl -X DELETE http://localhost:8000/cache/reference/currencies

# Invalidate all reference data
curl -X DELETE http://localhost:8000/cache/reference/all
```

In a real system, we'd hook these into the OLTP write operations. When someone adds a new currency, the insert trigger could call the invalidation endpoint.

---

## Look-Ahead Paging

The transaction grid uses a pagination pattern where we pre-load the next page while the user is viewing the current one. This makes scrolling feel instant.

### How It Works

When the user requests page 1:
1. Load page 1 from cache or database
2. Return page 1 to the user immediately
3. In the background, check if page 2 is cached
4. If not, load page 2 and cache it

```python
async def get_transactions_page(page, page_size):
    cache_key = f"ml:transactions:p{page}:s{page_size}"
    
    # Get requested page
    data = redis.get_json(cache_key)
    if data is None:
        data = load_from_database(page, page_size)
        redis.set_json(cache_key, data, TRANSACTION_TTL)
    
    # Pre-load next page
    if data['has_next']:
        next_key = f"ml:transactions:p{page+1}:s{page_size}"
        if not redis.exists(next_key):
            next_data = load_from_database(page + 1, page_size)
            redis.set_json(next_key, next_data, TRANSACTION_TTL)
    
    return data
```

### User Experience

From the user's perspective:
- Page 1 load: might be slow (first request, cache miss)
- Page 2 load: instant (pre-cached while viewing page 1)
- Page 3 load: instant (pre-cached while viewing page 2)
- And so on...

If the user jumps directly to page 10, there's a cache miss and it's slow. But sequential scrolling, which is the common case, is always fast.

---

## Exception Handling

The cache should never break the application. If Redis is down, slow, or throws errors, we fall back to the database.

### Connection Handling

```python
class RedisClient:
    def __init__(self):
        try:
            self.redis = redis.Redis(
                host='localhost',
                port=6379,
                socket_timeout=2,  # Don't wait forever
                socket_connect_timeout=2
            )
            self.redis.ping()  # Verify connection
            self.available = True
        except RedisError:
            self.available = False
            logging.warning("Redis not available, caching disabled")
```

If the initial connection fails, we set `available = False` and all cache operations become no-ops. The app continues to work, just without caching.

### Operation-Level Fallback

Even if the initial connection succeeds, individual operations can fail. We wrap every cache call in try/except:

```python
def get_json(self, key):
    if not self.available:
        return None
    try:
        data = self.redis.get(key)
        return json.loads(data) if data else None
    except RedisError as e:
        logging.error(f"Redis GET failed for {key}: {e}")
        return None  # Triggers database fallback
```

A failed GET returns None (treated as cache miss), triggering a database load. A failed SET is logged but doesn't affect the response—the data was already retrieved from the database.

---

## Logging & Telemetry

### What We Log

Every cache operation logs its outcome:

```
INFO [cache] HIT ml:reference:currencies ttl=2847s latency=1.2ms
INFO [cache] MISS ml:reference:loan_types loaded from DB in 45.3ms
WARN [cache] Redis timeout for ml:transactions:p5:s10, falling back to DB
ERROR [cache] Redis connection refused
```

The log includes:
- Operation result (HIT, MISS, ERROR)
- Cache key
- Remaining TTL (for hits)
- Latency in milliseconds

### Metrics Tracking

We track aggregate metrics in Redis itself using time-series keys:

```
ml:metrics:hits:minute:202512051030   → 47
ml:metrics:misses:minute:202512051030 → 12
ml:metrics:hits:total                 → {currencies: 150, loan_types: 89, ...}
```

The `/cache/metrics` endpoint returns a summary:

```json
{
  "current_minute": {"hits": 47, "misses": 12, "hit_ratio": "79.7%"},
  "totals": {"hits": 1234, "misses": 456},
  "latency": {
    "cache_avg_ms": 1.5,
    "db_avg_ms": 42.3,
    "speedup": "28x"
  }
}
```

### Using Telemetry

These metrics help answer questions like:
- **Is caching working?** Check the hit ratio. Should be >70% for reference data.
- **Are TTLs set right?** High miss rate might mean TTLs are too short.
- **What's the performance gain?** Compare cache vs DB latency.

In production, we'd push these to a monitoring system like Prometheus or Datadog and set up alerts. For now, we just expose them via API.

---

## Demo Walkthrough

Here's how to demonstrate the caching behavior:

### Combo-Box Caching Demo

1. Clear the cache:
   ```bash
   redis-cli FLUSHDB
   ```

2. Load currencies (cache miss):
   ```bash
   curl http://localhost:8000/cache/reference/currencies
   # Look for "cached": false
   ```

3. Load currencies again (cache hit):
   ```bash
   curl http://localhost:8000/cache/reference/currencies
   # Look for "cached": true
   ```

4. Invalidate and reload:
   ```bash
   curl -X DELETE http://localhost:8000/cache/reference/currencies
   curl http://localhost:8000/cache/reference/currencies
   # Look for "cached": false (fresh load)
   ```

### Look-Ahead Paging Demo

1. Clear transaction cache:
   ```bash
   redis-cli KEYS 'ml:transactions:*' | xargs redis-cli DEL
   ```

2. Request page 1:
   ```bash
   curl "http://localhost:8000/reporting/transactions?page=1&page_size=10"
   # "cached": false
   ```

3. Check Redis—page 2 should be pre-cached:
   ```bash
   redis-cli KEYS 'ml:transactions:*'
   # Should show both p1 and p2
   ```

4. Request page 2 (instant hit):
   ```bash
   curl "http://localhost:8000/reporting/transactions?page=2&page_size=10"
   # "cached": true
   ```
