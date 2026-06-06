"""
Auto Quiz Scheduler — har 30 min mein naya quiz bhejo, purana delete karo
"""

import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

class AutoQuizScheduler:

    def __init__(self, bot, quiz_manager, interval_minutes: int = 30):
        self.bot          = bot
        self.quiz_manager = quiz_manager
        self.interval     = interval_minutes
        self.scheduler    = AsyncIOScheduler()
        self.last_poll_ids: dict = {}  # chat_id -> message_id

    def start(self):
        self.scheduler.add_job(
            self._send_auto_quiz,
            trigger="interval",
            minutes=self.interval,
            id="auto_quiz",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info(f"✅ AutoQuizScheduler started — interval: {self.interval} min")

    def stop(self):
        self.scheduler.shutdown(wait=False)
        logger.info("AutoQuizScheduler stopped")

    async def _send_auto_quiz(self):
        chats = list(self.quiz_manager.active_chats)
        if not chats:
            logger.info("No active chats — skipping auto quiz")
            return

        question = self.quiz_manager.get_random_question()
        if not question:
            logger.warning("No questions available for auto quiz")
            return

        for chat_id in chats:
            try:
                # Purana poll delete karo
                old_msg_id = self.last_poll_ids.get(chat_id)
                if old_msg_id:
                    try:
                        await self.bot.application.bot.delete_message(
                            chat_id=chat_id,
                            message_id=old_msg_id
                        )
                    except Exception as e:
                        logger.warning(f"Delete failed for {chat_id}: {e}")

                # Naya poll bhejo
                options = question.get("options", [])
                correct_idx = question.get("correct_option_id", 0)
                explanation = question.get("explanation", "")

                msg = await self.bot.application.bot.send_poll(
                    chat_id=chat_id,
                    question=question.get("question", "Quiz"),
                    options=options,
                    type="quiz",
                    correct_option_id=correct_idx,
                    explanation=explanation[:200] if explanation else None,
                    is_anonymous=False,
                )
                self.last_poll_ids[chat_id] = msg.message_id
                logger.info(f"Auto quiz sent to {chat_id} — msg_id: {msg.message_id}")

            except Exception as e:
                logger.error(f"Auto quiz failed for {chat_id}: {e}")
