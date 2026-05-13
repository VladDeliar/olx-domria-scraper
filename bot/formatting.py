"""Render a Listing as a Telegram message (HTML parse mode)."""

from __future__ import annotations

import html

from listings.models import Listing


def render_listing(listing: Listing) -> str:
    """Build an HTML-formatted Telegram message for a listing."""

    def esc(value: str | None) -> str:
        return html.escape(str(value)) if value else ""

    title = esc(listing.title)
    url = listing.url

    price = "—"
    if listing.price_is_free:
        price = "free"
    elif listing.price_value is not None:
        price = f"{listing.price_value:,.0f} {esc(listing.price_currency)}"

    location = " / ".join(p for p in (esc(listing.city), esc(listing.district)) if p)

    rooms_param = listing.params.filter(key="number_of_rooms_string").first()
    area_param = listing.params.filter(key="total_area").first()
    floor_param = listing.params.filter(key="floor").first()

    facts: list[str] = []
    if rooms_param:
        facts.append(f"🛏 {esc(rooms_param.value)}")
    if area_param:
        facts.append(f"📐 {esc(area_param.value)}")
    if floor_param:
        facts.append(f"🏢 {esc(floor_param.value)} пов.")

    source_tag = {"olx": "OLX", "domria": "Dom.ria"}.get(listing.source, listing.source)
    header = f"🆕 <b>{title}</b>"

    lines = [header, f"<b>{price}</b>" + (f" · {location}" if location else "")]
    if facts:
        lines.append(" · ".join(facts))
    lines.append(f'<a href="{url}">{source_tag} →</a>')
    return "\n".join(lines)
