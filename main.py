"""
Movie Auto Post Bot — Entry Point
"""
import asyncio
import logging

from bot.client import app
from bot.database.mongo import Database
from bot import handlers  # noqa: F401 — registers all handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await Database.connect()
    logger.info("MongoDB connected successfully.")

    async with app:
        logger.info("Movie Auto Post Bot is running …")
        await asyncio.Event().wait()          # keep running until SIGINT/SIGTERM


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
