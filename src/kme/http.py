"""Polite HTTP: one session, a User-Agent, throttling, retries with exponential backoff."""
from __future__ import annotations

import time

import requests

from . import config

_session = None
_last = 0.0


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": config.USER_AGENT, "Accept": "application/json"})
    return _session


def get_json(url: str, params: dict | None = None, timeout: float = 30.0, allow_404: bool = False):
    """GET JSON with throttle + up to MAX_RETRIES retries (backoff 1s, 2s, 4s).

    429 and 5xx are retried; other 4xx raise immediately (or return None for
    404 when ``allow_404``).
    """
    global _last
    err = None
    for attempt in range(config.MAX_RETRIES + 1):
        wait = config.MIN_SECONDS_BETWEEN_REQUESTS - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        try:
            r = session().get(url, params=params, timeout=timeout)
            _last = time.time()
            if r.status_code == 404 and allow_404:
                return None
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code} from {url}", response=r)
            r.raise_for_status()
            return r.json()
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            err = e
            resp = getattr(e, "response", None)
            if resp is not None and 400 <= resp.status_code < 500 and resp.status_code != 429:
                raise
            if attempt < config.MAX_RETRIES:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"GET {url} failed after {config.MAX_RETRIES + 1} attempts: {err}")
