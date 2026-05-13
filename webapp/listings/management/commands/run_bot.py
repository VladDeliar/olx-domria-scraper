"""Launch the Telegram bot (long-running, polls Telegram for updates)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from bot.main import run


class Command(BaseCommand):
    help = "Run the Telegram bot (long-polling). Stops on Ctrl-C."

    def handle(self, *args: Any, **opts: Any) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError(
                "TELEGRAM_BOT_TOKEN is empty. Put it in c:\\parser\\.env "
                "(copy from .env.example, get token from @BotFather)."
            )
        try:
            asyncio.run(run(token))
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Stopped."))
