"""
Importing handler modules registers their @app.on_* decorators with the
Pyrogram client.  Add new handler modules here.
"""
from . import channel_post  # noqa: F401

__all__ = ["channel_post"]
