"""/subscribe — 3-state FSM dialog: district → max_price → rooms."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from asgiref.sync import sync_to_async
from listings.locations import resolve_location, suggest_locations
from listings.models import Subscription, TelegramUser

router = Router(name="subscribe")


class SubscribeStates(StatesGroup):
    district = State()
    confirm_location = State()
    max_price = State()
    rooms = State()


_SKIP_WORDS = {"-", "skip", "пропустити", "будь-який", "/skip"}


def _parse_skip(text: str) -> bool:
    return text.strip().lower() in _SKIP_WORDS


def _parse_rooms(text: str) -> tuple[int | None, int | None]:
    """Parse '1', '1-2', '-3', '2-' into (min, max). Returns (None, None) on garbage."""
    text = text.replace(" ", "").replace("к", "")
    if "-" in text:
        lo_s, hi_s = text.split("-", 1)
    else:
        lo_s = hi_s = text
    try:
        lo = int(lo_s) if lo_s else None
        hi = int(hi_s) if hi_s else None
    except ValueError:
        return None, None
    if lo and hi and lo > hi:
        lo, hi = hi, lo
    return lo, hi


@sync_to_async
def _save_subscription(tg_user_id: int, data: dict) -> Subscription:
    user, _ = TelegramUser.objects.get_or_create(tg_user_id=tg_user_id)
    sub = Subscription.objects.create(user=user, **data)
    return sub


@router.message(Command("subscribe"))
async def cmd_subscribe_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SubscribeStates.district)
    await message.answer(
        "1/3 🗺 Який район? Введи назву (напр. <i>Печерський</i>) або «-» щоб пропустити."
    )


async def _advance_to_price(message: Message, state: FSMContext) -> None:
    await state.set_state(SubscribeStates.max_price)
    await message.answer(
        "2/3 💵 Макс ціна? Формат: <code>30000 UAH</code> або <code>800 USD</code>. «-» щоб пропустити."
    )


@router.message(SubscribeStates.district, F.text)
async def step_district(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if _parse_skip(text):
        await state.update_data(district="")
        await _advance_to_price(message, state)
        return

    canonical = await sync_to_async(resolve_location, thread_sensitive=True)(text)
    if canonical:
        await state.update_data(district=canonical)
        if canonical.lower() != text.lower():
            await message.answer(f"📍 Знайшов: <b>{canonical}</b>")
        await _advance_to_price(message, state)
        return

    suggestions = await sync_to_async(suggest_locations, thread_sensitive=True)(text)
    if suggestions:
        await state.update_data(_pending_location=text, _suggestions=suggestions)
        await state.set_state(SubscribeStates.confirm_location)
        body = "\n".join(f"{i + 1}) {name}" for i, name in enumerate(suggestions))
        await message.answer(
            "Не знайшов точно. Можливо ти мав на увазі:\n"
            f"{body}\n\n"
            "Введи <b>номер</b>, точну назву ще раз, або «-» щоб без локації."
        )
        return

    # No match and no suggestions — keep raw text but warn.
    await state.update_data(district=text)
    await message.answer(
        f"⚠️ Локації «{text}» поки немає в базі. Підписку створю — як з'являться "
        "відповідні оголошення, отримаєш повідомлення."
    )
    await _advance_to_price(message, state)


@router.message(SubscribeStates.confirm_location, F.text)
async def step_confirm_location(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    data = await state.get_data()
    suggestions: list[str] = data.get("_suggestions") or []

    if _parse_skip(text):
        await state.update_data(district="")
        await _advance_to_price(message, state)
        return

    # Numeric pick?
    if text.isdigit() and 1 <= int(text) <= len(suggestions):
        chosen = suggestions[int(text) - 1]
        await state.update_data(district=chosen)
        await message.answer(f"📍 Обрано: <b>{chosen}</b>")
        await _advance_to_price(message, state)
        return

    # User retyped — re-run resolver.
    canonical = await sync_to_async(resolve_location, thread_sensitive=True)(text)
    if canonical:
        await state.update_data(district=canonical)
        await message.answer(f"📍 Знайшов: <b>{canonical}</b>")
        await _advance_to_price(message, state)
        return

    # Still no match — accept raw text, warn, move on.
    await state.update_data(district=text)
    await message.answer(f"⚠️ Локації «{text}» немає в базі. Зберігаю як є.")
    await _advance_to_price(message, state)


@router.message(SubscribeStates.max_price, F.text)
async def step_max_price(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if _parse_skip(text):
        await state.update_data(max_price=None, currency="")
    else:
        parts = text.split()
        try:
            amount = int(parts[0].replace(",", "").replace(" ", ""))
        except (ValueError, IndexError):
            await message.answer("Не зрозумів суму. Спробуй ще раз або «-».")
            return
        currency = parts[1].upper() if len(parts) > 1 else "UAH"
        await state.update_data(max_price=amount, currency=currency)
    await state.set_state(SubscribeStates.rooms)
    await message.answer(
        "3/3 🛏 Кількість кімнат? Приклади: <code>1</code>, <code>1-2</code>, <code>-3</code>. «-» щоб пропустити."
    )


@router.message(SubscribeStates.rooms, F.text)
async def step_rooms(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if _parse_skip(text):
        min_rooms = max_rooms = None
    else:
        min_rooms, max_rooms = _parse_rooms(text)
        if min_rooms is None and max_rooms is None and text:
            await message.answer("Не зрозумів формат кімнат. Спробуй ще раз або «-».")
            return

    data = await state.get_data()
    if message.from_user is None:
        return
    sub = await _save_subscription(
        message.from_user.id,
        {
            "district": data.get("district") or "",
            "max_price": data.get("max_price"),
            "currency": data.get("currency") or "",
            "min_rooms": min_rooms,
            "max_rooms": max_rooms,
        },
    )
    await state.clear()
    await message.answer(
        f"✅ Підписка #{sub.id} створена: <b>{sub}</b>\nЯ повідомлю про нові оголошення."
    )


@router.message(StateFilter(SubscribeStates), Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Скасовано.")
