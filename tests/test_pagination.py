"""Unit tests for scraper.pagination.page_url."""

from __future__ import annotations

import pytest

from scraper.pagination import page_url


@pytest.mark.parametrize(
    "base,page,expected",
    [
        # Page 1 returns the base URL unchanged (canonical).
        ("https://example.com/list", 1, "https://example.com/list"),
        ("https://example.com/list/", 1, "https://example.com/list/"),
        # Page 2+ appends ?page=N.
        ("https://example.com/list", 2, "https://example.com/list?page=2"),
        ("https://example.com/list/", 3, "https://example.com/list/?page=3"),
    ],
)
def test_page_url_basic(base, page, expected):
    assert page_url(base, page) == expected


def test_page_url_preserves_existing_query():
    url = page_url("https://example.com/list?city=kyiv&rooms=1", 2)
    assert "city=kyiv" in url
    assert "rooms=1" in url
    assert "page=2" in url


def test_page_url_replaces_existing_page_param():
    url = page_url("https://example.com/list?page=5", 7)
    assert url.count("page=") == 1
    assert "page=7" in url
