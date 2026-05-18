"""Location → source-URL mapping for the manual "Просканувати зараз" button.

Two kinds of entries:
- `kind="city"` — direct city/town catalog (~30 places).
- `kind="oblast"` — oblast-wide catalog (24 entries). Used as fallback when
  the user types a village name: walk up the gazetteer parent chain to the
  oblast and scan everything in it.

OLX and Dom.ria use different slug schemes that change over time:
- OLX recently switched oblast pages to **3-letter codes** (`ter`, `if`, `lv`,
  `dnp`, …) instead of long transliterations. Cities still use the long
  form (`kiev`, `lvov`).
- Dom.ria uses `obl-<ru-translit>skaya` for oblasts, and a mix of Russian and
  Ukrainian transliteration for cities (`khmelnytskyi` Ukrainian, `lvov`
  Russian).

Slugs verified during the initial write with `curl -I -L --max-time 6` for
both sources. If either source rebrands a slug in the future, fix the entry
here — that's the entire maintenance surface.

Canonical keys match `GazetteerLocation.name` (the ADM1_UA / ADM4_UA Ukrainian
form), so the resolver's output plugs in directly.
"""

from __future__ import annotations

CITY_OLX_ONLY: dict[str, str] = {
    # Cities where Dom.ria has no catalog page (Donbas active war zone,
    # Kyiv-region satellites without Dom.ria coverage).
    "Маріуполь": "mariupol",
    "Ірпінь": "irpen",
    "Біла Церква": "belaya-tserkov",
    "Коломия": "kolomyya",
}


LOCATION_SLUGS: dict[str, dict[str, str]] = {
    # --- 24 oblast centres (city kind, both sources) -------------------------
    "Київ": {"olx": "kiev", "domria": "kiev", "kind": "city"},
    "Львів": {"olx": "lvov", "domria": "lvov", "kind": "city"},
    "Харків": {"olx": "kharkov", "domria": "harkov", "kind": "city"},
    "Одеса": {"olx": "odessa", "domria": "odessa", "kind": "city"},
    "Дніпро": {"olx": "dnepr", "domria": "dnepr", "kind": "city"},
    "Запоріжжя": {"olx": "zaporozhe", "domria": "zaporozhye", "kind": "city"},
    "Вінниця": {"olx": "vinnitsa", "domria": "vinnitsa", "kind": "city"},
    "Хмельницький": {"olx": "hmelnitskiy", "domria": "khmelnytskyi", "kind": "city"},
    "Чернігів": {"olx": "chernigov", "domria": "chernigov", "kind": "city"},
    "Полтава": {"olx": "poltava", "domria": "poltava", "kind": "city"},
    "Черкаси": {"olx": "cherkassy", "domria": "cherkassy", "kind": "city"},
    "Житомир": {"olx": "zhitomir", "domria": "zhitomir", "kind": "city"},
    "Суми": {"olx": "sumy", "domria": "sumy", "kind": "city"},
    "Рівне": {"olx": "rovno", "domria": "rovno", "kind": "city"},
    "Івано-Франківськ": {"olx": "ivano-frankovsk", "domria": "ivano-frankovsk", "kind": "city"},
    "Тернопіль": {"olx": "ternopol", "domria": "ternopol", "kind": "city"},
    "Луцьк": {"olx": "lutsk", "domria": "lutsk", "kind": "city"},
    "Ужгород": {"olx": "uzhgorod", "domria": "uzhgorod", "kind": "city"},
    "Чернівці": {"olx": "chernovtsy", "domria": "chernovtsy", "kind": "city"},
    "Миколаїв": {"olx": "nikolaev", "domria": "nikolaev", "kind": "city"},
    "Херсон": {"olx": "kherson", "domria": "kherson", "kind": "city"},
    "Кропивницький": {"olx": "kropivnitskiy", "domria": "kropivnitskyi", "kind": "city"},
    # --- Kyiv-region + non-oblast-centre cities (city kind) ------------------
    "Бровари": {"olx": "brovary", "domria": "brovary", "kind": "city"},
    "Кременчук": {"olx": "kremenchug", "domria": "kremenchug", "kind": "city"},
    "Краматорськ": {"olx": "kramatorsk", "domria": "kramatorsk", "kind": "city"},
    # --- 24 oblasts (fallback for villages/raions inside them) ---------------
    # Key matches the bare ADM1_UA name (no "область" suffix).
    "Вінницька": {"olx": "vin", "domria": "obl-vinnitskaya", "kind": "oblast"},
    "Волинська": {"olx": "vol", "domria": "obl-volynskaya", "kind": "oblast"},
    "Дніпропетровська": {"olx": "dnp", "domria": "obl-dnepropetrovskaya", "kind": "oblast"},
    "Донецька": {"olx": "don", "domria": "obl-donetskaya", "kind": "oblast"},
    "Житомирська": {"olx": "zht", "domria": "obl-zhitomirskaya", "kind": "oblast"},
    "Закарпатська": {"olx": "zak", "domria": "obl-zakarpatskaya", "kind": "oblast"},
    "Запорізька": {"olx": "zap", "domria": "obl-zaporozhskaya", "kind": "oblast"},
    "Івано-Франківська": {"olx": "if", "domria": "obl-ivano-frankovskaya", "kind": "oblast"},
    "Київська": {"olx": "ko", "domria": "obl-kievskaya", "kind": "oblast"},
    "Кіровоградська": {"olx": "kir", "domria": "obl-kirovogradskaya", "kind": "oblast"},
    "Луганська": {"olx": "lug", "domria": "obl-luganskaya", "kind": "oblast"},
    "Львівська": {"olx": "lv", "domria": "obl-lvovskaya", "kind": "oblast"},
    "Миколаївська": {"olx": "nik", "domria": "obl-nikolaevskaya", "kind": "oblast"},
    "Одеська": {"olx": "od", "domria": "obl-odesskaya", "kind": "oblast"},
    "Полтавська": {"olx": "pol", "domria": "obl-poltavskaya", "kind": "oblast"},
    "Рівненська": {"olx": "rov", "domria": "obl-rovenskaya", "kind": "oblast"},
    "Сумська": {"olx": "sum", "domria": "obl-sumskaya", "kind": "oblast"},
    "Тернопільська": {"olx": "ter", "domria": "obl-ternopolskaya", "kind": "oblast"},
    "Харківська": {"olx": "kha", "domria": "obl-kharkovskaya", "kind": "oblast"},
    "Херсонська": {"olx": "khe", "domria": "obl-khersonskaya", "kind": "oblast"},
    "Хмельницька": {"olx": "khm", "domria": "obl-khmelnytskaya", "kind": "oblast"},
    "Черкаська": {"olx": "chk", "domria": "obl-cherkasskaya", "kind": "oblast"},
    "Чернівецька": {"olx": "chv", "domria": "obl-chernovytskaya", "kind": "oblast"},
    "Чернігівська": {"olx": "chn", "domria": "obl-chernigovskaya", "kind": "oblast"},
}

# Splice OLX-only cities (no Dom.ria pair) into LOCATION_SLUGS so the
# dispatcher treats them uniformly.
for _name, _olx_slug in CITY_OLX_ONLY.items():
    LOCATION_SLUGS[_name] = {"olx": _olx_slug, "kind": "city"}


# URL templates — match what Beat schedule uses in config/settings.py.
_OLX_RENT = "https://www.olx.ua/uk/nedvizhimost/kvartiry/dolgosrochnaya-arenda-kvartir/{slug}/"
_OLX_SALE = "https://www.olx.ua/uk/nedvizhimost/kvartiry/prodazha-kvartir/{slug}/"
_DOMRIA_RENT = "https://dom.ria.com/uk/arenda-kvartir/{slug}/"
_DOMRIA_SALE = "https://dom.ria.com/uk/prodazha-kvartir/{slug}/"


def build_scrape_targets(
    name: str,
    *,
    operation: str | None = None,
) -> list[tuple[str, str]]:
    """Return [(source, url), …] for `name`'s LOCATION_SLUGS entry.

    Up to 4 targets (OLX rent/sale + Dom.ria rent/sale); fewer if either
    source is absent or `operation` filters down. `[]` if `name` isn't in
    LOCATION_SLUGS — caller is expected to walk gazetteer parents via
    `find_scan_strategy` before giving up.
    """
    slugs = LOCATION_SLUGS.get(name)
    if not slugs:
        return []

    targets: list[tuple[str, str]] = []
    olx_slug = slugs.get("olx")
    domria_slug = slugs.get("domria")

    if operation in (None, "rent"):
        if olx_slug:
            targets.append(("olx", _OLX_RENT.format(slug=olx_slug)))
        if domria_slug:
            targets.append(("domria", _DOMRIA_RENT.format(slug=domria_slug)))
    if operation in (None, "sale"):
        if olx_slug:
            targets.append(("olx", _OLX_SALE.format(slug=olx_slug)))
        if domria_slug:
            targets.append(("domria", _DOMRIA_SALE.format(slug=domria_slug)))
    return targets


def find_scan_strategy(
    canonical_name: str,
    *,
    operation: str | None = None,
) -> tuple[str, str, list[tuple[str, str]]]:
    """Pick the right scan tier for `canonical_name` (output of resolve_location).

    Returns `(kind, scan_key, targets)`:
    - `kind` ∈ {"city", "oblast", "unsupported"}.
    - `scan_key` is the LOCATION_SLUGS key actually scanned (may differ from
      the input — e.g. "Підгайчики" → scan_key="Тернопільська").
    - `targets` is the same list `build_scrape_targets` would return; empty
      when `kind == "unsupported"`.

    Strategy:
    1. Direct hit in LOCATION_SLUGS → use it (city or oblast).
    2. Otherwise look the name up in GazetteerLocation; if the row has a
       parent_path, take the first segment (oblast) and try that.
    3. Else → unsupported.
    """
    if canonical_name in LOCATION_SLUGS:
        kind = LOCATION_SLUGS[canonical_name].get("kind", "city")
        return kind, canonical_name, build_scrape_targets(canonical_name, operation=operation)

    # Local import keeps this module importable from non-Django contexts
    # (e.g. unit tests for the URL builder alone).
    from listings.models import GazetteerLocation

    row = (
        GazetteerLocation.objects.filter(name__iexact=canonical_name)
        .exclude(parent_path="")
        .first()
    )
    if row is None:
        return "unsupported", "", []

    oblast = row.parent_path.split(" > ", 1)[0].strip()
    if oblast in LOCATION_SLUGS and LOCATION_SLUGS[oblast].get("kind") == "oblast":
        return "oblast", oblast, build_scrape_targets(oblast, operation=operation)
    return "unsupported", "", []


def supported_cities() -> list[str]:
    """Sorted city-tier names (oblasts excluded — they're a fallback, not a
    user-facing 'supported city' list)."""
    return sorted(name for name, s in LOCATION_SLUGS.items() if s.get("kind") == "city")
