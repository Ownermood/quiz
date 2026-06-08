"""
BotMessageTracker — one active bot message per type per chat.

Tracks the last bot message per (chat_id, msg_type) in MongoDB and deletes the
old message automatically before a new one of the same type is sent.

Usage pattern (in any command handler):
    # Delete old, send new, register new
    await self.tracker.delete_previous(context.bot, chat_id, "score")
    msg = await self._reply(update, "📊 …")
    if msg:
        self.tracker.save_tracked(chat_id, "score", msg.message_id)

Covered message types: "start", "score", "stats", "achievements",
                       "leaderboard", "welcome" (startup broadcast).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class BotMessageTracker:
    COLLECTION = "bot_messages"

    def __init__(self, db_manager=None):
        self.db = db_manager
        # (chat_id, msg_type) -> message_id
        self._cache: Dict[Tuple[int, str], int] = {}
        self._load_state()

    # ── Internal ───────────────────────────────────────────────

    def _col(self):
        return self.db.db[self.COLLECTION] if self.db else None

    def _load_state(self):
        if not self.db:
            return
        try:
            for doc in self._col().find(
                {}, {"_id": 0, "chat_id": 1, "msg_type": 1, "message_id": 1}
            ):
                cid   = doc.get("chat_id")
                mtype = doc.get("msg_type")
                mid   = doc.get("message_id")
                if cid is not None and mtype and mid:
                    self._cache[(cid, mtype)] = mid
            if self._cache:
                logger.info(f"[TRACKER] Loaded {len(self._cache)} tracked message(s)")
        except Exception as e:
            logger.warning(f"[TRACKER] Could not load state: {e}")

    # ── Public API ─────────────────────────────────────────────

    def get_tracked(self, chat_id: int, msg_type: str) -> Optional[int]:
        return self._cache.get((chat_id, msg_type))

    def save_tracked(self, chat_id: int, msg_type: str, message_id: int):
        """Register a new message as the active one for this type in this chat."""
        key = (chat_id, msg_type)
        self._cache[key] = message_id
        if self.db:
            try:
                self._col().update_one(
                    {"chat_id": chat_id, "msg_type": msg_type},
                    {"$set": {
                        "message_id": message_id,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
            except Exception as e:
                logger.debug(f"[TRACKER] save failed for {chat_id}/{msg_type}: {e}")

    def clear_tracked(self, chat_id: int, msg_type: str):
        self._cache.pop((chat_id, msg_type), None)
        if self.db:
            try:
                self._col().delete_one({"chat_id": chat_id, "msg_type": msg_type})
            except Exception as e:
                logger.debug(f"[TRACKER] clear failed for {chat_id}/{msg_type}: {e}")

    async def delete_previous(self, bot, chat_id: int, msg_type: str) -> bool:
        """
        Delete the previously tracked message of this type if it exists.
        Always clears the record afterwards (even if delete fails).
        Returns True if a message was actually deleted.
        """
        msg_id = self.get_tracked(chat_id, msg_type)
        if not msg_id:
            return False
        deleted = False
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            deleted = True
            logger.debug(f"[TRACKER] Deleted old {msg_type} msg={msg_id} chat={chat_id}")
        except Exception as e:
            logger.debug(f"[TRACKER] Delete skipped ({msg_type} chat={chat_id}): {e}")
        self.clear_tracked(chat_id, msg_type)
        return deleted

    async def startup_cleanup(self, bot):
        """
        On bot restart: delete all tracked startup welcome messages so previous
        restart notifications don't accumulate in every chat.
        """
        welcome_entries = [
            (cid, mtype, mid)
            for (cid, mtype), mid in list(self._cache.items())
            if mtype == "welcome"
        ]
        if not welcome_entries:
            logger.info("[TRACKER] Startup cleanup — no old welcome messages")
            return

        logger.info(f"[TRACKER] Startup cleanup — {len(welcome_entries)} welcome message(s)")
        for chat_id, msg_type, msg_id in welcome_entries:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                logger.debug(f"[TRACKER] Cleaned welcome msg={msg_id} chat={chat_id}")
            except Exception as e:
                logger.debug(f"[TRACKER] Welcome cleanup skip chat={chat_id}: {e}")
            self.clear_tracked(chat_id, msg_type)
            await asyncio.sleep(0.05)

        logger.info("[TRACKER] Startup cleanup complete")
