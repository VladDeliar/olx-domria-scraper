"""listing_extras template filters."""

from __future__ import annotations

from decimal import Decimal

import pytest
from listings.templatetags.listing_extras import thousands

_NBSP = " "


@pytest.mark.parametrize(
    "value,expected",
    [
        (2561487, f"2{_NBSP}561{_NBSP}487"),
        (Decimal("2561487.00"), f"2{_NBSP}561{_NBSP}487"),
        (15000, f"15{_NBSP}000"),
        (999, "999"),
        (0, "0"),
        (None, "—"),
        ("", "—"),
        ("not-a-number", "not-a-number"),  # defensive passthrough
    ],
)
def test_thousands(value, expected):
    assert thousands(value) == expected
