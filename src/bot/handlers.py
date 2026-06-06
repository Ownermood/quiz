"""
╔══════════════════════════════════════════════════════════╗
║          CLAT VISION QUIZ BOT — HANDLER ENGINE          ║
║     Professional • Mafiya-Style • Inline Mentions       ║
║     Smart DelQuiz • Bot Stats • Premium Formatting      ║
╚══════════════════════════════════════════════════════════╝
"""

import logging
import asyncio
import os
import re
import time
from typing import Optional, Any
from datetime import datetime

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand, Poll
)
from telegram.ext import (
    Application, CommandHandler, PollAnswerHandler,
    CallbackQueryHandler, MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from telegram.error import TelegramError, Forbidden, BadRequest

logger   = logging.getLogger(__name__)
OWNER_ID = int(os.environ.get("OWNER_ID", "8403136097"))

# ╔══════════════════════════════════════════════════════════╗
# ║                    DESIGN SYSTEM                        ║
# ╚══════════════════════════════════════════════════════════╝

class UI:
    """
    Central design token system.
    All visual constants & helpers live here — never inline.
    """

    # ── Separators ────────────────────────────────────────
    LINE    = "━" * 30
    DOTLINE = "┄" * 30
    THIN    = "─" * 28

    # ── Progress bar ─────────────────────────────────────
    @staticmethod
    def bar(pct: float, width: int = 10) -> str:
        filled = max(0, min(width, int(float(pct) / 100 * width)))
        return "█" * filled + "░" * (width - filled)

    @staticmethod
    def mini_bar(pct: float, width: int = 5) -> str:
        filled = max(0, min(width, int(float(pct) / 100 * width)))
        return "▰" * filled + "▱" * (width - filled)

    # ── Rank badges ───────────────────────────────────────
    @staticmethod
    def rank(score: int) -> tuple:
        if   score >= 500: return "👑 LEGEND",    "S"
        elif score >= 200: return "🔱 MASTER",    "A+"
        elif score >= 100: return "⚔️  EXPERT",   "A"
        elif score >= 50:  return "🎯 ADVANCED",  "B"
        elif score >= 20:  return "📈 RISING",    "C"
        elif score >= 5:   return "🌱 BEGINNER",  "D"
        else:              return "🎲 ROOKIE",    "E"

    # ── Medals ────────────────────────────────────────────
    MEDALS = ["🥇", "🥈", "🥉"] + ["🏅"] * 20

    # ── Category system ───────────────────────────────────
    CATS = {
        "legal":    ("⚖️",  "crimson"),
        "english":  ("📖",  "gold"),
        "gk":       ("🌐",  "teal"),
        "current":  ("📰",  "orange"),
        "polity":   ("🏛️",  "purple"),
        "math":     ("🔢",  "blue"),
        "reasoning":("🧠",  "green"),
        "history":  ("📜",  "brown"),
        "default":  ("📚",  "grey"),
    }

    @staticmethod
    def cat_emoji(cat: str) -> str:
        cat_lower = (cat or "").lower()
        for k, (emoji, _) in UI.CATS.items():
            if k in cat_lower:
                return emoji
        return UI.CATS["default"][0]

    # ── Section headers (Telegram-safe box drawing) ───────
    @staticmethod
    def box(emoji: str, title: str, width: int = 32) -> str:
        return f"<b>{'━'*width}</b>\n<b>{emoji}  {title}</b>\n<b>{'━'*width}</b>"

    @staticmethod
    def section(emoji: str, title: str) -> str:
        return f"\n<b>┌{'─'*2} {emoji} {title}</b>"

    @staticmethod
    def row(label: str, value: str, emoji: str = "▸") -> str:
        return f"│  {emoji} {label}: <b>{value}</b>"

    @staticmethod
    def end() -> str:
        return "└" + "─" * 20

    # ── Inline mention ────────────────────────────────────
    @staticmethod
    def mention(user_id: int, name: str) -> str:
        """Create a clickable inline user mention."""
        safe = name.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        return f'<a href="tg://user?id={user_id}">{safe}</a>'

    # ── Fire streak ───────────────────────────────────────
    @staticmethod
    def streak_display(n: int) -> str:
        if n == 0: return "—"
        fires = "🔥" * min(n, 5)
        return f"{fires} <b>{n}</b>"

    # ── Loading dots ──────────────────────────────────────
    SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


# ╔══════════════════════════════════════════════════════════╗
# ║                  FORUM / TOPIC HELPERS                  ║
# ╚══════════════════════════════════════════════════════════╝

def get_thread_id(update: Update) -> Optional[int]:
    msg = update.effective_message
    if msg and getattr(msg, "is_topic_message", False):
        return msg.message_thread_id
    return None

def get_tracking_id(chat_id: int, thread_id: Optional[int]) -> int:
    return int(f"{abs(chat_id)}{thread_id}") if thread_id else chat_id


# ╔══════════════════════════════════════════════════════════╗
# ║                    MAIN BOT CLASS                       ║
# ╚══════════════════════════════════════════════════════════╝

class TelegramQuizBot:

    def __init__(self, quiz_manager, db_manager=None):
        self.quiz_manager             = quiz_manager
        self.db                       = db_manager
        self.application: Optional[Application] = None
        self._dev                     = None
        # In-memory delete selection state {user_id: page}
        self._del_page: dict          = {}

    # ════════════════════════════════════════════════════════
    #  INITIALIZATION
    # ════════════════════════════════════════════════════════

    async def initialize(self, token: str):
        self.application = Application.builder().token(token).build()
        self._register_handlers()
        await self.application.initialize()
        await self._set_commands()
        logger.info("✅ Bot initialized — polling mode")

    async def initialize_webhook(self, token: str, webhook_url: str):
        self.application = Application.builder().token(token).build()
        self._register_handlers()
        await self.application.initialize()
        await self.application.bot.set_webhook(url=webhook_url)
        await self._set_commands()
        logger.info(f"✅ Bot initialized — webhook: {webhook_url}")

    def _register_handlers(self):
        app = self.application

        # ── User commands ─────────────────────────────────
        app.add_handler(CommandHandler("start",       self.cmd_start))
        app.add_handler(CommandHandler("help",        self.cmd_help))
        app.add_handler(CommandHandler("quiz",        self.cmd_quiz))
        app.add_handler(CommandHandler("q",           self.cmd_quiz))
        app.add_handler(CommandHandler("score",       self.cmd_score))
        app.add_handler(CommandHandler("stats",       self.cmd_stats))
        app.add_handler(CommandHandler("botstats",    self.cmd_botstats))
        app.add_handler(CommandHandler("leaderboard", self.cmd_leaderboard))
        app.add_handler(CommandHandler("lb",          self.cmd_leaderboard))
        app.add_handler(CommandHandler("ping",        self.cmd_ping))
        app.add_handler(CommandHandler("info",        self.cmd_info))

        # ── Admin commands ────────────────────────────────
        app.add_handler(CommandHandler("addquiz",     self.cmd_addquiz))
        app.add_handler(CommandHandler("importquiz",  self.cmd_importquiz))
        app.add_handler(CommandHandler("delquiz",     self.cmd_delquiz))
        app.add_handler(CommandHandler("editquiz",    self.cmd_editquiz))
        app.add_handler(CommandHandler("dev",         self.cmd_dev))
        app.add_handler(CommandHandler("broadcast",   self.cmd_broadcast))
        app.add_handler(CommandHandler("bc",          self.cmd_broadcast))
        app.add_handler(CommandHandler("reload",      self.cmd_reload))
        app.add_handler(CommandHandler("restart",     self.cmd_restart))

        # ── Poll + Callbacks ──────────────────────────────
        app.add_handler(PollAnswerHandler(self.handle_poll_answer))
        app.add_handler(CallbackQueryHandler(
            self._cb_delquiz, pattern=r"^dq_"))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        # ── Bulk import: .txt file upload ─────────────────
        app.add_handler(MessageHandler(
            filters.Document.TXT | filters.Document.TEXT,
            self.handle_document))

        # ── Dev module (optional) ─────────────────────────
        try:
            from src.bot.dev_commands import DeveloperCommands
            if self.db:
                self._dev = DeveloperCommands(self.db, self.quiz_manager)
                app.add_handler(CommandHandler("devstats",    self._dev.devstats))
                app.add_handler(CommandHandler("activity",    self._dev.activity))
                app.add_handler(CommandHandler("performance", self._dev.performance_stats))
                app.add_handler(CallbackQueryHandler(
                    self._dev.handle_edit_quiz_callback, pattern="^eq_"))
                app.add_handler(MessageHandler(
                    filters.TEXT & ~filters.COMMAND, self._dev.handle_text_input))
                logger.info("DeveloperCommands ✅")
        except Exception as e:
            logger.warning(f"DeveloperCommands skip: {e}")

    async def _set_commands(self):
        try:
            await self.application.bot.set_my_commands([
                BotCommand("quiz",        "🎯 Get a quiz question"),
                BotCommand("score",       "🏆 Your personal score"),
                BotCommand("stats",       "📈 Your detailed stats"),
                BotCommand("botstats",    "📊 Bot-wide quiz statistics"),
                BotCommand("leaderboard", "🔱 Global leaderboard"),
                BotCommand("help",        "📖 All commands"),
                BotCommand("start",       "🚀 Welcome screen"),
                BotCommand("ping",        "🏓 Bot latency"),
            ])
        except Exception as e:
            logger.warning(f"set_my_commands: {e}")

    # ════════════════════════════════════════════════════════
    #  CORE HELPERS
    # ════════════════════════════════════════════════════════

    def _is_owner(self, uid: int) -> bool:
        return uid == OWNER_ID

    async def _is_authorized(self, uid: int) -> bool:
        if self._is_owner(uid):
            return True
        if self.db:
            try:
                return any(d.get("user_id") == uid
                           for d in self.db.get_all_developers())
            except Exception:
                pass
        return False

    async def _reply(self, update: Update, text: str,
                     parse_mode=ParseMode.HTML,
                     reply_markup=None, **kw) -> Optional[Any]:
        """Smart reply — auto-injects thread_id for forum topics."""
        tid    = get_thread_id(update)
        kwargs = {"parse_mode": parse_mode}
        if reply_markup:
            kwargs["reply_markup"] = reply_markup
        if tid:
            kwargs["message_thread_id"] = tid
        kwargs.update(kw)
        try:
            return await update.effective_message.reply_text(text, **kwargs)
        except TelegramError as e:
            if any(w in str(e).lower() for w in ("topic", "thread", "closed")):
                kwargs.pop("message_thread_id", None)
                try:
                    return await update.effective_message.reply_text(text, **kwargs)
                except Exception:
                    pass
            logger.error(f"_reply error: {e}")
        return None

    async def _edit(self, msg, text: str, reply_markup=None):
        """Safe message edit."""
        try:
            kwargs = {"parse_mode": ParseMode.HTML}
            if reply_markup:
                kwargs["reply_markup"] = reply_markup
            await msg.edit_text(text, **kwargs)
        except Exception as e:
            logger.error(f"_edit error: {e}")

    async def _unauthorized(self, update: Update):
        user = update.effective_user
        mention = UI.mention(user.id, user.first_name or "User")
        text = (
            f"🔐 <b>ACCESS DENIED</b>\n"
            f"{UI.LINE}\n\n"
            f"Sorry {mention}, this command requires\n"
            f"<b>Owner</b> or <b>Developer</b> access.\n\n"
            f"<i>Contact @CLAT_Vision for access.</i>"
        )
        msg = await self._reply(update, text)
        await asyncio.sleep(7)
        try:
            if msg: await msg.delete()
            await update.effective_message.delete()
        except Exception:
            pass

    # ════════════════════════════════════════════════════════
    #  /start
    # ════════════════════════════════════════════════════════

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user    = update.effective_user
        name    = user.first_name or "Student"
        mention = UI.mention(user.id, name)
        q_count = len(self.quiz_manager.questions)
        is_pm   = update.effective_chat.type == "private"

        if is_pm:
            boot_frames = [
                "⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛\n⚡ <b>CLAT VISION</b> — <i>Booting...</i>",
                "🟥⬛⬛⬛⬛⬛⬛⬛⬛⬛\n🔍 <i>Scanning your profile...</i>",
                "🟥🟥⬛⬛⬛⬛⬛⬛⬛⬛\n📡 <i>Connecting to servers...</i>",
                "🟥🟥🟥⬛⬛⬛⬛⬛⬛⬛\n📚 <i>Loading question bank...</i>",
                "🟧🟧🟧🟧⬛⬛⬛⬛⬛⬛\n🏆 <i>Fetching leaderboard...</i>",
                "🟧🟧🟧🟧🟧⬛⬛⬛⬛⬛\n📊 <i>Loading your stats...</i>",
                "🟨🟨🟨🟨🟨🟨⬛⬛⬛⬛\n🔥 <i>Calculating streak...</i>",
                "🟨🟨🟨🟨🟨🟨🟨⬛⬛⬛\n💎 <i>Checking your level...</i>",
                "🟩🟩🟩🟩🟩🟩🟩🟩⬛⬛\n✨ <i>Personalising dashboard...</i>",
                "🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩\n✅ <b>System Ready! Welcome!</b>",
            ]
            msg = await self._reply(update, boot_frames[0])
            for frame in boot_frames[1:]:
                await asyncio.sleep(0.35)
                await self._edit(msg, frame)
            await asyncio.sleep(0.4)

        streak = 0
        total_score = 0
        rank = "Unranked"
        level = "🥉 Beginner"
        if self.db:
            try:
                u = self.db.get_user(user.id)
                if u:
                    streak = u.get("streak", 0)
                    total_score = u.get("total_score", 0)
                    if total_score >= 1000:
                        level = "💎 Elite"
                    elif total_score >= 500:
                        level = "🥇 Advanced"
                    elif total_score >= 100:
                        level = "🥈 Intermediate"
            except Exception:
                pass

        streak_bar = ("🔥" * min(streak, 7)) if streak > 0 else "❄️ Start today!"

        text = (
            f"╔═══════════════════════════╗\n"
            f"║  🎓 <b>CLAT VISION QUIZ BOT</b>  ║\n"
            f"╚═══════════════════════════╝\n\n"
            f"⚡ <b>Hey {mention}!</b> 👋\n"
            f"<i>Your CLAT 2027 grind never stops! 💪</i>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>LIVE DASHBOARD</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  🎯  Questions  ›  <b>{q_count} ready</b>\n"
            f"  🏆  Rank       ›  <b>{rank}</b>\n"
            f"  ⭐  Score      ›  <b>{total_score} pts</b>\n"
            f"  🎖️   Level      ›  <b>{level}</b>\n"
            f"  🔥  Streak     ›  <b>{streak} days</b>\n"
            f"  {streak_bar}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🚀 <b>ARSENAL</b>\n"
            f"  ⚡ Timed Quizzes  •  🗂️ Categories\n"
            f"  📊 Deep Analytics  •  🏆 Rankings\n"
            f"  🔔 Daily Reminders  •  📖 Guides\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Tip: Daily 20 mins = CLAT cracked!</i>\n"
            f"<i>⚡ @CLAT_Vision  •  CLAT 2027</i>"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ Play Quiz",      callback_data="play_quiz"),
             InlineKeyboardButton("📊 My Stats",       callback_data="my_stats")],
            [InlineKeyboardButton("🏆 Leaderboard",    callback_data="leaderboard"),
             InlineKeyboardButton("📖 Help",            callback_data="help")],
            [InlineKeyboardButton("🌐 CLAT Vision Channel", url="https://t.me/CLAT_Vision")],
        ])

        if is_pm and "msg" in locals() and msg:
            await self._edit(msg, text, kb)
        else:
            await self._reply(update, text, reply_markup=kb)
            await self._reply(update, text, reply_markup=kb)

        if self.db:
            try:
                self.db.upsert_user(user.id, {
                    "user_id":       user.id,
                    "username":      user.username or "",
                    "name":          name,
                    "last_seen":     datetime.utcnow().isoformat(),
                    "pm_accessible": is_pm,
                })
            except Exception as e:
                logger.error(f"upsert_user: {e}")

    # ════════════════════════════════════════════════════════
    #  /help
    # ════════════════════════════════════════════════════════

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        is_pm = update.effective_chat.type == "private"
        if is_pm:
            frames = [
                "📖⬛⬛⬛⬛⬛⬛⬛⬛⬛\n<i>Opening command guide...</i>",
                "📖🟦⬛⬛⬛⬛⬛⬛⬛⬛\n<i>Loading quiz commands...</i>",
                "📖🟦🟦⬛⬛⬛⬛⬛⬛⬛\n<i>Loading stat commands...</i>",
                "📖🟦🟦🟦⬛⬛⬛⬛⬛⬛\n<i>Loading admin panel...</i>",
                "📖🟦🟦🟦🟦⬛⬛⬛⬛⬛\n<i>Loading analytics...</i>",
                "📖🟦🟦🟦🟦🟦⬛⬛⬛⬛\n<i>Checking permissions...</i>",
                "📖🟦🟦🟦🟦🟦🟦⬛⬛⬛\n<i>Almost ready...</i>",
                "📖🟦🟦🟦🟦🟦🟦🟦🟦🟦\n✅ <b>Guide Ready!</b>",
            ]
            msg = await self._reply(update, frames[0])
            for frame in frames[1:]:
                await asyncio.sleep(0.3)
                await self._edit(msg, frame)
            await asyncio.sleep(0.3)

        text = (
            f"╔═══════════════════════════╗\n"
            f"║     📖 <b>CLAT VISION HELP</b>     ║\n"
            f"╚═══════════════════════════╝\n\n"

            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>PLAY QUIZ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  ⚡ /quiz — Random question\n"
            f"  🗂️ /quiz [cat] — e.g. <code>/quiz legal</code>\n"
            f"  🚀 /q — Quick shortcut\n\n"

            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>YOUR STATS</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  🏅 /score — Score + rank + streak\n"
            f"  📈 /stats — Full performance breakdown\n"
            f"  🏆 /leaderboard — Top 10 players (/lb)\n\n"

            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 <b>BOT ANALYTICS</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  📉 /botstats — Daily · weekly · monthly\n\n"

            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ <b>ADMIN PANEL</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  ➕ /addquiz — Add new question\n"
            f"  🗑️ /delquiz — Smart delete\n"
            f"  ✏️ /editquiz — Browse & manage\n"
            f"  📢 /broadcast — Message all users\n"
            f"  🔄 /reload — Sync from MongoDB\n"
            f"  ♻️ /restart — Hot restart bot\n"
            f"  📥 /importquiz — Bulk import questions\n"
            f"  🧑‍💻 /dev — Developer control panel\n\n"

            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"ℹ️ <b>INFO</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  🏓 /ping — Latency & status\n"
            f"  🤖 /info — Bot & chat info\n\n"

            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ <i>Forum & topic groups fully supported</i>\n"
            f"<i>⚡ @CLAT_Vision  •  CLAT 2027</i>"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⚡ Play Quiz",    callback_data="play_quiz"),
            InlineKeyboardButton("🏆 Leaderboard",  callback_data="leaderboard"),
        ]])
        if is_pm and "msg" in locals() and msg:
            await self._edit(msg, text, kb)
        else:
            await self._reply(update, text, reply_markup=kb)


    # ════════════════════════════════════════════════════════
    #  /ping
    # ════════════════════════════════════════════════════════

    async def cmd_ping(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        t0  = time.time()
        msg = await self._reply(update, "🏓 <i>Pinging...</i>")
        ms  = int((time.time() - t0) * 1000)
        if not msg:
            return

        q_count = len(self.quiz_manager.questions)
        bar     = UI.bar(min(100, ms / 10))
        speed   = "⚡ Blazing" if ms < 100 else "✅ Fast" if ms < 300 else "🟡 OK" if ms < 600 else "🔴 Slow"

        text = (
            f"🏓 <b>PONG!</b>\n"
            f"{UI.LINE}\n\n"
            f"  ⚡ Latency:  <code>{ms}ms</code>\n"
            f"  [{bar}]\n"
            f"  Status:     <b>{speed}</b>\n\n"
            f"  📦 Questions: <b>{q_count}</b>\n"
            f"  🟢 Bot:       <b>Online</b>\n\n"
            f"{UI.LINE}\n"
            f"<i>CLAT Vision Quiz Bot</i>"
        )
        await self._edit(msg, text)

    # ════════════════════════════════════════════════════════
    #  /info
    # ════════════════════════════════════════════════════════

    async def cmd_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat      = update.effective_chat
        thread_id = get_thread_id(update)
        q_count   = len(self.quiz_manager.questions)
        is_forum  = getattr(chat, "is_forum", False)

        text = (
            f"ℹ️ <b>BOT INFORMATION</b>\n"
            f"{UI.LINE}\n\n"
            f"<b>🤖 Bot</b>\n"
            f"  Name:      CLAT Vision Quiz Bot\n"
            f"  Questions: <b>{q_count}</b>\n"
            f"  Mode:      Polling\n"
            f"  DB:        MongoDB Atlas ✅\n\n"
            f"<b>💬 This Chat</b>\n"
            f"  ID:    <code>{chat.id}</code>\n"
            f"  Type:  <code>{chat.type}</code>\n"
            f"  Forum: <code>{is_forum}</code>\n"
        )
        if thread_id:
            text += f"  Topic: <code>{thread_id}</code>\n"
        text += (
            f"\n{UI.LINE}\n"
            f"<i>CLAT 2027 • @CLAT_Vision</i>"
        )
        await self._reply(update, text)

    # ════════════════════════════════════════════════════════
    #  /quiz
    # ════════════════════════════════════════════════════════

    async def cmd_quiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat      = update.effective_chat
        thread_id = get_thread_id(update)
        track_id  = get_tracking_id(chat.id, thread_id)
        category  = " ".join(context.args).strip() if context.args else ""

        question = self.quiz_manager.get_random_question(
            chat_id=track_id, category=category)

        if not question:
            cat_e = UI.cat_emoji(category)
            text  = (
                f"📭 <b>No Questions Found</b>\n"
                f"{UI.LINE}\n\n"
                + (f"  {cat_e} Category: <b>{category}</b>\n\n" if category else "")
                + "  The question bank is empty!\n\n"
                "  Use /addquiz to add questions."
            )
            await self._reply(update, text, reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Try Again", callback_data="play_quiz")
            ]]))
            return

        options = question.get("options", [])
        if not isinstance(options, list) or len(options) < 2:
            await self._reply(update, "⚠️ Question data error. Try /quiz again.")
            return

        correct_idx = question.get("correct_answer", 0)
        if not isinstance(correct_idx, int) or not (0 <= correct_idx < len(options)):
            correct_idx = 0

        cat       = question.get("category", "General")
        cat_emoji = UI.cat_emoji(cat)
        q_id      = question.get("id")

        poll_kwargs = dict(
            question          = f"{cat_emoji} {question['question']}",
            options           = options,
            type              = Poll.QUIZ,
            correct_option_id = correct_idx,
            is_anonymous      = False,
            open_period       = 30,
            explanation       = (
                f"✅ {options[correct_idx]}\n"
                f"📚 {cat} • 🆔 Q#{q_id}"
            )
        )
        if thread_id:
            poll_kwargs["message_thread_id"] = thread_id

        try:
            poll_msg = await update.effective_message.reply_poll(**poll_kwargs)
            poll_id  = poll_msg.poll.id

            if self.db and q_id:
                self.db.save_poll_mapping(str(poll_id), q_id)

            context.bot_data[f"poll_{poll_id}"] = {
                "question_id":       q_id,
                "question":          question["question"],
                "correct_option_id": correct_idx,
                "chat_id":           chat.id,
                "thread_id":         thread_id,
                "tracking_id":       track_id,
                "category":          cat,
            }

            if self.db and chat.type in ("group", "supergroup"):
                try:
                    self.db.register_group_interaction(
                        chat_id   = chat.id,
                        thread_id = thread_id,
                        title     = chat.title or "",
                        username  = getattr(chat, "username", "") or ""
                    )
                except Exception as eg:
                    logger.error(f"register_group: {eg}")

        except TelegramError as e:
            err = str(e).lower()
            logger.error(f"send_poll error: {e}")
            text = (
                "⚠️ <b>Topic Restricted</b>\n\nThis topic is closed."
                if any(w in err for w in ("topic", "thread", "closed"))
                else f"⚠️ Could not send quiz:\n<code>{e}</code>"
            )
            await self._reply(update, text)

    # ════════════════════════════════════════════════════════
    #  POLL ANSWER HANDLER
    # ════════════════════════════════════════════════════════

    async def handle_poll_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        answer     = update.poll_answer
        user_id    = answer.user.id
        poll_id    = answer.poll_id
        option_ids = answer.option_ids

        data       = context.bot_data.get(f"poll_{poll_id}", {})
        correct_id = data.get("correct_option_id")
        chat_id    = data.get("chat_id", 0)
        thread_id  = data.get("thread_id")
        track_id   = data.get("tracking_id", chat_id)

        if correct_id is None or not option_ids:
            return

        is_correct = (option_ids[0] == correct_id)

        try:
            self.quiz_manager.record_attempt(user_id, is_correct)
            if chat_id and chat_id != user_id:
                self.quiz_manager.record_group_attempt(user_id, chat_id, is_correct)
        except Exception as e:
            logger.error(f"record_attempt: {e}")

        if self.db:
            try:
                self.db.log_activity("quiz_answer",
                    user_id=user_id, chat_id=chat_id,
                    thread_id=thread_id, poll_id=poll_id,
                    is_correct=is_correct,
                    category=data.get("category", ""))
                self.db.upsert_user(user_id, {
                    "user_id":       user_id,
                    "last_seen":     datetime.utcnow().isoformat(),
                    "total_answers": self.quiz_manager.get_score(user_id),
                })
            except Exception as e:
                logger.error(f"DB poll_answer: {e}")

    # ════════════════════════════════════════════════════════
    #  /score
    # ════════════════════════════════════════════════════════

    async def cmd_score(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user    = update.effective_user
        mention = UI.mention(user.id, user.first_name or "User")
        score   = self.quiz_manager.get_score(user.id)
        stats   = self.quiz_manager.get_user_stats(user.id)

        total  = stats.get("total_quizzes", 0)
        rate   = stats.get("success_rate", 0)
        streak = stats.get("current_streak", 0)
        best   = stats.get("longest_streak", 0)
        today  = stats.get("today_quizzes", 0)

        bar          = UI.bar(rate)
        rank_txt, _  = UI.rank(score)

        text = (
            f"🏆 <b>SCORE CARD</b>\n"
            f"{UI.LINE}\n\n"
            f"  👤 {mention}\n"
            f"  {rank_txt}\n\n"
            f"<b>📊 Performance</b>\n"
            f"  ✅ Correct:   <b>{score}</b>\n"
            f"  📝 Attempted: <b>{total}</b>\n"
            f"  ❌ Wrong:     <b>{total - score}</b>\n\n"
            f"<b>🎯 Accuracy</b>\n"
            f"  [{bar}] <b>{rate}%</b>\n\n"
            f"<b>🔥 Streak</b>\n"
            f"  Current: {UI.streak_display(streak)}\n"
            f"  Best:    <b>{best}</b>\n"
            f"  Today:   <b>{today}</b>\n\n"
            f"{UI.LINE}\n"
            f"<i>Keep grinding! 💪</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Play",       callback_data="play_quiz"),
             InlineKeyboardButton("📈 Full Stats",  callback_data="my_stats")],
            [InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")],
        ])
        await self._reply(update, text, reply_markup=kb)

    # ════════════════════════════════════════════════════════
    #  /stats  (personal detailed)
    # ════════════════════════════════════════════════════════

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user    = update.effective_user
        mention = UI.mention(user.id, user.first_name or "User")

        msg = await self._reply(update, "📊 <i>Crunching your numbers...</i>")
        await asyncio.sleep(0.4)

        stats  = self.quiz_manager.get_user_stats(user.id)
        score  = self.quiz_manager.get_score(user.id)
        total  = stats.get("total_quizzes", 0)
        rate   = stats.get("success_rate", 0)
        streak = stats.get("current_streak", 0)
        best   = stats.get("longest_streak", 0)
        today  = stats.get("today_quizzes", 0)
        week   = stats.get("week_quizzes", 0)
        month  = stats.get("month_quizzes", 0)

        acc_bar  = UI.bar(rate)
        w_bar    = UI.bar(min(100, week / 50 * 100))
        rank_txt, grade = UI.rank(score)

        text = (
            f"📈 <b>DETAILED STATS</b>\n"
            f"{UI.LINE}\n\n"
            f"  👤 {mention}\n"
            f"  {rank_txt}  •  Grade <b>{grade}</b>\n\n"

            f"<b>🎯 Accuracy</b>\n"
            f"  [{acc_bar}] <b>{rate}%</b>\n"
            f"  ✅ <b>{score}</b> correct  ❌ <b>{total-score}</b> wrong  📝 <b>{total}</b> total\n\n"

            f"<b>🔥 Streaks</b>\n"
            f"  Current: {UI.streak_display(streak)}\n"
            f"  Best:    <b>{best}</b>\n\n"

            f"<b>📅 Activity</b>\n"
            f"  Today:   <b>{today}</b> quizzes\n"
            f"  Week:    <b>{week}</b>  [{w_bar}]\n"
            f"  Month:   <b>{month}</b>\n\n"

            f"{UI.LINE}\n"
            f"<i>Consistency is the key to CLAT! 🚀</i>"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎯 Play Quiz",   callback_data="play_quiz"),
            InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
        ]])
        if msg:
            await self._edit(msg, text, kb)
        else:
            await self._reply(update, text, reply_markup=kb)

    # ════════════════════════════════════════════════════════
    #  /botstats  (NEW — global quiz analytics)
    # ════════════════════════════════════════════════════════

    async def cmd_botstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await self._reply(update, "📊 <i>Loading bot analytics...</i>")
        await asyncio.sleep(0.4)

        q_total  = len(self.quiz_manager.questions)
        u_total  = 0
        g_total  = 0
        d_quizzes, w_quizzes, m_quizzes, a_quizzes = 0, 0, 0, 0
        d_correct, w_correct, m_correct, a_correct = 0, 0, 0, 0
        d_participants, w_participants = set(), set()

        if self.db:
            try:
                from datetime import timedelta
                now  = datetime.utcnow()
                d_cut = (now - timedelta(days=1)).isoformat()
                w_cut = (now - timedelta(days=7)).isoformat()
                m_cut = (now - timedelta(days=30)).isoformat()

                # Count quiz answers by period
                acts = self.db.activities_col
                d_quizzes = acts.count_documents({"type":"quiz_answer","timestamp":{"$gte":d_cut}})
                w_quizzes = acts.count_documents({"type":"quiz_answer","timestamp":{"$gte":w_cut}})
                m_quizzes = acts.count_documents({"type":"quiz_answer","timestamp":{"$gte":m_cut}})
                a_quizzes = acts.count_documents({"type":"quiz_answer"})

                d_correct = acts.count_documents({"type":"quiz_answer","is_correct":True,"timestamp":{"$gte":d_cut}})
                w_correct = acts.count_documents({"type":"quiz_answer","is_correct":True,"timestamp":{"$gte":w_cut}})
                m_correct = acts.count_documents({"type":"quiz_answer","is_correct":True,"timestamp":{"$gte":m_cut}})
                a_correct = acts.count_documents({"type":"quiz_answer","is_correct":True})

                # Unique participants
                d_participants = set(
                    d["user_id"] for d in acts.find(
                        {"type":"quiz_answer","timestamp":{"$gte":d_cut}},{"user_id":1}))
                w_participants = set(
                    d["user_id"] for d in acts.find(
                        {"type":"quiz_answer","timestamp":{"$gte":w_cut}},{"user_id":1}))

                u_total = self.db.users_col.count_documents({})
                g_total = self.db.groups_col.count_documents({})
            except Exception as e:
                logger.error(f"botstats DB error: {e}")

        def acc(correct, total):
            return f"{round(correct/total*100,1)}%" if total else "—"

        d_bar = UI.bar(d_quizzes / max(w_quizzes, 1) * 100) if w_quizzes else UI.bar(0)
        w_bar = UI.bar(w_quizzes / max(m_quizzes, 1) * 100) if m_quizzes else UI.bar(0)

        text = (
            f"📊 <b>BOT STATISTICS</b>\n"
            f"{UI.LINE}\n\n"

            f"<b>🗄️ Database</b>\n"
            f"  📦 Questions:  <b>{q_total}</b>\n"
            f"  👥 Users:      <b>{u_total}</b>\n"
            f"  💬 Groups:     <b>{g_total}</b>\n\n"

            f"<b>📅 Daily  <i>(last 24h)</i></b>\n"
            f"  [{d_bar}]\n"
            f"  🎯 Attempts:  <b>{d_quizzes}</b>  ✅ Correct: <b>{d_correct}</b>\n"
            f"  🎯 Accuracy:  <b>{acc(d_correct, d_quizzes)}</b>\n"
            f"  👤 Players:   <b>{len(d_participants)}</b>\n\n"

            f"<b>📆 Weekly  <i>(last 7 days)</i></b>\n"
            f"  [{w_bar}]\n"
            f"  🎯 Attempts:  <b>{w_quizzes}</b>  ✅ Correct: <b>{w_correct}</b>\n"
            f"  🎯 Accuracy:  <b>{acc(w_correct, w_quizzes)}</b>\n"
            f"  👤 Players:   <b>{len(w_participants)}</b>\n\n"

            f"<b>🗓️ Monthly  <i>(last 30 days)</i></b>\n"
            f"  🎯 Attempts:  <b>{m_quizzes}</b>  ✅ Correct: <b>{m_correct}</b>\n"
            f"  🎯 Accuracy:  <b>{acc(m_correct, m_quizzes)}</b>\n\n"

            f"<b>🏆 All-Time</b>\n"
            f"  🎯 Attempts:  <b>{a_quizzes}</b>  ✅ Correct: <b>{a_correct}</b>\n"
            f"  🎯 Accuracy:  <b>{acc(a_correct, a_quizzes)}</b>\n\n"

            f"{UI.LINE}\n"
            f"<i>CLAT Vision Quiz Bot Analytics</i>"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎯 Play Quiz", callback_data="play_quiz"),
        ]])
        if msg:
            await self._edit(msg, text, kb)
        else:
            await self._reply(update, text, reply_markup=kb)

    # ════════════════════════════════════════════════════════
    #  /leaderboard
    # ════════════════════════════════════════════════════════

    async def cmd_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat      = update.effective_chat
        thread_id = get_thread_id(update)
        is_group  = chat.type in ("group", "supergroup")

        msg = await self._reply(update, "🏆 <i>Loading leaderboard...</i>")
        await asyncio.sleep(0.4)

        if is_group:
            data         = self.quiz_manager.get_group_leaderboard(chat.id)
            lb           = data.get("leaderboard", [])
            total_q      = data.get("total_quizzes", 0)
            acc_g        = data.get("group_accuracy", 0)
            title_suffix = f" • {(chat.title or 'Group')[:14]}"
            if thread_id: title_suffix += " 🧵"
        else:
            lb           = self.quiz_manager.get_leaderboard()
            total_q      = sum(e.get("total_attempts", 0) for e in lb)
            acc_g        = 0
            title_suffix = ""

        if not lb:
            text = (
                f"🏆 <b>LEADERBOARD{title_suffix}</b>\n"
                f"{UI.LINE}\n\n"
                "  No scores yet — be the first! 🥇\n\n"
                "  Use /quiz to start playing."
            )
            if msg: await self._edit(msg, text)
            return

        top_score = lb[0].get("correct_answers", lb[0].get("score", 1)) or 1
        lines = [
            f"🏆 <b>LEADERBOARD{title_suffix}</b>\n"
            f"{UI.LINE}\n"
        ]

        for i, entry in enumerate(lb[:10]):
            uid   = entry.get("user_id")
            score = entry.get("correct_answers", entry.get("score", 0))
            acc   = entry.get("accuracy", 0)
            medal = UI.MEDALS[i]

            # Inline mention from DB
            display = f"User {str(uid)[-4:]}"
            if self.db:
                try:
                    doc = self.db.users_col.find_one(
                        {"user_id": uid}, {"name": 1, "username": 1})
                    if doc:
                        display = (doc.get("name") or doc.get("username") or display)[:20]
                except Exception:
                    pass
            mention = UI.mention(uid, display)

            fill = max(0, min(5, int(score / top_score * 5)))
            bar  = "▰" * fill + "▱" * (5 - fill)

            lines.append(
                f"{medal} {mention}\n"
                f"   {bar} <b>{score}</b>  <i>{acc}% acc</i>"
            )

        if is_group and total_q > 0:
            lines.append(
                f"\n<b>📊 Group Totals</b>\n"
                f"  Attempts: <b>{total_q}</b>  Accuracy: <b>{acc_g}%</b>"
            )

        lines.append(f"\n{UI.LINE}\n<i>Play /quiz to climb the ranks! 🚀</i>")

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎯 Play Quiz", callback_data="play_quiz"),
            InlineKeyboardButton("📊 My Stats",  callback_data="my_stats"),
        ]])

        text = "\n".join(lines)
        if msg:
            await self._edit(msg, text, kb)
        else:
            await self._reply(update, text, reply_markup=kb)

    # ════════════════════════════════════════════════════════
    #  /addquiz
    # ════════════════════════════════════════════════════════

    async def cmd_addquiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        text  = update.effective_message.text or ""
        raw   = [l.strip() for l in text.strip().split("\n")]
        if raw: raw[0] = raw[0].replace("/addquiz", "").strip()
        lines = [l for l in raw if l]

        USAGE = (
            f"➕ <b>ADD QUIZ QUESTION</b>\n"
            f"{UI.LINE}\n\n"
            "<b>Format:</b>\n"
            "<code>/addquiz\n"
            "Question text\n"
            "Option A\nOption B\nOption C\nOption D\n"
            "Correct (1-4)\n"
            "Category</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/addquiz\n"
            "Which Article abolishes untouchability?\n"
            "Article 14\nArticle 17\nArticle 19\nArticle 21\n"
            "2\nLegal Reasoning</code>"
        )

        if len(lines) < 6:
            await self._reply(update, USAGE)
            return

        question = lines[0]
        options  = lines[1:5]
        try:
            correct = int(lines[5]) - 1
        except (ValueError, IndexError):
            await self._reply(update, "❌ Correct answer must be a number: 1, 2, 3 or 4")
            return

        if not (0 <= correct <= 3):
            await self._reply(update, "❌ Correct answer must be <b>1, 2, 3 or 4</b>")
            return

        category = lines[6].strip() if len(lines) > 6 else "General"
        msg = await self._reply(update, "⏳ <i>Saving to database...</i>")
        await asyncio.sleep(0.4)

        result = self.quiz_manager.add_questions([{
            "question": question, "options": options,
            "correct_answer": correct, "category": category,
        }])

        added = result.get("added", 0)
        dups  = result.get("rejected", {}).get("duplicates", 0)
        total = len(self.quiz_manager.questions)
        mention = UI.mention(user.id, user.first_name or "Admin")

        if added > 0:
            text = (
                f"✅ <b>QUESTION ADDED</b>\n"
                f"{UI.LINE}\n\n"
                f"  Added by {mention}\n\n"
                f"<b>📝 Preview</b>\n"
                f"  {question[:60]}{'…' if len(question)>60 else ''}\n\n"
                f"  A: {options[0]}\n  B: {options[1]}\n"
                f"  C: {options[2]}\n  D: {options[3]}\n\n"
                f"  ✅ Answer: <b>Option {correct+1}</b> — {options[correct]}\n"
                f"  📂 Category: <b>{category}</b>\n\n"
                f"{UI.LINE}\n"
                f"  📦 Total in bank: <b>{total}</b>"
            )
        elif dups:
            text = (
                f"⚠️ <b>DUPLICATE</b>\n"
                f"{UI.LINE}\n\n"
                "  This question already exists.\n"
                "  Use /editquiz to modify it."
            )
        else:
            err = (result.get("errors") or ["Unknown"])[0]
            text = (
                f"❌ <b>FAILED</b>\n"
                f"{UI.LINE}\n\n"
                f"  Error: <code>{err}</code>"
            )

        if msg: await self._edit(msg, text)
        else:   await self._reply(update, text)

    # ════════════════════════════════════════════════════════
    #  /delquiz  — Smart inline button picker
    # ════════════════════════════════════════════════════════

    async def cmd_delquiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        # ── REPLY-TO-POLL detection ────────────────────────────────────────
        # If admin replies to a quiz poll with /delquiz → delete that question
        reply = update.effective_message.reply_to_message
        if reply and reply.poll:
            poll_id = reply.poll.id
            # Try to find Q ID from bot_data first
            poll_data = context.bot_data.get(f"poll_{poll_id}", {})
            q_id      = poll_data.get("question_id")

            # Fallback: check DB poll mapping
            if q_id is None and self.db:
                try:
                    q_id = self.db.get_quiz_id_from_poll(str(poll_id))
                except Exception:
                    pass

            # Fallback: match poll question text against DB
            if q_id is None:
                poll_q = reply.poll.question or ""
                # Strip leading emoji (cat_emoji prefix)
                poll_q_clean = re.sub(r"^\S+\s+", "", poll_q.strip())
                for q in self.quiz_manager.questions:
                    if q.get("question", "").strip() == poll_q_clean.strip():
                        q_id = q.get("id")
                        break

            if q_id is not None:
                mention   = UI.mention(user.id, user.first_name or "Admin")
                q_info    = next((q for q in self.quiz_manager.questions
                                  if q.get("id") == q_id), {})
                q_preview = q_info.get("question", f"#{q_id}")[:50]

                msg = await self._reply(update, f"🗑️ <i>Deleting Q#{q_id}...</i>")
                await asyncio.sleep(0.3)
                success = self.quiz_manager.delete_question_by_db_id(q_id)

                if success:
                    remaining = len(self.quiz_manager.questions)
                    text = (
                        f"✅ <b>DELETED</b>\n"
                        f"{UI.LINE}\n\n"
                        f"  By {mention}\n"
                        f"  <code>#{q_id}</code> — {q_preview}…\n\n"
                        f"  📦 Remaining: <b>{remaining}</b> questions"
                    )
                else:
                    text = (
                        f"❌ <b>Not Found</b>\n"
                        f"{UI.LINE}\n\n"
                        f"  Q#{q_id} not found in database."
                    )
                if msg:
                    await self._edit(msg, text)
                return
            else:
                # Could not identify the question
                await self._reply(update,
                    f"⚠️ <b>Cannot identify question</b>\n"
                    f"{UI.LINE}\n\n"
                    "  Could not match this poll to any question.\n"
                    "  Use /delquiz without reply to pick from list."
                )
                return
        # ── End reply-to-poll detection ────────────────────────────────────

        questions = self.quiz_manager.questions
        if not questions:
            await self._reply(update,
                f"📭 <b>No Questions</b>\n{UI.LINE}\n\nDatabase is empty.")
            return

        page = 0
        self._del_page[user.id] = page
        await self._reply(
            update,
            self._delquiz_text(questions, page),
            reply_markup=self._delquiz_kb(questions, page, user.id)
        )

    def _delquiz_text(self, questions: list, page: int) -> str:
        total = len(questions)
        per   = 8
        start = page * per
        end   = min(start + per, total)
        pages = (total + per - 1) // per

        lines = [
            f"🗑️ <b>DELETE QUESTION</b>\n"
            f"{UI.LINE}\n"
            f"  Page <b>{page+1}</b> / <b>{pages}</b>  •  Total: <b>{total}</b>\n"
            f"{UI.LINE}\n\n"
            f"Tap a question to delete it:\n"
        ]
        for q in questions[start:end]:
            qid   = q.get("id", "?")
            qtext = q.get("question", "")[:38]
            cat   = q.get("category", "General")
            emoji = UI.cat_emoji(cat)
            lines.append(f"  {emoji} <code>#{qid}</code>  {qtext}{'…' if len(q.get('question',''))>38 else ''}")

        return "\n".join(lines)

    def _delquiz_kb(self, questions: list, page: int, user_id: int) -> InlineKeyboardMarkup:
        per   = 8
        start = page * per
        total = len(questions)
        pages = (total + per - 1) // per
        rows  = []

        # Question buttons — 2 per row
        chunk = questions[start:start+per]
        for i in range(0, len(chunk), 2):
            row = []
            for q in chunk[i:i+2]:
                qid   = q.get("id", "?")
                qtext = q.get("question", "")[:18]
                row.append(InlineKeyboardButton(
                    f"🗑 #{qid} {qtext}…",
                    callback_data=f"dq_del_{qid}_{user_id}"
                ))
            rows.append(row)

        # Navigation
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"dq_page_{page-1}_{user_id}"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton("Next ▶", callback_data=f"dq_page_{page+1}_{user_id}"))
        if nav:
            rows.append(nav)

        rows.append([InlineKeyboardButton("❌ Cancel", callback_data=f"dq_cancel_{user_id}")])
        return InlineKeyboardMarkup(rows)

    async def _cb_delquiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data  = query.data  # dq_del_ID_UID | dq_page_N_UID | dq_cancel_UID
        actor = query.from_user

        parts = data.split("_")
        action = parts[1]  # del | page | cancel

        # Security: only the user who invoked /delquiz can interact
        try:
            owner_uid = int(parts[-1])
        except (ValueError, IndexError):
            owner_uid = 0
        if actor.id != owner_uid:
            await query.answer("❌ Not your menu!", show_alert=True)
            return

        questions = self.quiz_manager.questions

        if action == "cancel":
            try: await query.message.delete()
            except Exception: pass
            return

        if action == "page":
            page = int(parts[2])
            self._del_page[actor.id] = page
            try:
                await query.message.edit_text(
                    self._delquiz_text(questions, page),
                    parse_mode=ParseMode.HTML,
                    reply_markup=self._delquiz_kb(questions, page, actor.id)
                )
            except Exception:
                pass
            return

        if action == "del":
            qid = int(parts[2])
            # Find question text for confirmation message
            q_info = next((q for q in questions if q.get("id") == qid), None)
            q_preview = q_info.get("question", "")[:50] if q_info else f"#{qid}"

            success = self.quiz_manager.delete_question_by_db_id(qid)
            mention = UI.mention(actor.id, actor.first_name or "Admin")

            if success:
                remaining = len(self.quiz_manager.questions)
                text = (
                    f"✅ <b>DELETED</b>\n"
                    f"{UI.LINE}\n\n"
                    f"  Deleted by {mention}\n"
                    f"  <code>#{qid}</code> — {q_preview}…\n\n"
                    f"  📦 Remaining: <b>{remaining}</b> questions"
                )
                try:
                    await query.message.edit_text(text, parse_mode=ParseMode.HTML)
                except Exception:
                    pass
            else:
                try:
                    await query.message.edit_text(
                        f"❌ <b>Not Found</b>\n{UI.LINE}\n\nQuestion #{qid} not found.",
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass

    # ════════════════════════════════════════════════════════
    #  /editquiz
    # ════════════════════════════════════════════════════════

    async def cmd_editquiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        if self._dev and hasattr(self._dev, "editquiz"):
            await self._dev.editquiz(update, context)
            return

        msg = await self._reply(update, "📋 <i>Loading question bank...</i>")
        await asyncio.sleep(0.3)

        questions = self.quiz_manager.questions
        if not questions:
            text = (
                f"📭 <b>EMPTY BANK</b>\n"
                f"{UI.LINE}\n\n"
                "  No questions in database.\n"
                "  Use /addquiz to add some."
            )
            if msg: await self._edit(msg, text)
            return

        total = len(questions)
        lines = [
            f"📋 <b>QUESTION BANK</b>  ({total} total)\n"
            f"{UI.LINE}\n"
        ]

        for q in questions[:20]:
            qid   = q.get("id", "?")
            qtext = q.get("question", "")[:42]
            cat   = q.get("category", "General")
            emoji = UI.cat_emoji(cat)
            lines.append(
                f"  {emoji} <code>#{qid}</code>  {qtext}"
                + ("…" if len(q.get("question", "")) > 42 else "")
            )

        if total > 20:
            lines.append(f"\n  <i>…and {total-20} more</i>")

        lines.append(
            f"\n{UI.LINE}\n"
            f"  /delquiz — Smart delete\n"
            f"  /addquiz — Add question\n"
            f"  /reload  — Sync from DB"
        )

        if msg: await self._edit(msg, "\n".join(lines))

    # ════════════════════════════════════════════════════════
    #  /dev
    # ════════════════════════════════════════════════════════

    async def cmd_dev(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        if self._dev and hasattr(self._dev, "dev"):
            await self._dev.dev(update, context)
            return

        msg = await self._reply(update, "🛠️ <i>Loading dev panel...</i>")
        await asyncio.sleep(0.3)

        mention = UI.mention(user.id, user.first_name or "Dev")
        q_count = len(self.quiz_manager.questions)
        chats   = len(self.quiz_manager.active_chats)
        users, groups = 0, 0
        if self.db:
            try:
                users  = len(self.db.get_all_users_stats())
                groups = len(self.db.get_all_groups())
            except Exception:
                pass

        text = (
            f"🛠️ <b>DEVELOPER PANEL</b>\n"
            f"{UI.LINE}\n\n"
            f"  👤 {mention}\n\n"
            f"<b>📊 Live Stats</b>\n"
            f"  📦 Questions:    <b>{q_count}</b>\n"
            f"  👥 Users:        <b>{users}</b>\n"
            f"  💬 Groups:       <b>{groups}</b>\n"
            f"  🟢 Active Chats: <b>{chats}</b>\n\n"
            f"<b>⚡ Commands</b>\n"
            f"  /addquiz  /delquiz  /editquiz\n"
            f"  /broadcast  /reload  /restart\n"
            f"  /botstats  /devstats  /activity\n"
            f"  /performance\n\n"
            f"{UI.LINE}\n"
            f"  Owner ID: <code>{OWNER_ID}</code>"
        )
        if msg: await self._edit(msg, text)

    # ════════════════════════════════════════════════════════
    #  /broadcast
    # ════════════════════════════════════════════════════════

    async def cmd_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not self._is_owner(user.id):
            await self._unauthorized(update)
            return

        if self._dev and hasattr(self._dev, "broadcast"):
            await self._dev.broadcast(update, context)
            return

        raw = (update.effective_message.text or "").replace("/broadcast","").replace("/bc","").strip()

        if not raw:
            text = (
                f"📡 <b>BROADCAST</b>\n"
                f"{UI.LINE}\n\n"
                "<b>Usage:</b>\n"
                "  <code>/broadcast Your message</code>\n\n"
                "Supports HTML: <code>&lt;b&gt;</code> <code>&lt;i&gt;</code> <code>&lt;code&gt;</code>\n"
                "Alias: /bc"
            )
            await self._reply(update, text)
            return

        if not self.db:
            await self._reply(update, "❌ Database not available.")
            return

        users  = self.db.get_pm_accessible_users()
        groups = self.db.get_all_groups()
        total  = len(users) + len(groups)
        mention = UI.mention(user.id, user.first_name or "Owner")

        status = await self._reply(update,
            f"📡 <b>Broadcasting...</b>\n"
            f"{UI.LINE}\n\n"
            f"  Initiated by {mention}\n"
            f"  👥 Users:  <b>{len(users)}</b>\n"
            f"  💬 Groups: <b>{len(groups)}</b>\n"
            f"  📨 Total:  <b>{total}</b>\n\n"
            f"<i>Please wait...</i>"
        )

        sent, failed = 0, 0
        for u in users:
            try:
                await context.bot.send_message(
                    chat_id=u["user_id"], text=raw, parse_mode=ParseMode.HTML)
                sent += 1
                await asyncio.sleep(0.05)
            except (Forbidden, BadRequest):
                failed += 1
            except Exception as e:
                logger.error(f"BC user {u['user_id']}: {e}")
                failed += 1

        for g in groups:
            tid = g.get("message_thread_id")
            try:
                kwargs = {"chat_id": g["chat_id"], "text": raw, "parse_mode": ParseMode.HTML}
                if tid: kwargs["message_thread_id"] = tid
                await context.bot.send_message(**kwargs)
                sent += 1
                await asyncio.sleep(0.05)
            except TelegramError as e:
                if any(w in str(e).lower() for w in ("topic","closed","thread")):
                    try:
                        await context.bot.send_message(
                            chat_id=g["chat_id"], text=raw, parse_mode=ParseMode.HTML)
                        sent += 1
                    except Exception:
                        failed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"BC group {g.get('chat_id')}: {e}")
                failed += 1

        rate = int(sent / total * 100) if total else 0
        if status:
            await self._edit(status,
                f"✅ <b>BROADCAST COMPLETE</b>\n"
                f"{UI.LINE}\n\n"
                f"  📤 Sent:    <b>{sent}</b>\n"
                f"  ❌ Failed:  <b>{failed}</b>\n"
                f"  📊 Rate:    [{UI.bar(rate)}] <b>{rate}%</b>"
            )

    # ════════════════════════════════════════════════════════
    #  /reload
    # ════════════════════════════════════════════════════════

    async def cmd_reload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        mention = UI.mention(user.id, user.first_name or "Admin")
        msg = await self._reply(update, "🔄 <i>Syncing from MongoDB...</i>")
        await asyncio.sleep(0.4)

        try:
            old = len(self.quiz_manager.questions)
            self.quiz_manager.reload_data()
            new  = len(self.quiz_manager.questions)
            diff = new - old
            text = (
                f"✅ <b>RELOAD COMPLETE</b>\n"
                f"{UI.LINE}\n\n"
                f"  By {mention}\n\n"
                f"  📦 Questions: <b>{new}</b>  "
                f"({'<b>+'+str(diff)+'</b>' if diff>=0 else '<b>'+str(diff)+'</b>'})\n"
                f"  🗄️  Source: MongoDB Atlas\n"
                f"  ⚡ Cache refreshed!"
            )
        except Exception as e:
            text = (
                f"❌ <b>RELOAD FAILED</b>\n"
                f"{UI.LINE}\n\n"
                f"  Error: <code>{e}</code>"
            )
        if msg: await self._edit(msg, text)

    # ════════════════════════════════════════════════════════
    #  /restart
    # ════════════════════════════════════════════════════════

    async def cmd_restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not self._is_owner(user.id):
            await self._unauthorized(update)
            return

        mention = UI.mention(user.id, user.first_name or "Owner")
        await self._reply(update,
            f"🔄 <b>RESTARTING</b>\n"
            f"{UI.LINE}\n\n"
            f"  Initiated by {mention}\n"
            f"  ⏳ Shutting down gracefully...\n"
            f"  ✅ Back online in seconds!"
        )
        import sys
        os.makedirs("data", exist_ok=True)
        open("data/.restart_flag", "w").close()
        await asyncio.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)


    # ════════════════════════════════════════════════════════
    #  /importquiz  — usage hint
    # ════════════════════════════════════════════════════════

    async def cmd_importquiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        text = (
            f"📥 <b>BULK IMPORT</b>\n"
            f"{UI.LINE}\n\n"
            f"Just send a <b>.txt file</b> to this chat!\n\n"
            f"<b>✅ Auto-detected formats:</b>\n"
            f"  • Numbered questions (1. / Q1:)\n"
            f"  • A) B) C) D) options\n"
            f"  • Answer: B / Ans: 2 / Correct: C\n"
            f"  • Inline options on same line\n"
            f"  • Asterisk * to mark correct answer\n\n"
            f"<b>📌 No fixed format required</b>\n"
            f"  The bot auto-detects the structure.\n\n"
            f"<b>Protection:</b>\n"
            f"  ✅ Duplicate detection\n"
            f"  ✅ Validation\n"
            f"  ✅ Auto category tagging\n\n"
            f"{UI.LINE}\n"
            f"<i>Send your .txt file now →</i>"
        )
        await self._reply(update, text)

    # ════════════════════════════════════════════════════════
    #  DOCUMENT HANDLER — Bulk .txt import
    # ════════════════════════════════════════════════════════

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user

        # Only authorized users
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        doc = update.effective_message.document
        if not doc:
            return

        mention = UI.mention(user.id, user.first_name or "Admin")

        # Only accept .txt files
        fname = doc.file_name or ""
        is_txt = (
            fname.lower().endswith(".txt") or
            (doc.mime_type or "").startswith("text/")
        )
        if not is_txt:
            await self._reply(update,
                f"⚠️ <b>Wrong File Type</b>\n"
                f"{UI.LINE}\n\n"
                f"  Please send a <b>.txt</b> file.\n"
                f"  Use /importquiz to see the format guide."
            )
            return

        # File size guard (max 2MB)
        if doc.file_size and doc.file_size > 2 * 1024 * 1024:
            await self._reply(update,
                f"❌ <b>File Too Large</b>\n"
                f"{UI.LINE}\n\n"
                f"  Max size: 2MB.\n"
                f"  Split into smaller files."
            )
            return

        # Step 1 — Show progress
        msg = await self._reply(update,
            f"📥 <b>IMPORTING</b>\n"
            f"{UI.LINE}\n\n"
            f"  By {mention}\n"
            f"  📄 File: <code>{fname}</code>\n"
            f"  Size:   <code>{doc.file_size or 0:,} bytes</code>\n\n"
            f"  ⏳ Detecting quizzes..."
        )

        # Step 2 — Download file
        try:
            file_obj = await context.bot.get_file(doc.file_id, read_timeout=60, write_timeout=60, connect_timeout=60)
            raw_bytes = await file_obj.download_as_bytearray(read_timeout=60)
        except Exception as e:
            logger.error(f"File download error: {e}")
            if msg:
                await self._edit(msg,
                    f"❌ <b>Download Failed</b>\n"
                    f"{UI.LINE}\n\n"
                    f"  Error: <code>{e}</code>"
                )
            return

        # Step 3 — Decode text (try UTF-8 then latin-1)
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw_bytes.decode("latin-1")
            except Exception as e:
                if msg:
                    await self._edit(msg,
                        f"❌ <b>Cannot Read File</b>\n"
                        f"{UI.LINE}\n\n"
                        f"  Save as UTF-8 and retry."
                    )
                return

        # Step 4 — Parse & validate
        if msg:
            await self._edit(msg,
                f"📥 <b>IMPORTING</b>\n"
                f"{UI.LINE}\n\n"
                f"  By {mention}\n"
                f"  📄 <code>{fname}</code>\n\n"
                f"  🔍 Analyzing {len(text.splitlines())} lines..."
            )

        # Step 5 — Bulk import
        try:
            from src.bot.quiz_parser import bulk_import
            result = bulk_import(text, self.quiz_manager)
        except Exception as e:
            logger.error(f"bulk_import error: {e}")
            if msg:
                await self._edit(msg,
                    f"❌ <b>Import Failed</b>\n"
                    f"{UI.LINE}\n\n"
                    f"  Error: <code>{e}</code>"
                )
            return

        # Step 6 — Show summary
        detected = result.get("total_detected", 0)
        imported = result.get("imported", 0)
        skipped  = result.get("skipped", 0)
        failed   = result.get("failed", 0)
        errors   = result.get("errors", [])
        total_q  = len(self.quiz_manager.questions)

        rate     = int(imported / max(detected, 1) * 100)
        bar      = UI.bar(rate)

        text_out = (
            f"📊 <b>IMPORT SUMMARY</b>\n"
            f"{UI.LINE}\n\n"
            f"  By {mention}\n"
            f"  📄 <code>{fname}</code>\n\n"
            f"  🔍 Detected:  <b>{detected}</b>\n"
            f"  ✅ Imported:  <b>{imported}</b>\n"
            f"  ⚠️ Skipped:   <b>{skipped}</b>  <i>(dupes/incomplete)</i>\n"
            f"  ❌ Failed:    <b>{failed}</b>\n\n"
            f"  [{bar}] <b>{rate}%</b> success\n\n"
            f"  📦 Total in DB: <b>{total_q}</b>\n"
        )
        if errors:
            text_out += f"\n<b>⚠️ Errors (first {len(errors)}):</b>\n"
            for err in errors[:3]:
                text_out += f"  <code>{str(err)[:60]}</code>\n"

        text_out += f"\n{UI.LINE}\n<i>Use /quiz to test your new questions!</i>"

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎯 Play Quiz", callback_data="play_quiz"),
        ]])
        if msg:
            await self._edit(msg, text_out, kb)
        else:
            await self._reply(update, text_out, reply_markup=kb)

    # ════════════════════════════════════════════════════════
    #  CALLBACK HANDLER
    # ════════════════════════════════════════════════════════

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data  = query.data

        if   data == "play_quiz":   await self.cmd_quiz(update, context)
        elif data == "leaderboard": await self.cmd_leaderboard(update, context)
        elif data == "my_stats":    await self.cmd_stats(update, context)
        elif data == "help":        await self.cmd_help(update, context)
        elif data == "back_start":  await self.cmd_start(update, context)
