"""Template filters for the listings app."""

from __future__ import annotations

from django import template

register = template.Library()

# Non-breaking space — keeps a price like "2 561 487" from wrapping mid-number.
_NBSP = " "


@register.filter
def thousands(value: object) -> str:
    """Format a number with NBSP thousands separators.

    2561487 → "2 561 487". `None`/"" → "—". Non-numeric input is returned
    unchanged (defensive — a template filter should never raise).
    """
    if value is None or value == "":
        return "—"
    try:
        n = round(float(value))
    except (TypeError, ValueError):
        return str(value)
    return f"{n:,}".replace(",", _NBSP)
