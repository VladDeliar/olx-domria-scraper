"""HTTP utilities: session with retries, UA rotation, jittered rate limiting."""

from __future__ import annotations

import random
import time
from typing import Final

import requests
from fake_useragent import UserAgent
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_MIN_DELAY_SEC: Final[float] = 1.0
_MAX_DELAY_SEC: Final[float] = 3.0
_TIMEOUT_SEC: Final[float] = 15.0

_ua = UserAgent()


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
        }
    )
    return session


@retry(
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def fetch(session: requests.Session, url: str) -> requests.Response:
    """Fetch URL with retries, rotating User-Agent, raising on HTTP errors."""
    headers = {"User-Agent": _ua.random}
    response = session.get(url, headers=headers, timeout=_TIMEOUT_SEC)
    response.raise_for_status()
    return response


def polite_sleep() -> None:
    """Jittered pause between requests, per project rate-limit rule (1–3 sec)."""
    time.sleep(random.uniform(_MIN_DELAY_SEC, _MAX_DELAY_SEC))
