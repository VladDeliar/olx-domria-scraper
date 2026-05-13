"""/start and /help — onboarding."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from asgiref.sync import sync_to_async

from listings.models import TelegramUser

router = Router(name="start")


_WELCOME = (
    "👋 <b>RealEstate Radar</b>\n\n"
    "Я надсилатиму нові оголошення з OLX та Dom.ria за твоїми критеріями.\n\n"
    "Команди:\n"
    "/subscribe — створити підписку (район, ціна, кімнати)\n"
    "/list — переглянути активні підписки\n"
    "/clear — видалити всі підписки\n"
    "/help — довідка"
)


@sync_to_async
def _ensure_user(tg_id: int, username: str, first_name: str) -> None:
    TelegramUser.objects.update_or_create(
        tg_user_id=tg_id,
        defaults={"username": username or "", "first_name": first_name or "", "is_active": True},
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    await _ensure_user(user.id, user.username or "", user.first_name or "")
    await message.answer(_WELCOME)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(_WELCOME)
