"""
AutoQuizScheduler — production-grade, singleton, fault-tolerant.

Design guarantees:
  • Exactly one quiz per 30-minute interval per active chat.
  • No overlapping/bunched jobs (max_instances=1, coalesce).
  • Previous quiz message deleted before new one is posted —
    via the shared QuizCleanupManager (single active quiz per chat).
  • Poll validated and sanitized before every send.
  • Inline-keyboard fallback when poll fails.
  • Never crashes — all errors caught per chat.
  • Single global instance enforced at module level.
"""

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.core.validators import validate, sanitize, build_explanation

logger = logging.getLogger(__name__)

# ── Singleton guard ────────────────────────────────────────────────────────────
_INSTANCE: Optional["AutoQuizScheduler"] = None


class AutoQuizScheduler:

    def __init__(self, bot, quiz_manager, db_manager=None, interval_minutes: int = 30):
        global _INSTANCE
        if _INSTANCE is not None:
            logger.warning("[QUIZ] Duplicate scheduler detected — stopping old instance")
            try:
                _INSTANCE._scheduler.shutdown(wait=False)
            except Exception:
                pass
        _INSTANCE = self

        self.bot          = bot
        self.quiz_manager = quiz_manager
        self.db           = db_manager
        self.interval     = interval_minutes
        self._scheduler   = AsyncIOScheduler()
        self._running     = False

    @property
    def _cleanup(self):
        """Shared single-active-quiz cleanup manager (lives on the bot)."""
        return getattr(self.bot, "cleanup", None)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            logger.warning("[QUIZ] Scheduler already running — skipping duplicate start")
            return
        self._scheduler.add_job(
            self._send_auto_quiz,
            trigger="interval",
            minutes=self.interval,
            id="auto_quiz",
            replace_existing=True,
            max_instances=1,
            coalesce=True,          # skip missed fires instead of bunching
            misfire_grace_time=60,  # ignore fires more than 60s late
        )
        self._scheduler.start()
        self._running = True
        logger.info(f"[QUIZ] Scheduler Started — interval: {self.interval} min")

    def stop(self):
        try:
            self._scheduler.shutdown(wait=False)
        except Exception:
            pass
        self._running = False
        logger.info("[QUIZ] Scheduler Stopped")

    # ── Core job ───────────────────────────────────────────────────────────────

    async def _send_auto_quiz(self):
        chats = list(self.quiz_manager.active_chats)
        if not chats:
            logger.info("[QUIZ] No active chats — skipping cycle")
            return

        logger.info(f"[QUIZ] Scheduler cycle — {len(chats)} chat(s)")

        for chat_id in chats:
            try:
                await self._send_to_chat(chat_id)
            except Exception as e:
                logger.error(f"[QUIZ] Unhandled error for chat {chat_id}: {e}")

    async def _send_to_chat(self, chat_id: int):
        # Get a valid question (up to 5 attempts)
        question = None
        for attempt in range(5):
            q = self.quiz_manager.get_random_question(chat_id=chat_id)
            if not q:
                logger.warning(f"[QUIZ] No questions available for {chat_id}")
                return
            q = sanitize(q)
            if q and validate(q).valid:
                question = q
                break
            logger.warning(f"[QUIZ] Invalid Question Skipped (attempt {attempt+1}/5)")

        if not question:
            logger.error(f"[QUIZ] All replacement questions failed for {chat_id} — skipping")
            return

        logger.info(f"[QUIZ] Quiz Validation Passed — Q#{question.get('id')} for {chat_id}")

        # Group thread_id
        thread_id = None
        if self.db:
            try:
                gdoc = self.db.groups_col.find_one({"chat_id": chat_id}, {"message_thread_id": 1})
                if gdoc:
                    thread_id = gdoc.get("message_thread_id")
            except Exception:
                pass

        # ── Single-active-quiz cleanup: delete previous quiz first ──
        logger.info(f"[QUIZ] Sending New Quiz — auto chat={chat_id}")
        if self._cleanup:
            await self._cleanup.cleanup(self.bot.application.bot, chat_id)

        # Try poll first, then inline fallback
        msg, timed_out = await self._try_send_poll(chat_id, question, thread_id)
        quiz_type = "poll"
        if msg is None and timed_out:
            # Network timeout — poll may have been delivered; skip inline to
            # avoid a duplicate quiz. State stays cleared; next cycle proceeds.
            logger.warning(f"[QUIZ] Poll timed out for {chat_id} — skipping inline fallback")
            return
        if msg is None:
            logger.info(f"[QUIZ] Switching To Inline Mode for {chat_id}")
            msg = await self._try_send_inline(chat_id, question, thread_id)
            quiz_type = "inline"

        if msg is None:
            logger.error(f"[QUIZ] All send methods failed for {chat_id} — skipping")
            return

        # Register as the single active quiz for this chat
        if self._cleanup:
            self._cleanup.save_active(chat_id, msg.message_id,
                                      quiz_type=quiz_type, thread_id=thread_id)
        logger.info(f"[QUIZ] Quiz Sent Successfully — msg_id={msg.message_id} chat={chat_id}")
        logger.info(f"[QUIZ] Next Quiz Scheduled — in {self.interval} min for {chat_id}")

        # Save poll mapping for answer tracking
        if self.db and hasattr(msg, "poll") and msg.poll:
            try:
                self.db.save_poll_mapping(str(msg.poll.id), question.get("id"))
            except Exception:
                pass

    async def _try_send_poll(self, chat_id: int, q: dict, thread_id=None):
        """Attempt to send a Telegram Quiz Poll.
        Returns (message_or_None, timed_out: bool)."""
        from telegram import Poll
        from telegram.error import TimedOut, NetworkError
        try:
            cat       = q.get("category", "General")
            cat_emoji = _cat_emoji(cat)
            poll_q    = f"{cat_emoji} {q['question']}"
            if len(poll_q) > 300:
                poll_q = poll_q[:299] + "…"

            kwargs = dict(
                chat_id           = chat_id,
                question          = poll_q,
                options           = q["options"],
                type              = Poll.QUIZ,
                correct_option_id = q["correct_answer"],
                explanation       = build_explanation(q),
                is_anonymous      = False,
            )
            if thread_id:
                kwargs["message_thread_id"] = thread_id

            logger.info(f"[QUIZ] Poll Validation Passed — sending poll to {chat_id}")
            return await self.bot.application.bot.send_poll(**kwargs), False

        except (TimedOut, NetworkError) as e:
            logger.warning(f"[QUIZ] Poll send timed out for {chat_id}: {e}")
            return None, True
        except Exception as e:
            logger.warning(f"[QUIZ] Poll send failed for {chat_id}: {e}")
            return None, False

    async def _try_send_inline(self, chat_id: int, q: dict, thread_id=None):
        """Fallback: send question as inline-keyboard message. Returns message or None."""
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        try:
            cat      = q.get("category", "General")
            cat_emoji= _cat_emoji(cat)
            opts     = q["options"]
            correct  = q["correct_answer"]
            q_id     = q.get("id", "?")
            labels   = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

            text = (
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📚 CLAT VISION  •  QUIZ\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Category:</b> {cat_emoji} {cat}\n"
                f"<b>Q#{q_id}</b>\n\n"
                f"{q['question']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Select the correct answer:"
            )

            # One button per option
            buttons = []
            for i, opt in enumerate(opts):
                label = f"{labels[i]}  {opt}" if i < len(labels) else opt
                buttons.append([InlineKeyboardButton(
                    label[:64], callback_data=f"aq_ans_{q_id}_{i}_{correct}")])

            kb = InlineKeyboardMarkup(buttons)
            kwargs = dict(
                chat_id      = chat_id,
                text         = text,
                parse_mode   = "HTML",
                reply_markup = kb,
            )
            if thread_id:
                kwargs["message_thread_id"] = thread_id

            return await self.bot.application.bot.send_message(**kwargs)

        except Exception as e:
            logger.error(f"[QUIZ] Inline fallback failed for {chat_id}: {e}")
            return None


# ── Helpers ────────────────────────────────────────────────────────────────────

_EMOJI_MAP = {
    "gk": "🌍", "current": "📰", "static": "📚",
    "science": "🔬", "history": "📜", "geography": "🗺",
    "economics": "💰", "polity": "🏛️", "political": "🏛️",
    "constitution": "⚖️", "legal": "⚖️",
    "arts": "🎭", "literature": "🎭",
    "sports": "🎮", "english": "📖",
    "math": "🔢", "reasoning": "🧠",
}

def _cat_emoji(cat: str) -> str:
    key = (cat or "").lower().strip()
    for k, e in _EMOJI_MAP.items():
        if k in key:
            return e
    return "📚"
