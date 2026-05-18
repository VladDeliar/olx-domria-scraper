"""Forgiving location matching — two-tier resolver.

- Tier 1 (in-data): distinct `Listing.city ∪ district`. Small (~50–200 names).
  Powers the on-site `<datalist>` autocomplete — users see only places that
  actually have listings.
- Tier 2 (gazetteer): the full GazetteerLocation table loaded from HDX UNOCHA
  Ukraine admin boundaries (~30k rows). Used as the fallback when the user
  asks about a real Ukrainian place we haven't scraped yet.

Fuzzy match is rapidfuzz (C++) — 20-50× faster than stdlib difflib on the
~30k gazetteer scale. Cutoffs are on a 0–100 scale (rapidfuzz convention),
NOT 0–1 like difflib.

Three public functions:
- `normalize_location(text)`
- `resolve_location(user_input, cutoff=80)`
- `suggest_locations(user_input, n=3, cutoff=60)`
"""

from __future__ import annotations

import re

from django.core.cache import cache
from rapidfuzz import fuzz, process

_NORMALISE_RE = re.compile(r"[\s\-'’`.,]+")

_DATA_CACHE_KEY = "locations:in_data:v3"
_DATA_MAP_CACHE_KEY = "locations:in_data_map:v3"
_GAZETTEER_CACHE_KEY = "locations:gazetteer:v3"
_GAZETTEER_MAP_CACHE_KEY = "locations:gazetteer_map:v3"
_DATA_CACHE_TTL = 300  # 5 min — listings churn
_GAZETTEER_CACHE_TTL = 86_400  # 24 h — admin boundaries don't change


def normalize_location(text: str | None) -> str:
    """Lowercase + strip whitespace/dashes/apostrophes/dots/commas."""
    if not text:
        return ""
    return _NORMALISE_RE.sub("", text).lower()


def get_known_locations() -> list[str]:
    """Tier 1: distinct city ∪ district values from Listing. Cached 5 min."""
    cached = cache.get(_DATA_CACHE_KEY)
    if cached is not None:
        return cached
    from listings.models import Listing

    cities = set(Listing.objects.exclude(city="").values_list("city", flat=True).distinct())
    districts = set(
        Listing.objects.exclude(district="").values_list("district", flat=True).distinct()
    )
    names = sorted(cities | districts)
    cache.set(_DATA_CACHE_KEY, names, _DATA_CACHE_TTL)
    return names


def get_gazetteer_locations() -> list[str]:
    """Tier 2: all GazetteerLocation names. Cached 24 h (immutable reference data)."""
    cached = cache.get(_GAZETTEER_CACHE_KEY)
    if cached is not None:
        return cached
    from listings.models import GazetteerLocation

    names = sorted(set(GazetteerLocation.objects.values_list("name", flat=True).distinct()))
    cache.set(_GAZETTEER_CACHE_KEY, names, _GAZETTEER_CACHE_TTL)
    return names


def _get_in_data_map() -> dict[str, str]:
    cached = cache.get(_DATA_MAP_CACHE_KEY)
    if cached is not None:
        return cached
    mapping = {normalize_location(name): name for name in get_known_locations()}
    cache.set(_DATA_MAP_CACHE_KEY, mapping, _DATA_CACHE_TTL)
    return mapping


def _get_gazetteer_map() -> dict[str, str]:
    cached = cache.get(_GAZETTEER_MAP_CACHE_KEY)
    if cached is not None:
        return cached
    mapping = {normalize_location(name): name for name in get_gazetteer_locations()}
    cache.set(_GAZETTEER_MAP_CACHE_KEY, mapping, _GAZETTEER_CACHE_TTL)
    return mapping


def _best_match(target: str, candidates: dict[str, str], cutoff: float) -> str | None:
    """Use rapidfuzz to find the closest candidate; return original-case name."""
    if not candidates:
        return None
    if target in candidates:
        return candidates[target]
    match = process.extractOne(
        target,
        list(candidates),
        scorer=fuzz.ratio,
        score_cutoff=cutoff,
    )
    return candidates[match[0]] if match else None


def resolve_location(user_input: str, cutoff: float = 80) -> str | None:
    """Return canonical name (original case) or None.

    Tries the in-data tier first (high confidence), then falls back to the
    full gazetteer. `cutoff` is rapidfuzz 0–100 scale: 80 ≈ one missing
    letter is fine, 100 = exact match only.
    """
    target = normalize_location(user_input)
    if not target:
        return None

    hit = _best_match(target, _get_in_data_map(), cutoff)
    if hit:
        return hit
    return _best_match(target, _get_gazetteer_map(), cutoff)


def suggest_locations(user_input: str, n: int = 3, cutoff: float = 60) -> list[str]:
    """Top-N close matches across both tiers for 'did you mean X?' UX."""
    target = normalize_location(user_input)
    if not target:
        return []

    combined = {**_get_gazetteer_map(), **_get_in_data_map()}  # in-data wins on collisions
    if not combined:
        return []
    matches = process.extract(
        target,
        list(combined),
        scorer=fuzz.ratio,
        limit=n,
        score_cutoff=cutoff,
    )
    return [combined[m[0]] for m in matches]


def invalidate_known_locations_cache() -> None:
    """Clear both tiers (lists + pre-normalised maps)."""
    for key in (
        _DATA_CACHE_KEY,
        _DATA_MAP_CACHE_KEY,
        _GAZETTEER_CACHE_KEY,
        _GAZETTEER_MAP_CACHE_KEY,
    ):
        cache.delete(key)
