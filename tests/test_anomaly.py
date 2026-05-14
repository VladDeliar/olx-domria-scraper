"""Anomaly detection: price outlier, parse drop, high error rate."""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


def _make_listing(price, *, source_id, source="olx", city="Київ", currency="UAH"):
    from listings.models import Listing

    return Listing.objects.create(
        source=source,
        source_id=str(source_id),
        url=f"https://example.com/{source_id}",
        title=f"test {source_id}",
        price_value=Decimal(price),
        price_currency=currency,
        city=city,
    )


def test_price_outlier_fires_when_listing_is_50x_peers():
    """Target = 5M with peers ~50k: ratio 100x, within the ±100x cohort band."""
    from listings.anomaly import check_listing
    from listings.models import ScrapeAlert

    for i in range(15):
        _make_listing(50_000 + i * 1_000, source_id=f"peer{i}")

    target = _make_listing(5_000_000, source_id="big")
    alert = check_listing(target)
    assert alert is not None
    assert alert.category == ScrapeAlert.Category.PRICE_OUTLIER
    assert alert.context["direction"] == "high"
    assert alert.context["peer_sample_size"] >= 10


def test_price_outlier_silent_when_too_few_peers():
    """Below MIN_PEERS (10) we have no reliable baseline — don't alert."""
    from listings.anomaly import check_listing

    for i in range(5):
        _make_listing(50_000, source_id=f"peer{i}")
    target = _make_listing(5_000_000, source_id="solo")
    assert check_listing(target) is None


def test_high_error_rate_alert():
    from listings.anomaly import check_run
    from listings.models import ScrapeAlert, ScrapeRun

    run = ScrapeRun.objects.create(
        source="olx",
        url="https://x/",
        scraped_count=8,
        error_count=4,  # 4/12 = 33% > 20%
        status=ScrapeRun.Status.SUCCESS,
    )
    alerts = list(check_run(run))
    cats = {a.category for a in alerts}
    assert ScrapeAlert.Category.HIGH_ERROR_RATE in cats


def test_parse_drop_alert_vs_previous_run():
    from listings.anomaly import check_run
    from listings.models import ScrapeAlert, ScrapeRun

    ScrapeRun.objects.create(
        source="olx",
        url="https://x/",
        pages_requested=2,
        scraped_count=60,
        status=ScrapeRun.Status.SUCCESS,
    )
    current = ScrapeRun.objects.create(
        source="olx",
        url="https://x/",
        pages_requested=2,
        scraped_count=10,  # 10 < 0.5 * 60
        status=ScrapeRun.Status.SUCCESS,
    )
    alerts = list(check_run(current))
    cats = {a.category for a in alerts}
    assert ScrapeAlert.Category.PARSE_DROP in cats


def test_empty_page_alert():
    from listings.anomaly import check_run
    from listings.models import ScrapeAlert, ScrapeRun

    run = ScrapeRun.objects.create(
        source="olx",
        url="https://x/",
        pages_requested=1,
        scraped_count=0,
        error_count=0,
        status=ScrapeRun.Status.SUCCESS,
    )
    alerts = list(check_run(run))
    cats = {a.category for a in alerts}
    assert ScrapeAlert.Category.EMPTY_PAGE in cats
