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
from django.conf import settings

from bot.formatting import render_listing
from listings.models import Listing, Notification, Subscription

logger = logging.getLogger(__name__)


def _matches(listing: Listing, sub: Subscription) -> bool:
    if sub.source and listing.source != sub.source:
        return False
    if sub.city and listing.city.lower() != sub.city.lower():
        return False
    if sub.district and listing.district.lower() != sub.district.lower():
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
        if not rooms_param or not isinstance(rooms_param.normalized_value, (int, float)):
            return False
        rooms = int(rooms_param.normalized_value)
        if sub.min_rooms is not None and rooms < sub.min_rooms:
            return False
        if sub.max_rooms is not None and rooms > sub.max_rooms:
            return False
    return True


def _candidate_subscriptions(listing: Listing) -> list[Subscription]:
    """All active subscriptions, minus ones already notified for this listing."""
    return list(
        Subscription.objects.filter(is_active=True, user__is_active=True)
        .exclude(user__notifications__listing=listing)
        .select_related("user")
    )


async def _send(bot: Bot, chat_id: int, text: str) -> bool:
    try:
        await bot.send_message(chat_id, text, disable_web_page_preview=False)
        return True
    except TelegramAPIError as exc:
        logger.warning("send_message failed for chat %s: %s", chat_id, exc)
        return False


async def _notify_async(listing: Listing) -> int:
    subs = _candidate_subscriptions(listing)
    if not subs:
        return 0
    matched = [s for s in subs if _matches(listing, s)]
    if not matched:
        return 0
    text = render_listing(listing)
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    sent = 0
    try:
        for sub in matched:
            ok = await _send(bot, sub.user.tg_user_id, text)
            if ok:
                Notification.objects.create(user=sub.user, listing=listing)
                sent += 1
    finally:
        await bot.session.close()
    return sent


def notify_new_listing(listing: Listing) -> int:
    """Sync entry point — returns count of notifications sent."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return 0
    return asyncio.run(_notify_async(listing))
