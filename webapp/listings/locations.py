"""Forgiving location matching.

Three public functions:
- `normalize_location(text)`: strip whitespace / dashes / apostrophes / dots /
  commas, lowercase. "Івано-Франківськ", "Івано Франківськ", "ІваноФранківськ"
  → "іванофранківськ".
- `resolve_location(user_input, cutoff=0.7)`: if `user_input` normalises to
  a known city/district (exact or fuzzy via difflib), return the canonical
  original-case name; otherwise None. Used by the HTML/API filter and the bot.
- `suggest_locations(user_input, n=3, cutoff=0.5)`: top-N close matches for
  "did you mean X?" prompts in the bot when resolve fails.

Known-name list is a deduplicated `(city ∪ district)` projection of `Listing`,
cached for 5 minutes via Django's default cache. difflib.SequenceMatcher is
plenty fast at our scale (≤200 distinct names).
"""

from __future__ import annotations

import re
from difflib import get_close_matches

from django.core.cache import cache

_NORMALISE_RE = re.compile(r"[\s\-'’`.,]+")

_CACHE_KEY = "locations:known_names:v1"
_CACHE_TTL = 300  # 5 minutes


def normalize_location(text: str | None) -> str:
    """Lowercase + strip whitespace/dashes/apostrophes/dots/commas."""
    if not text:
        return ""
    return _NORMALISE_RE.sub("", text).lower()


def get_known_locations() -> list[str]:
    """Distinct city ∪ district values that appear at least once. Cached."""
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached
    # Local import to avoid circular dependency at app-loading time.
    from listings.models import Listing

    cities = set(Listing.objects.exclude(city="").values_list("city", flat=True).distinct())
    districts = set(
        Listing.objects.exclude(district="").values_list("district", flat=True).distinct()
    )
    names = sorted(cities | districts)
    cache.set(_CACHE_KEY, names, _CACHE_TTL)
    return names


def _normalised_map(known: list[str]) -> dict[str, str]:
    return {normalize_location(name): name for name in known}


def resolve_location(user_input: str, cutoff: float = 0.7) -> str | None:
    """Return the canonical name (original case + diacritics) or None."""
    target = normalize_location(user_input)
    if not target:
        return None
    mapping = _normalised_map(get_known_locations())
    if target in mapping:
        return mapping[target]
    matches = get_close_matches(target, list(mapping), n=1, cutoff=cutoff)
    return mapping[matches[0]] if matches else None


def suggest_locations(user_input: str, n: int = 3, cutoff: float = 0.5) -> list[str]:
    """Top-N close matches for 'did you mean X?' UX."""
    target = normalize_location(user_input)
    if not target:
        return []
    mapping = _normalised_map(get_known_locations())
    matches = get_close_matches(target, list(mapping), n=n, cutoff=cutoff)
    return [mapping[m] for m in matches]


def invalidate_known_locations_cache() -> None:
    """Hook for tests / batch imports to clear the 5-min cache immediately."""
    cache.delete(_CACHE_KEY)
