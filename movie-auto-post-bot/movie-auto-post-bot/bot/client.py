"""
bot/client.py — Single Pyrogram Client instance shared across the project.
"""
from pyrogram import Client

from config import settings

app = Client(
    name="movie_auto_post_bot",
    api_id=settings.API_ID,
    api_hash=settings.API_HASH,
    bot_token=settings.BOT_TOKEN,
    # Increase workers for high-traffic channels
    workers=8,
)
