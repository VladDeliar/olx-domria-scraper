"""Match a freshly-scraped listing to user subscriptions and push Telegram messages.

Designed to be called from sync code (the `scrape` management command) for one
listing at a time. Internally spins up an aiogram Bot, sends, and closes it.
For our scrape volumes this is cheaper than maintaining a long-lived bot
process just for outbound messages.
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from asgiref.sync import sync_to_async
from django.conf import settings
from listings.locations import normalize_location
from listings.models import Listing, Notification, Subscription

from bot.formatting import render_listing

logger = logging.getLogger(__name__)


def _matches(listing: Listing, sub: Subscription) -> bool:
    if sub.source and listing.source != sub.source:
        return False
    if sub.city and listing.city.lower() != sub.city.lower():
        return False
    if sub.district:
        # location_search holds normalize_location(city + district + region) —
        # one icontains lookup covers all three with whitespace/dash variants.
        want = normalize_location(sub.district)
        if want and want not in listing.location_search:
            return False
    if sub.min_price is not None or sub.max_price is not None:
        if listing.price_value is None:
            return False
        if sub.currency and listing.price_currency != sub.currency:
            return False
        if sub.min_price is not None and listing.price_value < Decimal(sub.min_price):
            return False
        if sub.max_price is not None and listing.price_value > Decimal(sub.max_price):
            return False
    if sub.min_rooms is not None or sub.max_rooms is not None:
        rooms_param = listing.params.filter(key="number_of_rooms_string").first()
        if not rooms_param:
            return False
        rooms = _coerce_rooms(rooms_param.normalized_value)
        if rooms is None:
            return False
        if sub.min_rooms is not None and rooms < sub.min_rooms:
            return False
        if sub.max_rooms is not None and rooms > sub.max_rooms:
            return False
    return True


# OLX historically stored rooms as category slugs (`'odnokomnatnye'` …) in
# normalized_value before we added a coercion step in the parser. Listings
# scraped pre-fix may still have the string form, so the matcher accepts both.
_ROOMS_SLUG_FALLBACK: dict[str, int] = {
    "odnokomnatnye": 1,
    "dvuhkomnatnye": 2,
    "trehkomnatnye": 3,
    "chetyrehkomnatnye": 4,
    "pyatikomnatnye": 5,
    "shestikomnatnye": 6,
}


def _coerce_rooms(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        if value.isdigit():
            return int(value)
        return _ROOMS_SLUG_FALLBACK.get(value)
    return None


def _gather_targets(listing: Listing) -> list[tuple[int, str, int, int]]:
    """Sync: find subscriptions to notify. Returns list of (sub_id, text, user_pk, tg_user_id).

    Doing all ORM work here (sync) lets the async caller wrap one call with
    sync_to_async instead of N — and keeps `_matches` ORM access trivial.
    """
    subs = list(
        Subscription.objects.filter(is_active=True, user__is_active=True)
        .exclude(user__notifications__listing=listing)
        .select_related("user")
    )
    matched = [s for s in subs if _matches(listing, s)]
    if not matched:
        return []
    text = render_listing(listing)
    return [(s.id, text, s.user.pk, s.user.tg_user_id) for s in matched]


def _record_notification(user_pk: int, listing_pk: int) -> None:
    Notification.objects.create(user_id=user_pk, listing_id=listing_pk)


async def _send(bot: Bot, chat_id: int, text: str) -> bool:
    try:
        await bot.send_message(chat_id, text, disable_web_page_preview=False)
        return True
    except TelegramAPIError as exc:
        logger.warning("send_message failed for chat %s: %s", chat_id, exc)
        return False


async def _notify_async(listing: Listing) -> int:
    targets = await sync_to_async(_gather_targets, thread_sensitive=True)(listing)
    if not targets:
        return 0
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    sent = 0
    try:
        for _sub_id, text, user_pk, tg_user_id in targets:
            if await _send(bot, tg_user_id, text):
                await sync_to_async(_record_notification, thread_sensitive=True)(
                    user_pk, listing.pk
                )
                sent += 1
    finally:
        await bot.session.close()
    return sent


def notify_new_listing(listing: Listing) -> int:
    """Sync entry point — returns count of notifications sent."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return 0
    return asyncio.run(_notify_async(listing))
