"""aiogram bot entry point. Called by `manage.py run_bot`."""

from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import manage as manage_router
from bot.handlers import start as start_router
from bot.handlers import subscribe as subscribe_router

logger = logging.getLogger(__name__)


async def run(token: str) -> None:
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty")

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start_router.router)
    dp.include_router(subscribe_router.router)
    dp.include_router(manage_router.router)

    me = await bot.get_me()
    logger.info("Starting bot @%s (id=%s)", me.username, me.id)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
