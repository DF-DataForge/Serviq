"""Short-lived result cache for the dashboard endpoints.

The dashboards are read-only aggregates that are expensive to compute and
opened often (the landing page computes several of them). Results are
kept per database, company, language / time zone and arguments for
CACHE_TTL seconds; every dashboard's refresh button passes force=True to
recompute. The cache lives in the worker process, so with several
workers each keeps its own copy - that only costs an extra computation.
"""
import copy
import threading
import time

CACHE_TTL = 600  # seconds
_MAX_ENTRIES = 500
_cache = {}
_lock = threading.Lock()


def cached(model, name, args, compute, force=False, ttl=CACHE_TTL):
    """Return compute() from the cache when a fresh entry exists (a deep
    copy, so callers can never alter the stored value)."""
    env = model.env
    key = (env.cr.dbname, env.company.id, env.context.get('lang'),
           env.context.get('tz'), name, repr(args))
    now = time.monotonic()
    if not force:
        with _lock:
            hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return copy.deepcopy(hit[1])
    value = compute()
    with _lock:
        _cache[key] = (now, copy.deepcopy(value))
        if len(_cache) > _MAX_ENTRIES:
            for old in [k for k, (t, _v) in _cache.items() if now - t >= ttl]:
                _cache.pop(old, None)
    return value
