"""/list and /clear — manage existing subscriptions."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from asgiref.sync import sync_to_async
from listings.models import Subscription

router = Router(name="manage")


@sync_to_async
def _list_subs(tg_user_id: int) -> list[str]:
    return [
        f"#{s.id} — {s}"
        for s in Subscription.objects.filter(user__tg_user_id=tg_user_id, is_active=True)
    ]


@sync_to_async
def _clear_subs(tg_user_id: int) -> int:
    return Subscription.objects.filter(user__tg_user_id=tg_user_id, is_active=True).update(
        is_active=False
    )


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    if message.from_user is None:
        return
    items = await _list_subs(message.from_user.id)
    if not items:
        await message.answer("У тебе ще немає підписок. /subscribe щоб створити.")
        return
    body = "\n".join(items)
    await message.answer(f"<b>Твої підписки:</b>\n{body}")


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    if message.from_user is None:
        return
    n = await _clear_subs(message.from_user.id)
    await message.answer(f"Деактивовано {n} підписок." if n else "Підписок не було.")
