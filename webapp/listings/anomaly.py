"""Anomaly detection for scraping pipeline.

Two kinds of checks:
- Per-listing: called right after a Listing is upserted. Currently flags
  price outliers vs. a recent peer baseline (same source + city + currency).
- Per-run: called when a ScrapeRun finishes. Flags high error rate, sudden
  drop in scraped count vs. previous run for the same source, and empty
  pages despite a non-zero pages_fetched.

Each check that fires creates a `ScrapeAlert` row — never raises. The point
is observability, not blocking the pipeline.
"""

from __future__ import annotations

import logging
import statistics
from collections.abc import Iterable
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from listings.models import Listing, ScrapeAlert, ScrapeRun

logger = logging.getLogger(__name__)

# Tunables. Conservative — false-positive cost is low (one alert row), but
# false-negative cost is silently missing data quality regressions.
_PRICE_OUTLIER_MULTIPLIER = 10.0
_PRICE_OUTLIER_MIN_PEERS = 10
_PRICE_OUTLIER_LOOKBACK_DAYS = 30
_HIGH_ERROR_RATE_THRESHOLD = 0.20  # >20% of attempts failed
_HIGH_ERROR_RATE_MIN_SAMPLE = 10
_PARSE_DROP_RATIO = 0.5  # current < 50% of previous run's count for same source
_PARSE_DROP_MIN_PREV = 20


def check_listing(listing: Listing) -> ScrapeAlert | None:
    """Flag price outliers vs. a *price-magnitude-bounded* peer cohort.

    Cohort: same source/city/currency, last 30d. To survive bi-modal data
    (e.g. OLX catalogs that mix sale + rent in one URL), we restrict the
    cohort to peers within ±100× of the candidate's price — i.e. listings
    of the same rough order of magnitude. This keeps "rent" comparable to
    "rent" without needing an explicit operation_type field on the model.
    Median + IQR-style bounds are used in place of mean to be robust to
    remaining skew.
    """
    if listing.price_value is None or not listing.price_currency:
        return None

    since = timezone.now() - timedelta(days=_PRICE_OUTLIER_LOOKBACK_DAYS)
    price = Decimal(listing.price_value)
    band_low = price / Decimal(100)
    band_high = price * Decimal(100)

    prices = list(
        Listing.objects.filter(
            source=listing.source,
            city=listing.city,
            price_currency=listing.price_currency,
            price_value__gte=band_low,
            price_value__lte=band_high,
            last_seen_at__gte=since,
        )
        .exclude(pk=listing.pk)
        .values_list("price_value", flat=True)
    )
    sample_size = len(prices)
    if sample_size < _PRICE_OUTLIER_MIN_PEERS:
        return None

    median = Decimal(statistics.median(prices))
    if median <= 0:
        return None
    ratio = price / median

    high = ratio >= Decimal(_PRICE_OUTLIER_MULTIPLIER)
    low = ratio <= Decimal(1) / Decimal(_PRICE_OUTLIER_MULTIPLIER)
    if not (high or low):
        return None

    return ScrapeAlert.objects.create(
        severity=ScrapeAlert.Severity.WARN,
        category=ScrapeAlert.Category.PRICE_OUTLIER,
        message=(
            f"{listing.source}#{listing.source_id} price {price:.0f} "
            f"{listing.price_currency} is {float(ratio):.1f}× the {sample_size}-peer "
            f"median ({float(median):.0f}) in {listing.city or '?'}"
        ),
        context={
            "price": str(price),
            "currency": listing.price_currency,
            "peer_median": str(median),
            "peer_sample_size": sample_size,
            "ratio": float(ratio),
            "city": listing.city,
            "direction": "high" if high else "low",
        },
        listing=listing,
    )


def check_run(run: ScrapeRun) -> Iterable[ScrapeAlert]:
    """Flag run-level anomalies. Returns the alerts created (for callers' logs)."""
    alerts: list[ScrapeAlert] = []

    attempted = run.scraped_count + run.error_count
    if (
        attempted >= _HIGH_ERROR_RATE_MIN_SAMPLE
        and run.error_count / attempted >= _HIGH_ERROR_RATE_THRESHOLD
    ):
        alerts.append(
            ScrapeAlert.objects.create(
                severity=ScrapeAlert.Severity.ERROR,
                category=ScrapeAlert.Category.HIGH_ERROR_RATE,
                message=(
                    f"{run.source}: {run.error_count}/{attempted} listings failed "
                    f"({run.error_count / attempted:.0%})"
                ),
                context={
                    "errors": run.error_count,
                    "attempted": attempted,
                    "rate": run.error_count / attempted,
                },
                run=run,
            )
        )

    if run.pages_requested >= 1 and run.scraped_count == 0:
        alerts.append(
            ScrapeAlert.objects.create(
                severity=ScrapeAlert.Severity.WARN,
                category=ScrapeAlert.Category.EMPTY_PAGE,
                message=f"{run.source}: 0 listings parsed from {run.url}",
                context={"url": run.url, "pages_requested": run.pages_requested},
                run=run,
            )
        )

    previous = (
        ScrapeRun.objects.filter(
            source=run.source,
            status=ScrapeRun.Status.SUCCESS,
            pages_requested=run.pages_requested,
        )
        .exclude(pk=run.pk)
        .order_by("-started_at")
        .first()
    )
    if (
        previous
        and previous.scraped_count >= _PARSE_DROP_MIN_PREV
        and run.scraped_count < _PARSE_DROP_RATIO * previous.scraped_count
    ):
        alerts.append(
            ScrapeAlert.objects.create(
                severity=ScrapeAlert.Severity.WARN,
                category=ScrapeAlert.Category.PARSE_DROP,
                message=(
                    f"{run.source}: scraped {run.scraped_count}, previous run "
                    f"#{previous.id} got {previous.scraped_count}"
                ),
                context={
                    "current": run.scraped_count,
                    "previous": previous.scraped_count,
                    "previous_run_id": previous.id,
                    "drop_ratio": (
                        run.scraped_count / previous.scraped_count
                        if previous.scraped_count
                        else None
                    ),
                },
                run=run,
            )
        )

    return alerts
