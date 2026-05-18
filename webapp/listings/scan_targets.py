"""City → source-URL mapping for the manual "Просканувати зараз" button.

OLX and Dom.ria use mixed transliteration in their catalog URLs (`lvov`
Russian + `khmelnytskyi` Ukrainian on the same site), so the slugs are
empirical — verified one-shot by curling each URL during the initial
write of this map. If either source rebrands a slug, fix the entry here.

A source may be **missing** from a row when that source has no catalog
for that city (e.g. Dom.ria doesn't list Маріуполь or Біла Церква). In
that case `build_scrape_targets` returns only the available source(s).

Canonical name keys match `GazetteerLocation.name` (Ukrainian, with
diacritics and hyphens) so the resolver's output plugs in directly.
"""

from __future__ import annotations

CITY_SLUGS: dict[str, dict[str, str]] = {
    # 24 oblast centres (verified 200 on both sources unless noted).
    "Київ": {"olx": "kiev", "domria": "kiev"},
    "Львів": {"olx": "lvov", "domria": "lvov"},
    "Харків": {"olx": "kharkov", "domria": "harkov"},
    "Одеса": {"olx": "odessa", "domria": "odessa"},
    "Дніпро": {"olx": "dnepr", "domria": "dnepr"},
    "Запоріжжя": {"olx": "zaporozhe", "domria": "zaporozhye"},  # different on each
    "Вінниця": {"olx": "vinnitsa", "domria": "vinnitsa"},
    "Хмельницький": {"olx": "hmelnitskiy", "domria": "khmelnytskyi"},  # different
    "Чернігів": {"olx": "chernigov", "domria": "chernigov"},
    "Полтава": {"olx": "poltava", "domria": "poltava"},
    "Черкаси": {"olx": "cherkassy", "domria": "cherkassy"},
    "Житомир": {"olx": "zhitomir", "domria": "zhitomir"},
    "Суми": {"olx": "sumy", "domria": "sumy"},
    "Рівне": {"olx": "rovno", "domria": "rovno"},
    "Івано-Франківськ": {"olx": "ivano-frankovsk", "domria": "ivano-frankovsk"},
    "Тернопіль": {"olx": "ternopol", "domria": "ternopol"},
    "Луцьк": {"olx": "lutsk", "domria": "lutsk"},
    "Ужгород": {"olx": "uzhgorod", "domria": "uzhgorod"},
    "Чернівці": {"olx": "chernovtsy", "domria": "chernovtsy"},
    "Миколаїв": {"olx": "nikolaev", "domria": "nikolaev"},
    "Херсон": {"olx": "kherson", "domria": "kherson"},
    "Кропивницький": {"olx": "kropivnitskiy", "domria": "kropivnitskyi"},  # different
    # Kyiv-region satellites
    "Бровари": {"olx": "brovary", "domria": "brovary"},
    # Larger non-oblast-centre cities that come up in user queries.
    "Кременчук": {"olx": "kremenchug", "domria": "kremenchug"},
    "Краматорськ": {"olx": "kramatorsk", "domria": "kramatorsk"},
    # OLX-only — Dom.ria has no catalog for these.
    "Маріуполь": {"olx": "mariupol"},
    "Ірпінь": {"olx": "irpen"},
    "Біла Церква": {"olx": "belaya-tserkov"},
    "Коломия": {"olx": "kolomyya"},
}


# URL templates — match what Beat schedule uses in config/settings.py.
_OLX_RENT = "https://www.olx.ua/uk/nedvizhimost/kvartiry/dolgosrochnaya-arenda-kvartir/{slug}/"
_OLX_SALE = "https://www.olx.ua/uk/nedvizhimost/kvartiry/prodazha-kvartir/{slug}/"
_DOMRIA_RENT = "https://dom.ria.com/uk/arenda-kvartir/{slug}/"
_DOMRIA_SALE = "https://dom.ria.com/uk/prodazha-kvartir/{slug}/"


def build_scrape_targets(
    city_name: str,
    *,
    operation: str | None = None,
) -> list[tuple[str, str]]:
    """Return [(source, url), …] for the manual-scan trigger.

    - `city_name` must be the canonical form (from `resolve_location`).
    - `operation` filters to "sale" or "rent"; None returns both.
    - Up to 4 targets returned (2 per source × 2 operations); fewer if the
      city doesn't have a Dom.ria catalog, or if filtered by operation.
    - Returns `[]` if the city isn't in `CITY_SLUGS` — caller should show
      a "not supported" message rather than fire nothing.
    """
    slugs = CITY_SLUGS.get(city_name)
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


def supported_cities() -> list[str]:
    """Sorted list of canonical names supported for manual scan."""
    return sorted(CITY_SLUGS)
