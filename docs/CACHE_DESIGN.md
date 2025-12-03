# Cache Design

## MicroLending Platform
Saksham Mehta, Jose Lamela, Richard Baah  
December 2025

---

## Redis Setup

We're running Redis in Docker using the official Alpine image. The docker-compose.yml is pretty simple:

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
```

We went with Alpine because the image is tiny. The appendonly flag gives us persistence so cached data survives restarts. To start it up: `docker-compose up -d`

---

## Caching Pattern

We use cache-aside (also called lazy loading). The idea is simple:

1. Check Redis first
2. If it's there, return it
3. If not, get it from the database, store it in Redis, then return it

```python
def get_or_set(self, key, fetch_fn, ttl):
    cached = redis.get_json(key)
    if cached is not None:
        return cached  # cache hit
    
    # cache miss - go to database
    data = fetch_fn()
    if data is not None:
        redis.set_json(key, data, ttl)
    return data
```

We chose this over write-through because it's simpler and our data is mostly read-heavy. The analytics dashboard gets hit way more than data gets updated.

The nice thing about cache-aside is if Redis dies, the app still works—it just gets everything from the database (slower but functional).

---

## Key Structure

All our keys follow the pattern `ml:{type}:{identifier}`. Examples:
- `ml:reference:currencies` — list of currencies for dropdown
- `ml:reference:loan_types` — loan product types
- `ml:transactions:p1:s10:stall:ball` — page 1 of transactions, 10 per page

Values are stored as JSON strings. We could use Redis hashes or something fancier, but JSON is easy to debug (you can just redis-cli GET the key and read it) and Python's json module handles everything.

---

## TTLs

Different data gets different expiration times:

Reference data like currencies and regions gets 1 hour (3600 seconds). This stuff almost never changes, so we cache it aggressively.

Transaction pages get 5 minutes (300 seconds). The data is more dynamic, but we still want some caching for the grid UI.

Analytics summaries get 30 minutes. They're pre-aggregated so we don't want to recalculate them constantly.

---

## Combo-Box Caching

When the GUI loads, it needs to populate dropdowns for currencies, loan types, regions, etc. These come from the `/cache/reference/{type}` endpoint.

First request for currencies hits the database, caches the result, returns it with `cached: false`. Second request finds it in Redis and returns immediately with `cached: true`.

If someone adds a new currency to the database, we need to invalidate the cache. There's a DELETE endpoint for that:

```
DELETE /cache/reference/currencies
```

Or to clear everything:

```
DELETE /cache/reference/all
```

After invalidation, the next request reloads from the database.

---

## Look-Ahead Paging

This is for the transaction grid. When a user requests page 1, we also pre-load page 2 into the cache. That way, when they scroll down, page 2 is already there.

```python
# Load the requested page
data = load_from_db(page)
redis.set(cache_key, data, ttl=300)

# Pre-cache next page
if page < total_pages:
    next_key = f"ml:transactions:p{page+1}:..."
    if not redis.exists(next_key):
        next_data = load_from_db(page + 1)
        redis.set(next_key, next_data, ttl=300)
```

The result is that after the first page load, scrolling through the grid is really fast—each page is already cached. We only go back to the database when the cache expires or if someone jumps to a random page.

---

## Error Handling

If Redis is down or slow, we don't crash. The code catches connection errors and falls back to the database:

```python
try:
    cached = redis.get_json(key)
except RedisError:
    cached = None  # will trigger database load
```

It's slower without the cache, but the app keeps working.

---

## Telemetry

Redis tracks hits and misses automatically. You can see them with:

```bash
redis-cli INFO stats | grep keyspace
# keyspace_hits:24
# keyspace_misses:12
```

That's a 66% hit rate, which is pretty good. Memory usage:

```bash
redis-cli INFO memory | grep used_memory_human
# used_memory_human:1.21M
```

We also log cache hits/misses in the application logs so we can see which keys are being accessed most.

---

## Demo Flow

For the combo-box demo:
1. Load currencies → cache miss, loads from DB
2. Load currencies again → cache hit
3. Invalidate with DELETE endpoint
4. Load currencies → cache miss again (fresh data)

For the grid demo:
1. Request page 1 → cache miss, also pre-caches page 2
2. Request page 2 → cache hit
3. Request page 1 again → cache hit
