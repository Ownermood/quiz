"""
Quiz Cleanup Manager — enforces a SINGLE active quiz per chat.

Every quiz-send path (auto scheduler, /quiz command, category, admin, and any
future quiz mode) MUST use this manager:

    await cleanup.cleanup(bot, chat_id)        # delete previous, before sending
    ... send the new quiz ...
    cleanup.save_active(chat_id, message_id)   # register the new active quiz

State is persisted in the `active_quiz` MongoDB collection (one doc per chat),
so the single-quiz guarantee survives restarts via startup_recovery().
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class QuizCleanupManager:
    COLLECTION = "active_quiz"

    def __init__(self, db_manager=None):
        self.db = db_manager
        self._active: Dict[int, dict] = {}   # chat_id -> record
        self._load_state()

    # ── Internal ────────────────────────────────────────────────────────────────

    def _col(self):
        return self.db.db[self.COLLECTION] if self.db else None

    def _load_state(self):
        """Load persisted active-quiz records on startup."""
        if not self.db:
            return
        try:
            for doc in self._col().find({}, {"_id": 0}):
                cid = doc.get("chat_id")
                if cid is not None:
                    self._active[cid] = doc
            if self._active:
                logger.info(f"[QUIZ] Loaded {len(self._active)} active-quiz record(s)")
        except Exception as e:
            logger.warning(f"[QUIZ] Could not load active-quiz state: {e}")

    def _clear(self, chat_id: int):
        """Remove an active-quiz record from cache and DB."""
        self._active.pop(chat_id, None)
        if self.db:
            try:
                self._col().delete_one({"chat_id": chat_id})
            except Exception as e:
                logger.warning(f"[QUIZ] Could not clear active-quiz for {chat_id}: {e}")

    # ── Public API ──────────────────────────────────────────────────────────────

    def get_active(self, chat_id: int) -> Optional[dict]:
        rec = self._active.get(chat_id)
        if rec is None and self.db:
            try:
                rec = self._col().find_one({"chat_id": chat_id}, {"_id": 0})
                if rec:
                    self._active[chat_id] = rec
            except Exception:
                rec = None
        return rec

    async def cleanup(self, bot, chat_id: int) -> bool:
        """
        Delete the currently-active quiz for a chat (if any) and clear its data.
        Returns True if a previous quiz message was actually deleted.
        Never raises — failures are logged and execution continues safely.
        """
        rec = self.get_active(chat_id)
        if not rec:
            return False

        msg_id = rec.get("message_id")
        logger.info(f"[QUIZ] Active Quiz Found — chat={chat_id} msg={msg_id}")

        deleted = False
        if msg_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                deleted = True
                logger.info(f"[QUIZ] Previous Quiz Deleted — chat={chat_id} msg={msg_id}")
            except Exception as e:
                logger.warning(
                    f"[QUIZ] Cleanup Failed - Continuing Safely — "
                    f"chat={chat_id} msg={msg_id}: {e}")

        self._clear(chat_id)
        logger.info(f"[QUIZ] Cleanup Completed — chat={chat_id}")
        return deleted

    def save_active(self, chat_id: int, message_id: int,
                    quiz_type: str = "poll", thread_id: Optional[int] = None):
        """Register the new (and only) active quiz for a chat — overwrites old."""
        rec = {
            "chat_id":    chat_id,
            "message_id": message_id,
            "quiz_type":  quiz_type,
            "thread_id":  thread_id,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        }
        self._active[chat_id] = rec
        if self.db:
            try:
                self._col().update_one(
                    {"chat_id": chat_id}, {"$set": rec}, upsert=True)
            except Exception as e:
                logger.warning(f"[QUIZ] Could not save active-quiz for {chat_id}: {e}")
        logger.info(
            f"[QUIZ] New Active Quiz Saved — chat={chat_id} "
            f"msg={message_id} type={quiz_type}")

    async def startup_recovery(self, bot):
        """
        On bot restart: delete any leftover active quizzes so the bot starts
        with a clean state and quizzes never accumulate across restarts.
        """
        if not self._active:
            logger.info("[QUIZ] Startup recovery — no leftover quizzes")
            return
        leftover = list(self._active.keys())
        logger.info(f"[QUIZ] Startup recovery — {len(leftover)} leftover quiz(es)")
        for chat_id in leftover:
            try:
                await self.cleanup(bot, chat_id)
            except Exception as e:
                logger.warning(f"[QUIZ] Startup recovery error for {chat_id}: {e}")
        logger.info("[QUIZ] Startup recovery complete — clean state")
