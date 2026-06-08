"""
CLAT VISION QUIZ BOT — PREMIUM HANDLER ENGINE
Ultra-premium redesign: modern, elegant, professional.
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
OWNER_ID   = int(os.environ.get("OWNER_ID", "8403136097"))
OWNER_NAME = "🌷 𝐂𝐋𝐀𝐓 𝐎𝐖𝐍𝐄𝐑 🌷"
COMMUNITY  = "@CLAT_Vision"


# ══════════════════════════════════════════════════════════════
#  PREMIUM DESIGN SYSTEM
# ══════════════════════════════════════════════════════════════

class UI:
    """Central design token system — all visual constants live here."""

    LINE  = "━" * 30
    THIN  = "─" * 26
    DOT   = "·"

    # ── Progress bars ─────────────────────────────────────────
    @staticmethod
    def bar(pct: float, width: int = 10) -> str:
        """Legacy bar — used for leaderboard entry mini-bars only."""
        filled = max(0, min(width, int(float(pct) / 100 * width)))
        return "█" * filled + "░" * (width - filled)

    @staticmethod
    def pbar(pct: float, width: int = 10) -> str:
        """Premium colored progress bar — standard across all user screens."""
        filled = max(1, min(width, int(float(pct) / 100 * width)))
        return "🟩" * filled + "⬜" * (width - filled)

    @staticmethod
    def xpbar(pct: float, width: int = 10) -> str:
        """Blue XP bar to distinguish from accuracy bar."""
        filled = max(1, min(width, int(float(pct) / 100 * width)))
        return "🟦" * filled + "⬜" * (width - filled)

    @staticmethod
    def mini_bar(pct: float, width: int = 5) -> str:
        filled = max(0, min(width, int(float(pct) / 100 * width)))
        return "▰" * filled + "▱" * (width - filled)

    # ── Rank tier system (based on correct answers) ───────────
    @staticmethod
    def rank(score: int) -> tuple:
        """Returns (rank_label, grade_letter)."""
        if   score >= 500: return "👑 LEGEND",   "S"
        elif score >= 200: return "🔱 MASTER",   "A+"
        elif score >= 100: return "⚔️  EXPERT",  "A"
        elif score >= 50:  return "🎯 ADVANCED", "B"
        elif score >= 20:  return "📈 RISING",   "C"
        elif score >= 5:   return "🌱 BEGINNER", "D"
        else:              return "🎲 ROOKIE",   "E"

    # ── XP Level system (score × 10 = XP) ────────────────────
    @staticmethod
    def level(score: int) -> str:
        xp = score * 10
        if   xp >= 10000: return "💠 Legendary"
        elif xp >= 5000:  return "💎 Diamond"
        elif xp >= 2500:  return "🔷 Platinum"
        elif xp >= 1000:  return "🥇 Gold"
        elif xp >= 500:   return "🥈 Silver"
        else:             return "🥉 Bronze"

    @staticmethod
    def xp_bar(score: int) -> str:
        """Show progress within current XP level as blue bar."""
        breakpoints = [0, 50, 100, 250, 500, 1000]
        for i, bp in enumerate(breakpoints):
            if score < bp:
                prev = breakpoints[i - 1] if i > 0 else 0
                pct  = (score - prev) / (bp - prev) * 100 if bp > prev else 100
                return UI.xpbar(pct)
        return "🟦" * 10

    # ── Medal & ranking display ───────────────────────────────
    MEDALS = ["🥇", "🥈", "🥉"] + ["🏅"] * 20

    @staticmethod
    def rank_badge(pos: int) -> str:
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        return medals.get(pos, f"  {pos}.")

    # ── Category system ───────────────────────────────────────
    CATS = {
        "gk":          ("🌍",  "General Knowledge"),
        "current":     ("📰",  "Current Affairs"),
        "static":      ("📚",  "Static GK"),
        "science":     ("🔬",  "Science & Technology"),
        "history":     ("📜",  "History"),
        "geography":   ("🗺",  "Geography"),
        "economics":   ("💰",  "Economics"),
        "polity":      ("🏛️",  "Political Science"),
        "political":   ("🏛️",  "Political Science"),
        "constitution":("⚖️",  "Constitution & Law"),
        "legal":       ("⚖️",  "Constitution & Law"),
        "arts":        ("🎭",  "Arts & Literature"),
        "literature":  ("🎭",  "Arts & Literature"),
        "sports":      ("🎮",  "Sports & Games"),
        "english":     ("📖",  "English Language"),
        "math":        ("🔢",  "Mathematics"),
        "reasoning":   ("🧠",  "Logical Reasoning"),
        "default":     ("📚",  "General"),
    }

    # Ordered display list for /categories screen
    CATS_DISPLAY = [
        ("🌍", "General Knowledge",    "gk"),
        ("📰", "Current Affairs",      "current"),
        ("📚", "Static GK",            "static"),
        ("🔬", "Science & Technology", "science"),
        ("📜", "History",              "history"),
        ("🗺", "Geography",            "geography"),
        ("💰", "Economics",            "economics"),
        ("🏛️", "Political Science",    "polity"),
        ("⚖️",  "Constitution & Law",  "constitution"),
        ("🎭", "Arts & Literature",    "arts"),
        ("🎮", "Sports & Games",       "sports"),
        ("📖", "English Language",     "english"),
        ("🧠", "Logical Reasoning",    "reasoning"),
        ("🔢", "Mathematics",          "math"),
    ]

    @staticmethod
    def cat_emoji(cat: str) -> str:
        cat_lower = (cat or "").lower()
        for k, (emoji, _) in UI.CATS.items():
            if k in cat_lower:
                return emoji
        return UI.CATS["default"][0]

    # ── Inline mention ────────────────────────────────────────
    @staticmethod
    def mention(user_id: int, name: str) -> str:
        safe = name.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        return f'<a href="tg://user?id={user_id}">{safe}</a>'

    # ── Streak display ────────────────────────────────────────
    @staticmethod
    def streak_display(n: int) -> str:
        if n == 0:
            return "— No streak yet"
        fires = "🔥" * min(n, 5)
        suffix = " 🔥" if n > 5 else ""
        return f"{fires}{suffix} <b>{n} days</b>"

    # ── Number formatter ──────────────────────────────────────
    @staticmethod
    def fmt_num(n: int) -> str:
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000:     return f"{n/1_000:.1f}K"
        return str(n)

    # ── Achievement system ────────────────────────────────────
    ACHIEVEMENTS = [
        ("first_quiz",   "🌟", "First Step",       "Answered your first quiz",      lambda s,st,a,t: t >= 1),
        ("score_10",     "🌱", "Getting Started",  "10 correct answers",             lambda s,st,a,t: s >= 10),
        ("score_50",     "📈", "Rising Star",      "50 correct answers",             lambda s,st,a,t: s >= 50),
        ("score_100",    "⚔️",  "Expert",           "100 correct answers",            lambda s,st,a,t: s >= 100),
        ("score_250",    "🔱", "Master",            "250 correct answers",            lambda s,st,a,t: s >= 250),
        ("score_500",    "👑", "Legend",            "500 correct answers",            lambda s,st,a,t: s >= 500),
        ("streak_3",     "🔥", "On Fire",           "3-day answer streak",            lambda s,st,a,t: st >= 3),
        ("streak_7",     "💫", "Week Warrior",      "7-day streak",                   lambda s,st,a,t: st >= 7),
        ("streak_30",    "⚡", "Lightning",         "30-day streak",                  lambda s,st,a,t: st >= 30),
        ("accuracy_80",  "🎯", "Sharp Shooter",    "80%+ accuracy (20+ questions)",  lambda s,st,a,t: a >= 80 and t >= 20),
        ("perfect_10",   "💎", "Perfect Ten",      "100% on first 10 questions",     lambda s,st,a,t: a >= 100 and t >= 10),
    ]

    @staticmethod
    def get_achievements(score: int, streak: int, accuracy: float, total: int):
        earned, locked = [], []
        for key, icon, name, desc, check in UI.ACHIEVEMENTS:
            if check(score, streak, accuracy, total):
                earned.append((icon, name, desc))
            else:
                locked.append((icon, name, desc))
        return earned, locked


# ══════════════════════════════════════════════════════════════
#  FORUM / TOPIC HELPERS
# ══════════════════════════════════════════════════════════════

def get_thread_id(update: Update) -> Optional[int]:
    msg = update.effective_message
    if msg and getattr(msg, "is_topic_message", False):
        return msg.message_thread_id
    return None

def get_tracking_id(chat_id: int, thread_id: Optional[int]) -> int:
    return int(f"{abs(chat_id)}{thread_id}") if thread_id else chat_id


# ══════════════════════════════════════════════════════════════
#  MAIN BOT CLASS
# ══════════════════════════════════════════════════════════════

class TelegramQuizBot:

    def __init__(self, quiz_manager, db_manager=None):
        from src.core.quiz_cleanup import QuizCleanupManager
        self.quiz_manager             = quiz_manager
        self.db                       = db_manager
        self.application: Optional[Application] = None
        self._dev                     = None
        self._del_page: dict          = {}
        # Leaderboard page cache: key → (timestamp, ranked_list)
        self._lb_cache: dict          = {}
        self._lb_cache_ttl            = 60  # seconds
        # Centralized single-active-quiz cleanup manager (shared by all paths)
        self.cleanup                  = QuizCleanupManager(db_manager)

    # ─── Initialization ──────────────────────────────────────

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

        # User commands
        app.add_handler(CommandHandler("start",       self.cmd_start))
        app.add_handler(CommandHandler("help",        self.cmd_help))
        app.add_handler(CommandHandler("quiz",        self.cmd_quiz))
        app.add_handler(CommandHandler("q",           self.cmd_quiz))
        app.add_handler(CommandHandler("score",       self.cmd_score))
        app.add_handler(CommandHandler("stats",       self.cmd_stats))
        app.add_handler(CommandHandler("botstats",    self.cmd_botstats))
        app.add_handler(CommandHandler("leaderboard",  self.cmd_leaderboard))
        app.add_handler(CommandHandler("lb",           self.cmd_leaderboard))
        app.add_handler(CommandHandler("achievements", self.cmd_achievements))
        app.add_handler(CommandHandler("categories",   self.cmd_categories))
        app.add_handler(CommandHandler("ping",        self.cmd_ping))
        app.add_handler(CommandHandler("info",        self.cmd_info))

        # Admin commands
        app.add_handler(CommandHandler("addquiz",     self.cmd_addquiz))
        app.add_handler(CommandHandler("importquiz",  self.cmd_importquiz))
        app.add_handler(CommandHandler("delquiz",     self.cmd_delquiz))
        app.add_handler(CommandHandler("editquiz",    self.cmd_editquiz))
        app.add_handler(CommandHandler("dev",         self.cmd_dev))
        app.add_handler(CommandHandler("broadcast",    self.cmd_broadcast))
        app.add_handler(CommandHandler("bc",           self.cmd_broadcast))
        app.add_handler(CommandHandler("delbroadcast", self.cmd_delbroadcast))
        app.add_handler(CommandHandler("reload",      self.cmd_reload))
        app.add_handler(CommandHandler("restart",     self.cmd_restart))

        # Poll + Callbacks
        app.add_handler(PollAnswerHandler(self.handle_poll_answer))
        app.add_handler(CallbackQueryHandler(self._cb_delquiz, pattern=r"^dq_"))
        app.add_handler(CallbackQueryHandler(
            self._handle_inline_quiz_answer, pattern=r"^aq_ans_"))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        app.add_error_handler(self._error_handler)

        # Bulk import: .txt file
        app.add_handler(MessageHandler(
            filters.Document.TXT | filters.Document.TEXT,
            self.handle_document))

        # Dev module
        try:
            from src.bot.dev_commands import DeveloperCommands
            if self.db:
                self._dev = DeveloperCommands(self.db, self.quiz_manager)
                app.add_handler(CommandHandler("devstats",           self._dev.devstats))
                app.add_handler(CommandHandler("activity",           self._dev.activity))
                app.add_handler(CommandHandler("performance",        self._dev.performance_stats))
                app.add_handler(CommandHandler("broadcast_confirm",  self._dev.broadcast_confirm))
                app.add_handler(CommandHandler("delbroadcast",       self._dev.delbroadcast))
                app.add_handler(CommandHandler("delbroadcast_confirm", self._dev.delbroadcast_confirm))
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
                BotCommand("botstats",    "📊 Bot-wide statistics"),
                BotCommand("leaderboard", "🔱 Global leaderboard"),
                BotCommand("help",        "📖 Command center"),
                BotCommand("start",       "🚀 Welcome screen"),
                BotCommand("ping",        "🏓 Connection test"),
            ])
        except Exception as e:
            logger.warning(f"set_my_commands: {e}")

    # ─── Core helpers ─────────────────────────────────────────

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

    async def _edit(self, msg, text: str, reply_markup=None) -> bool:
        """Safe message edit. Returns True on success, False on failure."""
        try:
            kwargs = {"parse_mode": ParseMode.HTML}
            if reply_markup:
                kwargs["reply_markup"] = reply_markup
            await msg.edit_text(text, **kwargs)
            return True
        except Exception as e:
            if "not modified" in str(e).lower():
                return True  # identical content — treat as success, no spam
            logger.error(f"_edit error: {e}")
            return False

    async def _unauthorized(self, update: Update):
        user    = update.effective_user
        mention = UI.mention(user.id, user.first_name or "User")
        text = (
            f"🔒  <b>𝐀𝐂𝐂𝐄𝐒𝐒  𝐃𝐄𝐍𝐈𝐄𝐃</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  {mention}\n"
            f"│  This command requires admin access.\n"
            f"╰──────────────────────────────────────╯\n\n"
            f"  <i>Contact {COMMUNITY} for access.</i>"
        )
        await self._reply(update, text)

    def _get_user_rank_position(self, user_id: int) -> Optional[int]:
        """Return global rank position (1-indexed) or None."""
        try:
            lb = self.quiz_manager.get_leaderboard(limit=200)
            for i, entry in enumerate(lb):
                if entry.get("user_id") == user_id:
                    return i + 1
        except Exception:
            pass
        return None

    # ─── /start ──────────────────────────────────────────────

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user    = update.effective_user
        name    = user.first_name or "Student"
        mention = UI.mention(user.id, name)
        is_pm   = update.effective_chat.type == "private"

        # 5-frame emoji animation (PM only)
        if is_pm:
            msg = await self._reply(update, "✨")
            await asyncio.sleep(0.22)
            await self._edit(msg, "✨  🌟  ✨")
            await asyncio.sleep(0.25)
            await self._edit(msg, "🎓  <b>𝐂𝐋𝐀𝐓 𝐕𝐈𝐒𝐈𝐎𝐍</b>  🎓")
            await asyncio.sleep(0.30)
            await self._edit(msg,
                "╔══════════════════════════════════════════════╗\n"
                "║          🎓  <b>𝐂𝐋𝐀𝐓  𝐕𝐈𝐒𝐈𝐎𝐍</b>  🎓              ║\n"
                "║          ✦  <b>𝐐𝐔𝐈𝐙  𝐀𝐂𝐀𝐃𝐄𝐌𝐘</b>  ✦              ║\n"
                "╚══════════════════════════════════════════════╝\n\n"
                "  <i>✦  Loading your dashboard…  ✦</i>"
            )
            await asyncio.sleep(0.42)
        else:
            msg = None

        # Fetch stats
        score   = self.quiz_manager.get_score(user.id)
        stats   = self.quiz_manager.get_user_stats(user.id)
        q_count = len(self.quiz_manager.questions)

        streak  = stats.get("current_streak", 0)
        rate    = stats.get("success_rate", 0)
        total_q = stats.get("total_quizzes", 0)
        correct = stats.get("correct_answers", 0)
        wrong   = max(0, total_q - correct)

        rank_txt, grade = UI.rank(score)
        level_txt       = UI.level(score)
        rank_pos        = self._get_user_rank_position(user.id)
        rank_line       = f"#{rank_pos} Global" if rank_pos else "Not Ranked Yet"

        streak_d = f"{streak} Days" if streak > 0 else "0 Days"

        if is_pm:
            text = (
                f"╔══════════════════════════════════════════════╗\n"
                f"║          🎓  <b>𝐂𝐋𝐀𝐓  𝐕𝐈𝐒𝐈𝐎𝐍</b>  🎓              ║\n"
                f"║          ✦  <b>𝐐𝐔𝐈𝐙  𝐀𝐂𝐀𝐃𝐄𝐌𝐘</b>  ✦              ║\n"
                f"╚══════════════════════════════════════════════╝\n\n"
                f"🌟  <b>Welcome Back,</b>  {mention}  🌟\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🏆  <b>𝐏𝐑𝐎𝐅𝐈𝐋𝐄  𝐃𝐀𝐒𝐇𝐁𝐎𝐀𝐑𝐃</b>\n\n"
                f"╭──────────────────────────────────────────────╮\n"
                f"│  🎖  <b>Rank</b>              :  <b>{rank_txt}  •  {grade}</b>\n"
                f"│  🌍  <b>Global Position</b> :  <b>{rank_line}</b>\n"
                f"│  📈  <b>Level</b>             :  <b>{level_txt}</b>\n"
                f"│  🔥  <b>Streak</b>            :  <b>{streak_d}</b>\n"
                f"│  🎯  <b>Accuracy</b>         :  <b>{rate}%</b>\n"
                f"╰──────────────────────────────────────────────╯\n\n"
                f"📊  <b>𝐒𝐓𝐀𝐓𝐒</b>\n"
                f"  ✅  <b>Correct</b>              :  <b>{correct}</b>\n"
                f"  ❌  <b>Wrong</b>                :  <b>{wrong}</b>\n"
                f"  📚  <b>Quizzes Played</b>  :  <b>{total_q}</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚜  <b><i>Train  •  Practice  •  Dominate</i></b>  ⚜\n\n"
                f"  ⚡  {COMMUNITY}  ·  <b>CLAT 2027</b>"
            )
        else:
            q_count = len(self.quiz_manager.questions)
            text = (
                f"🎓  <b>𝐂𝐋𝐀𝐓  𝐕𝐈𝐒𝐈𝐎𝐍</b>  ·  Quiz Academy\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👋  Welcome, {mention}!\n\n"
                f"╭──────────────────────────────────────╮\n"
                f"│  📚  Questions    ›  <b>{q_count}+</b> available\n"
                f"│  🎯  Start Quiz  ›  /quiz\n"
                f"│  📊  Your Stats  ›  /score\n"
                f"│  🏆  Rankings    ›  /leaderboard\n"
                f"│  📋  All Topics  ›  /categories\n"
                f"╰──────────────────────────────────────╯\n\n"
                f"  <i>Compete, climb the ranks, ace CLAT! 🚀</i>"
            )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🟢 Start Quiz",       callback_data="play_quiz"),
             InlineKeyboardButton("🔵 My Stats",         callback_data="my_stats")],
            [InlineKeyboardButton("🏆 Leaderboard",      callback_data="leaderboard"),
             InlineKeyboardButton("🟣 Commands",          callback_data="help")],
            [InlineKeyboardButton("🔴 Join CLAT Vision",  url="https://t.me/CLAT_Vision")],
        ])

        if msg:
            ok = await self._edit(msg, text, kb)
            if not ok:
                await self._reply(update, text, reply_markup=kb)
        else:
            await self._reply(update, text, reply_markup=kb)

        # Register user in DB
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

    # ─── /help ───────────────────────────────────────────────

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            f"╔══════════════════════════════════════════╗\n"
            f"║   🎓  <b>𝐂𝐋𝐀𝐓 𝐕𝐈𝐒𝐈𝐎𝐍</b>  ·  Command Guide   ║\n"
            f"╚══════════════════════════════════════════╝\n\n"

            f"🎯  <b>𝐐𝐔𝐈𝐙  𝐂𝐄𝐍𝐓𝐄𝐑</b>\n"
            f"╭──────────────────────────────────────────╮\n"
            f"│  /quiz              ›  Start a quiz\n"
            f"│  /quiz [topic]  ›  Quiz by subject\n"
            f"│  /q                  ›  Quick shortcut\n"
            f"│  /categories      ›  Browse all topics\n"
            f"╰──────────────────────────────────────────╯\n\n"

            f"📊  <b>𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒  𝐂𝐄𝐍𝐓𝐄𝐑</b>\n"
            f"╭──────────────────────────────────────────╮\n"
            f"│  /score           ›  Scorecard &amp; rank\n"
            f"│  /stats            ›  Full analytics\n"
            f"│  /achievements  ›  Badges &amp; milestones\n"
            f"╰──────────────────────────────────────────╯\n\n"

            f"🏆  <b>𝐂𝐎𝐌𝐏𝐄𝐓𝐈𝐓𝐈𝐎𝐍</b>\n"
            f"╭──────────────────────────────────────────╮\n"
            f"│  /leaderboard  ›  Global rankings\n"
            f"│  /lb                  ›  Quick shortcut\n"
            f"╰──────────────────────────────────────────╯\n\n"

            f"🔧  <b>𝐒𝐘𝐒𝐓𝐄𝐌</b>\n"
            f"╭──────────────────────────────────────────╮\n"
            f"│  /ping    ›  Latency check\n"
            f"│  /info     ›  Bot information\n"
            f"│  /start   ›  Dashboard\n"
            f"╰──────────────────────────────────────────╯\n\n"

            f"👑  <b>𝐀𝐃𝐌𝐈𝐍  𝐂𝐄𝐍𝐓𝐄𝐑</b>  <i>· Owner &amp; Devs only</i>\n"
            f"╭──────────────────────────────────────────╮\n"
            f"│  /dev           ›  Admin panel\n"
            f"│  /addquiz      ›  Add question\n"
            f"│  /editquiz     ›  Edit question\n"
            f"│  /delquiz      ›  Delete question\n"
            f"│  /importquiz  ›  Bulk import (.txt)\n"
            f"│  /broadcast      ›  Message everyone\n"
            f"│  /bc                 ›  Broadcast shortcut\n"
            f"│  /delbroadcast  ›  Delete last broadcast\n"
            f"│  /botstats    ›  Platform analytics\n"
            f"│  /devstats    ›  Developer metrics\n"
            f"│  /reload        ›  Sync from database\n"
            f"│  /restart       ›  Restart bot\n"
            f"╰──────────────────────────────────────────╯\n\n"

            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  ⚡  {COMMUNITY}  ·  <b>CLAT 2027</b>"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Start Quiz",    callback_data="play_quiz"),
             InlineKeyboardButton("📊 My Stats",      callback_data="my_stats")],
            [InlineKeyboardButton("🏆 Leaderboard",   callback_data="leaderboard"),
             InlineKeyboardButton("🎖 Achievements",  callback_data="achievements")],
            [InlineKeyboardButton("🏠 Home",           callback_data="back_start")],
        ])
        await self._reply(update, text, reply_markup=kb,
                          disable_web_page_preview=True)

    # ─── /ping ───────────────────────────────────────────────

    async def cmd_ping(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        t0  = time.time()
        msg = await self._reply(update, "🏓 <i>Pinging...</i>")
        ms  = int((time.time() - t0) * 1000)
        if not msg:
            return

        q_count = len(self.quiz_manager.questions)
        if   ms < 100: status = "⚡ Blazing fast";  dot = "🟢"
        elif ms < 300: status = "✅ Fast";            dot = "🟢"
        elif ms < 600: status = "🟡 Normal";          dot = "🟡"
        else:          status = "🔴 Slow";            dot = "🔴"

        text = (
            f"🏓  <b>𝐏𝐎𝐍𝐆</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  ⏱  Latency    ›  <code>{ms} ms</code>\n"
            f"│  {dot}  Status     ›  <b>{status}</b>\n"
            f"│  📚  Questions  ›  <b>{q_count}</b> loaded\n"
            f"│  🤖  Bot         ›  🟢 Online\n"
            f"╰──────────────────────────────────────╯\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  <i>CLAT Vision Quiz Bot</i>"
        )
        await self._edit(msg, text)

    # ─── /info ───────────────────────────────────────────────

    async def cmd_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat      = update.effective_chat
        thread_id = get_thread_id(update)
        q_count   = len(self.quiz_manager.questions)
        is_forum  = getattr(chat, "is_forum", False)

        chat_type = {"private": "DM", "group": "Group",
                     "supergroup": "Supergroup", "channel": "Channel"}.get(chat.type, chat.type)

        text = (
            f"ℹ️  <b>𝐁𝐎𝐓  𝐈𝐍𝐅𝐎𝐑𝐌𝐀𝐓𝐈𝐎𝐍</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🤖  <b>𝐁𝐎𝐓</b>\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  📛  Name        ›  CLAT Vision Quiz Bot\n"
            f"│  📚  Questions   ›  <b>{q_count}</b>\n"
            f"│  🗄  Database    ›  MongoDB Atlas  ✅\n"
            f"│  👑  Owner       ›  {OWNER_NAME}\n"
            f"╰──────────────────────────────────────╯\n\n"
            f"💬  <b>𝐓𝐇𝐈𝐒  𝐂𝐇𝐀𝐓</b>\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  🆔  Chat ID    ›  <code>{chat.id}</code>\n"
            f"│  📌  Type       ›  <b>{chat_type}</b>\n"
        )
        if is_forum:
            text += f"│  📂  Forum     ›  Yes\n"
        if thread_id:
            text += f"│  🧵  Topic ID  ›  <code>{thread_id}</code>\n"
        text += (
            f"╰──────────────────────────────────────╯\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  ⚡  {COMMUNITY}  ·  <b>CLAT 2027</b>"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🎯 Start Quiz", callback_data="play_quiz"),
            InlineKeyboardButton("🏠 Home",        callback_data="back_start"),
        ]])
        await self._reply(update, text, reply_markup=kb)

    # ─── /categories ─────────────────────────────────────────

    async def cmd_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        cat_lines = "\n".join(
            f"•  {name}  {emoji}" for emoji, name, _ in UI.CATS_DISPLAY
        )
        text = (
            f"  📚  <b>𝗩𝗜𝗘𝗪  𝗖𝗔𝗧𝗘𝗚𝗢𝗥𝗜𝗘𝗦</b>\n"
            f"══════════════════════════\n\n"
            f"📑  <b>𝗔𝗩𝗔𝗜𝗟𝗔𝗕𝗟𝗘  𝗤𝗨𝗜𝗭  𝗖𝗔𝗧𝗘𝗚𝗢𝗥𝗜𝗘𝗦</b>\n\n"
            f"{cat_lines}\n\n"
            f"══════════════════════════\n"
            f"🎯  Stay tuned! More quizzes coming soon!\n"
            f"🛠  Need help? Use /help for more commands"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Start Quiz",   callback_data="play_quiz"),
             InlineKeyboardButton("🏆 Leaderboard",  callback_data="leaderboard")],
            [InlineKeyboardButton("🏠 Home",          callback_data="back_start")],
        ])
        await self._reply(update, text, reply_markup=kb)

    # ─── /quiz ───────────────────────────────────────────────

    async def cmd_quiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from src.core.validators import validate, sanitize, build_explanation

        chat      = update.effective_chat
        thread_id = get_thread_id(update)
        track_id  = get_tracking_id(chat.id, thread_id)
        category  = " ".join(context.args).strip() if context.args else ""

        question = self.quiz_manager.get_random_question(
            chat_id=track_id, category=category)

        if not question:
            cat_e = UI.cat_emoji(category)
            cat_line = f"│  {cat_e}  Category  ›  <b>{category}</b>\n" if category else ""
            text  = (
                f"📭  <b>𝐍𝐎  𝐐𝐔𝐄𝐒𝐓𝐈𝐎𝐍𝐒  𝐅𝐎𝐔𝐍𝐃</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"╭──────────────────────────────────────╮\n"
                f"{cat_line}"
                f"│  The question bank is empty.\n"
                f"│  Use /addquiz or /importquiz to add.\n"
                f"╰──────────────────────────────────────╯"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Browse Topics",  callback_data="categories"),
                 InlineKeyboardButton("🏠 Home",            callback_data="back_start")],
            ])
            await self._reply(update, text, reply_markup=kb)
            return

        # Validate and sanitize
        question = sanitize(question)
        if not question or not validate(question).valid:
            await self._reply(update, "⚠️ Question data error. Try /quiz again.")
            return

        options     = question["options"]
        correct_idx = question["correct_answer"]
        cat         = question.get("category", "General")
        cat_emoji   = UI.cat_emoji(cat)
        q_id        = question.get("id")

        poll_q = f"{cat_emoji} {question['question']}"
        if len(poll_q) > 300:
            poll_q = poll_q[:299] + "…"

        poll_kwargs = dict(
            question          = poll_q,
            options           = options,
            type              = Poll.QUIZ,
            correct_option_id = correct_idx,
            is_anonymous      = False,
            explanation       = build_explanation(question),
        )
        if thread_id:
            poll_kwargs["message_thread_id"] = thread_id

        # ── Single-active-quiz cleanup: delete previous quiz first ──
        logger.info(f"[QUIZ] Sending New Quiz — /quiz chat={chat.id}")
        await self.cleanup.cleanup(context.bot, chat.id)

        poll_sent = False
        try:
            poll_msg = await update.effective_message.reply_poll(**poll_kwargs)
            poll_id  = poll_msg.poll.id
            poll_sent = True

            # Register as the single active quiz for this chat
            self.cleanup.save_active(chat.id, poll_msg.message_id,
                                     quiz_type="poll", thread_id=thread_id)

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
            if any(w in err for w in ("topic", "thread", "closed")):
                await self._reply(update, "⚠️ <b>Topic Restricted</b>\n\nThis topic is closed.")
                return
            logger.warning(f"[QUIZ] Poll Validation Failed — falling back to inline: {e}")

        # Inline keyboard fallback if poll failed
        if not poll_sent:
            labels = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
            text = (
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📚 CLAT VISION  •  QUIZ\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Category:</b> {cat_emoji} {cat}\n"
                f"<b>Q#{q_id}</b>\n\n"
                f"{question['question']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Select the correct answer:"
            )
            buttons = []
            for i, opt in enumerate(options):
                lbl = f"{labels[i]}  {opt}" if i < len(labels) else opt
                buttons.append([InlineKeyboardButton(
                    lbl[:64], callback_data=f"aq_ans_{q_id}_{i}_{correct_idx}")])
            try:
                inline_msg = await update.effective_message.reply_text(
                    text, parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(buttons))
                # Register inline quiz as the single active quiz
                self.cleanup.save_active(chat.id, inline_msg.message_id,
                                         quiz_type="inline", thread_id=thread_id)
            except TelegramError as e2:
                logger.error(f"[QUIZ] Inline fallback also failed: {e2}")

    # ─── POLL ANSWER HANDLER ─────────────────────────────────

    async def handle_poll_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        answer     = update.poll_answer
        user_id    = answer.user.id
        poll_id    = answer.poll_id
        option_ids = answer.option_ids

        data       = context.bot_data.get(f"poll_{poll_id}", {})
        correct_id = data.get("correct_option_id")
        chat_id    = data.get("chat_id", 0)
        thread_id  = data.get("thread_id")

        if correct_id is None or not option_ids:
            return

        is_correct = (option_ids[0] == correct_id)

        # Capture rank/level BEFORE recording (to detect promotions)
        score_before = self.quiz_manager.get_score(user_id)
        _, grade_before = UI.rank(score_before)
        level_before = UI.level(score_before)

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
                # Save name every time so leaderboard always has real names
                u = answer.user
                uname = (u.first_name or "").strip() or (u.username or "").strip()
                self.db.upsert_user(user_id, {
                    "user_id":       user_id,
                    "name":          uname or f"User{str(user_id)[-4:]}",
                    "username":      u.username or "",
                    "last_seen":     datetime.utcnow().isoformat(),
                    "total_answers": self.quiz_manager.get_score(user_id),
                })
            except Exception as e:
                logger.error(f"DB poll_answer: {e}")

        # Send milestone notification (PM only, non-intrusive)
        if is_correct:
            score_after = self.quiz_manager.get_score(user_id)
            _, grade_after = UI.rank(score_after)
            level_after = UI.level(score_after)
            stats_after = self.quiz_manager.get_user_stats(user_id)
            streak = stats_after.get("current_streak", 0)

            notif = None
            # Rank promotion
            if grade_after != grade_before:
                rank_txt, _ = UI.rank(score_after)
                notif = (
                    f"🎉  <b>RANK UP!</b>\n\n"
                    f"  You've been promoted to\n"
                    f"  <b>{rank_txt}</b>  🏆\n\n"
                    f"  Score: <b>{score_after} correct</b>\n"
                    f"  Keep dominating! 💪"
                )
            # Level up
            elif level_after != level_before:
                notif = (
                    f"⬆️  <b>LEVEL UP!</b>\n\n"
                    f"  You reached  <b>{level_after}</b>  ✨\n\n"
                    f"  Score: <b>{score_after} correct</b>\n"
                    f"  On your way to the top! 🚀"
                )
            # Streak milestones
            elif streak in (3, 7, 14, 30, 50, 100):
                streak_msgs = {
                    3: ("🔥", "3-Day Streak!", "You're on fire!"),
                    7: ("💫", "Week Warrior!", "7 days strong!"),
                    14: ("⚡", "Two Weeks!", "Unstoppable streak!"),
                    30: ("🌟", "Month Master!", "30 days — incredible!"),
                    50: ("💎", "Elite Streak!", "50 days of dedication!"),
                    100: ("👑", "Century!", "100-day legend streak!"),
                }
                icon, title, sub = streak_msgs[streak]
                notif = (
                    f"{icon}  <b>{title}</b>\n\n"
                    f"  {sub}\n"
                    f"  🔥 <b>{streak} day streak</b>  maintained!\n\n"
                    f"  Keep the momentum! 💪"
                )

            if notif:
                try:
                    await context.bot.send_message(
                        chat_id=user_id, text=notif, parse_mode="HTML")
                except Exception:
                    pass

    # ─── /score ──────────────────────────────────────────────

    async def cmd_score(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user    = update.effective_user
        msg     = await self._reply(update, "🏆")
        mention = UI.mention(user.id, user.first_name or "User")
        score   = self.quiz_manager.get_score(user.id)
        stats   = self.quiz_manager.get_user_stats(user.id)

        total   = stats.get("total_quizzes", 0)
        rate    = stats.get("success_rate", 0)
        streak  = stats.get("current_streak", 0)
        best    = stats.get("longest_streak", 0)
        today   = stats.get("today_quizzes", 0)
        wrong   = total - score

        rank_txt, grade = UI.rank(score)
        level_txt       = UI.level(score)
        xp_bar          = UI.xp_bar(score)
        rank_pos        = self._get_user_rank_position(user.id)
        pos_text        = f"#{rank_pos}" if rank_pos else "—"
        acc_pbar        = UI.pbar(rate)

        text = (
            f"🏆  <b>𝐒𝐂𝐎𝐑𝐄𝐂𝐀𝐑𝐃</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"  {mention}\n\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  🎖  <b>Rank</b>       ›  {rank_txt}  <i>({grade})</i>\n"
            f"│  📈  <b>Level</b>      ›  {level_txt}\n"
            f"│  🌍  <b>Position</b>  ›  <b>{pos_text} Global</b>\n"
            f"╰──────────────────────────────────────╯\n"
            f"  <i>XP Progress</i>  {xp_bar}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊  <b>𝐏𝐄𝐑𝐅𝐎𝐑𝐌𝐀𝐍𝐂𝐄</b>\n\n"
            f"  ✅  <b>Correct</b>    ›  <b>{score}</b>\n"
            f"  ❌  <b>Wrong</b>      ›  <b>{wrong}</b>\n"
            f"  📝  <b>Total</b>      ›  <b>{total}</b>\n"
            f"  🎯  <b>Accuracy</b>  ›  <b>{rate}%</b>\n\n"
            f"  {acc_pbar}  <b>{rate}%</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔥  <b>𝐒𝐓𝐑𝐄𝐀𝐊𝐒</b>\n\n"
            f"  ◈  <b>Current</b>  ›  {UI.streak_display(streak)}\n"
            f"  ◈  <b>Best</b>     ›  <b>{best} days</b>\n"
            f"  ◈  <b>Today</b>    ›  <b>{today}</b> questions\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  <i>Every correct answer brings you closer to CLAT! 🎯</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Play Quiz",    callback_data="play_quiz"),
             InlineKeyboardButton("📊 Full Stats",   callback_data="my_stats")],
            [InlineKeyboardButton("🏆 Leaderboard",  callback_data="leaderboard"),
             InlineKeyboardButton("🏠 Home",          callback_data="back_start")],
        ])
        if msg:
            ok = await self._edit(msg, text, kb)
            if not ok:
                await self._reply(update, text, reply_markup=kb)
        else:
            await self._reply(update, text, reply_markup=kb)

    # ─── /stats ──────────────────────────────────────────────

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user    = update.effective_user
        msg     = await self._reply(update, "📊")
        mention = UI.mention(user.id, user.first_name or "User")

        score  = self.quiz_manager.get_score(user.id)
        stats  = self.quiz_manager.get_user_stats(user.id)

        total   = stats.get("total_quizzes", 0)
        rate    = stats.get("success_rate", 0)
        streak  = stats.get("current_streak", 0)
        best    = stats.get("longest_streak", 0)
        today   = stats.get("today_quizzes", 0)
        week    = stats.get("week_quizzes", 0)
        month   = stats.get("month_quizzes", 0)
        wrong   = total - score

        rank_txt, grade = UI.rank(score)
        level_txt       = UI.level(score)
        xp_bar          = UI.xp_bar(score)
        rank_pos        = self._get_user_rank_position(user.id)
        pos_text        = f"#{rank_pos}" if rank_pos else "Unranked"

        w_pct    = min(100, week / 50 * 100) if week else 0
        w_pbar   = UI.pbar(w_pct)
        acc_pbar = UI.pbar(rate)

        text = (
            f"📈  <b>𝐏𝐄𝐑𝐅𝐎𝐑𝐌𝐀𝐍𝐂𝐄  𝐀𝐍𝐀𝐋𝐘𝐓𝐈𝐂𝐒</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"  {mention}\n\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  🎖  <b>Rank</b>       ›  {rank_txt}  <i>({grade})</i>\n"
            f"│  📈  <b>Level</b>      ›  {level_txt}\n"
            f"│  🌍  <b>Position</b>  ›  <b>{pos_text} Global</b>\n"
            f"╰──────────────────────────────────────╯\n"
            f"  <i>XP Progress</i>  {xp_bar}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯  <b>𝐀𝐂𝐂𝐔𝐑𝐀𝐂𝐘</b>\n\n"
            f"  ✅  <b>Correct</b>    ›  <b>{score}</b>\n"
            f"  ❌  <b>Wrong</b>      ›  <b>{wrong}</b>\n"
            f"  📝  <b>Total</b>      ›  <b>{total}</b>\n"
            f"  🎯  <b>Accuracy</b>  ›  <b>{rate}%</b>\n\n"
            f"  {acc_pbar}  <b>{rate}%</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔥  <b>𝐒𝐓𝐑𝐄𝐀𝐊𝐒</b>\n\n"
            f"  ◈  <b>Current</b>  ›  {UI.streak_display(streak)}\n"
            f"  ◈  <b>Best</b>     ›  <b>{best} days</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📅  <b>𝐀𝐂𝐓𝐈𝐕𝐈𝐓𝐘</b>\n\n"
            f"  ◈  <b>Today</b>   ›  <b>{today}</b> questions\n"
            f"  ◈  <b>Week</b>    ›  <b>{week}</b>  / 50 target\n"
            f"  {w_pbar}  <b>{int(w_pct)}%</b> weekly goal\n"
            f"  ◈  <b>Month</b>   ›  <b>{month}</b> questions\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  <i>Target: 20+ questions daily to ace CLAT! 🎓</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Play Quiz",    callback_data="play_quiz"),
             InlineKeyboardButton("🏆 Leaderboard",  callback_data="leaderboard")],
            [InlineKeyboardButton("🏠 Home",          callback_data="back_start")],
        ])
        if msg:
            ok = await self._edit(msg, text, kb)
            if not ok:
                await self._reply(update, text, reply_markup=kb)
        else:
            await self._reply(update, text, reply_markup=kb)

    # ─── /achievements ───────────────────────────────────────

    async def cmd_achievements(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user    = update.effective_user
        msg     = await self._reply(update, "🎖")
        mention = UI.mention(user.id, user.first_name or "User")
        score   = self.quiz_manager.get_score(user.id)
        stats   = self.quiz_manager.get_user_stats(user.id)
        streak  = stats.get("current_streak", 0)
        rate    = stats.get("success_rate", 0)
        total   = stats.get("total_quizzes", 0)

        earned, locked = UI.get_achievements(score, streak, float(rate), total)
        n_earned = len(earned)
        n_total  = len(UI.ACHIEVEMENTS)
        prog     = UI.pbar(int(n_earned / n_total * 100))

        lines = [
            f"🏅  <b>𝐀𝐂𝐇𝐈𝐄𝐕𝐄𝐌𝐄𝐍𝐓𝐒</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"  {mention}\n\n"
            f"  {prog}  <b>{n_earned} / {n_total}</b> unlocked\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        ]

        if earned:
            lines.append(f"\n✅  <b>EARNED</b>\n")
            for icon, name, desc in earned:
                lines.append(f"  {icon}  <b>{name}</b>  —  <i>{desc}</i>")

        if locked:
            lines.append(f"\n🔒  <b>LOCKED</b>\n")
            for icon, name, desc in locked[:6]:
                lines.append(f"  ░  <b>{name}</b>  —  <i>{desc}</i>")
            if len(locked) > 6:
                lines.append(f"  <i>… and {len(locked)-6} more to discover</i>")

        lines.append(
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  <i>Keep playing to unlock all achievements! 🎯</i>"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Play Quiz",   callback_data="play_quiz"),
             InlineKeyboardButton("📊 My Stats",    callback_data="my_stats")],
            [InlineKeyboardButton("🏠 Home",         callback_data="back_start")],
        ])
        result_text = "\n".join(lines)
        if msg:
            ok = await self._edit(msg, result_text, kb)
            if not ok:
                await self._reply(update, result_text, reply_markup=kb)
        else:
            await self._reply(update, result_text, reply_markup=kb)

    # ─── /botstats ───────────────────────────────────────────

    async def cmd_botstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await self._reply(update, "📊")

        q_total = len(self.quiz_manager.questions)

        # Users
        u_total = u_active_d = u_active_w = 0
        u_new_d = u_new_w = u_new_m = 0
        # Groups
        g_total = g_new_d = g_new_w = g_new_m = 0
        # Quiz attempts
        d_q = w_q = m_q = a_q = 0
        d_c = w_c = m_c = a_c = 0
        d_players: set = set()
        w_players: set = set()
        m_players: set = set()

        if self.db:
            try:
                from datetime import timedelta
                now   = datetime.utcnow()
                d_cut = (now - timedelta(days=1)).isoformat()
                w_cut = (now - timedelta(days=7)).isoformat()
                m_cut = (now - timedelta(days=30)).isoformat()
                acts  = self.db.activities_col
                ucol  = self.db.users_col
                gcol  = self.db.groups_col

                # ── Users ────────────────────────────────────
                u_total    = ucol.count_documents({})
                u_active_d = ucol.count_documents({"last_seen": {"$gte": d_cut}})
                u_active_w = ucol.count_documents({"last_seen": {"$gte": w_cut}})
                u_new_d    = ucol.count_documents({"joined_at": {"$gte": d_cut}})
                u_new_w    = ucol.count_documents({"joined_at": {"$gte": w_cut}})
                u_new_m    = ucol.count_documents({"joined_at": {"$gte": m_cut}})

                # ── Groups ───────────────────────────────────
                g_total = gcol.count_documents({})
                g_new_d = gcol.count_documents({"joined_at": {"$gte": d_cut}})
                g_new_w = gcol.count_documents({"joined_at": {"$gte": w_cut}})
                g_new_m = gcol.count_documents({"joined_at": {"$gte": m_cut}})

                # ── Quiz attempts ────────────────────────────
                d_q = acts.count_documents({"type": "quiz_answer", "timestamp": {"$gte": d_cut}})
                w_q = acts.count_documents({"type": "quiz_answer", "timestamp": {"$gte": w_cut}})
                m_q = acts.count_documents({"type": "quiz_answer", "timestamp": {"$gte": m_cut}})
                a_q = acts.count_documents({"type": "quiz_answer"})

                d_c = acts.count_documents({"type": "quiz_answer", "is_correct": True, "timestamp": {"$gte": d_cut}})
                w_c = acts.count_documents({"type": "quiz_answer", "is_correct": True, "timestamp": {"$gte": w_cut}})
                m_c = acts.count_documents({"type": "quiz_answer", "is_correct": True, "timestamp": {"$gte": m_cut}})
                a_c = acts.count_documents({"type": "quiz_answer", "is_correct": True})

                d_players = set(d["user_id"] for d in acts.find(
                    {"type": "quiz_answer", "timestamp": {"$gte": d_cut}}, {"user_id": 1}))
                w_players = set(d["user_id"] for d in acts.find(
                    {"type": "quiz_answer", "timestamp": {"$gte": w_cut}}, {"user_id": 1}))
                m_players = set(d["user_id"] for d in acts.find(
                    {"type": "quiz_answer", "timestamp": {"$gte": m_cut}}, {"user_id": 1}))

            except Exception as e:
                logger.error(f"botstats DB error: {e}")

        def acc(c, t): return f"{round(c/t*100,1)}%" if t else "—"

        text = (
            f"📊  <b>𝐁𝐎𝐓  𝐀𝐍𝐀𝐋𝐘𝐓𝐈𝐂𝐒</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"👥  <b>𝐔𝐒𝐄𝐑𝐒</b>\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  Total          ›  <b>{UI.fmt_num(u_total)}</b>\n"
            f"│  Active 24h     ›  <b>{u_active_d}</b>\n"
            f"│  Active 7d      ›  <b>{u_active_w}</b>\n"
            f"│  New Today      ›  <b>+{u_new_d}</b>\n"
            f"│  New This Week  ›  <b>+{u_new_w}</b>\n"
            f"│  New This Month ›  <b>+{u_new_m}</b>\n"
            f"╰──────────────────────────────────────╯\n\n"

            f"💬  <b>𝐆𝐑𝐎𝐔𝐏𝐒</b>\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  Total          ›  <b>{UI.fmt_num(g_total)}</b>\n"
            f"│  New Today      ›  <b>+{g_new_d}</b>\n"
            f"│  New This Week  ›  <b>+{g_new_w}</b>\n"
            f"│  New This Month ›  <b>+{g_new_m}</b>\n"
            f"╰──────────────────────────────────────╯\n\n"

            f"📚  <b>𝐐𝐔𝐄𝐒𝐓𝐈𝐎𝐍  𝐁𝐀𝐍𝐊</b>  ›  <b>{UI.fmt_num(q_total)}</b> questions\n\n"

            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"🎯  <b>QUIZ ACTIVITY</b>\n\n"
            f"  <b>24h</b>   ›  <b>{d_q}</b> attempts  ·  <b>{d_c}</b> correct  ·  <b>{acc(d_c, d_q)}</b>  ·  <b>{len(d_players)}</b> players\n"
            f"  <b>7d</b>    ›  <b>{w_q}</b> attempts  ·  <b>{w_c}</b> correct  ·  <b>{acc(w_c, w_q)}</b>  ·  <b>{len(w_players)}</b> players\n"
            f"  <b>30d</b>   ›  <b>{m_q}</b> attempts  ·  <b>{m_c}</b> correct  ·  <b>{acc(m_c, m_q)}</b>  ·  <b>{len(m_players)}</b> players\n"
            f"  <b>All</b>   ›  <b>{UI.fmt_num(a_q)}</b> attempts  ·  <b>{UI.fmt_num(a_c)}</b> correct  ·  <b>{acc(a_c, a_q)}</b>\n\n"

            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  <i>⚡ {COMMUNITY}  ·  CLAT Vision Analytics</i>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📈 Dev Stats",  callback_data="devstats_prompt"),
             InlineKeyboardButton("🏠 Home",        callback_data="back_start")],
        ])
        if msg:
            ok = await self._edit(msg, text, kb)
            if not ok:
                await self._reply(update, text, reply_markup=kb)
        else:
            await self._reply(update, text, reply_markup=kb)

    # ─── /leaderboard ────────────────────────────────────────
    #  Paginated Top-100 leaderboard — 20 per page, 5 pages.

    LB_PAGE_SIZE = 20
    LB_MAX_RANKS = 100
    LB_NAME_W    = 13     # display width for usernames (monospace column)

    async def cmd_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._show_leaderboard(update, context, mode="global", page=1)

    # ── Period mapping ─────────────────────────────────────────
    _LB_PERIOD = {"global": 36500, "weekly": 7, "monthly": 30}
    _LB_LABEL  = {
        "global":  "All-Time",
        "weekly":  "Last 7 Days",
        "monthly": "Last 30 Days",
        "group":   "This Group",
    }

    def _lb_truncate(self, name: str) -> str:
        """Truncate a username to LB_NAME_W chars with an ellipsis, no wrapping."""
        name = (name or "").replace("\n", " ").strip()
        # Escape for HTML <pre> block
        name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if len(name) > self.LB_NAME_W:
            return name[:self.LB_NAME_W - 1] + "…"
        return name

    def _lb_fetch(self, mode: str, chat_id: int) -> list:
        """Fetch the full ranked list (cached) for a leaderboard mode."""
        key = f"{mode}:{chat_id if mode == 'group' else 0}"
        now = time.time()
        cached = self._lb_cache.get(key)
        if cached and (now - cached[0]) < self._lb_cache_ttl:
            return cached[1]

        if mode == "group":
            data = self.quiz_manager.get_group_leaderboard(chat_id)
            lb   = data.get("leaderboard", [])
        elif self.db:
            days = self._LB_PERIOD.get(mode, 36500)
            lb   = self.db.get_leaderboard_by_period(days=days, limit=self.LB_MAX_RANKS)
        else:
            lb = self.quiz_manager.get_leaderboard(limit=self.LB_MAX_RANKS)

        self._lb_cache[key] = (now, lb)
        return lb

    def _lb_resolve_names(self, uids: list) -> dict:
        """Batch-resolve display names for a list of user IDs from the DB."""
        names: dict = {}
        if not uids:
            return names
        if self.db:
            try:
                cursor = self.db.users_col.find(
                    {"user_id": {"$in": uids}}, {"user_id": 1, "name": 1, "username": 1})
                for doc in cursor:
                    n = (doc.get("name") or doc.get("username") or "").strip()
                    if n:
                        names[doc["user_id"]] = n
            except Exception as e:
                logger.error(f"_lb_resolve_names error: {e}")
        return names

    async def _show_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                mode: str = "global", page: int = 1, edit_msg=None):
        """
        Paginated leaderboard.
          mode : 'global' | 'weekly' | 'monthly' | 'group'
          page : 1-indexed page number (20 entries/page, max 100 ranks)
        """
        chat      = update.effective_chat
        is_group  = chat.type in ("group", "supergroup")
        req_user  = update.effective_user

        # Groups always show the group leaderboard
        if is_group and mode in ("global", "weekly", "monthly"):
            mode = "group"

        if edit_msg is None:
            wait_msg = await self._reply(update, "🏆  <i>Loading leaderboard…</i>")
        else:
            wait_msg = None

        lb = self._lb_fetch(mode, chat.id)

        if not lb:
            text = (
                f"🏆  <b>CLAT VISION • LEADERBOARD</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "  No scores yet — be the first! 🥇\n\n"
                "  Use /quiz to start playing."
            )
            target = edit_msg or wait_msg
            if target:
                await self._edit(target, text)
            return

        # ── Pagination math ────────────────────────────────────
        total      = min(len(lb), self.LB_MAX_RANKS)
        total_pages = max(1, (total + self.LB_PAGE_SIZE - 1) // self.LB_PAGE_SIZE)
        page       = max(1, min(page, total_pages))    # clamp — callback security
        start      = (page - 1) * self.LB_PAGE_SIZE
        end        = min(start + self.LB_PAGE_SIZE, total)
        page_slice = lb[start:end]

        # ── Resolve names for this page only ───────────────────
        page_uids = [e.get("user_id") for e in page_slice]
        names     = self._lb_resolve_names(page_uids)

        # ── Build monospace, perfectly-aligned table ───────────
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        rows   = []
        for i, entry in enumerate(page_slice):
            rank  = start + i + 1
            uid   = entry.get("user_id")
            score = entry.get("correct_answers", entry.get("score", 0))

            if uid == OWNER_ID:
                raw_name = "CLAT OWNER"
            else:
                raw_name = names.get(uid) or f"User{str(uid)[-4:]}"
            name = self._lb_truncate(raw_name)

            # rank right-aligned (3), name left-padded (LB_NAME_W), score right (6)
            row = f"{rank:>3}  {name:<{self.LB_NAME_W}}  {score:>6}"

            trail = ""
            if rank in medals:
                trail += f"  {medals[rank]}"
            if req_user and uid == req_user.id:
                trail += "  ⭐"
            rows.append(row + trail)

        table = "\n".join(rows)
        label = self._LB_LABEL.get(mode, "All-Time")

        # ── YOUR POSITION section (always visible) ─────────────
        my_section = ""
        if req_user and mode != "group" and self.db:
            try:
                info = self.db.get_user_rank_in_period(
                    req_user.id, self._LB_PERIOD.get(mode, 36500))
                if info.get("total", 0) > 0:
                    streak = self.quiz_manager.get_user_stats(
                        req_user.id).get("current_streak", 0)
                    my_section = (
                        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊  <b>YOUR POSITION</b>\n"
                        f"   Rank:    #{info['rank']}\n"
                        f"   Score:   {info['correct']}\n"
                        f"   Streak:  🔥 {streak}\n"
                    )
            except Exception as e:
                logger.error(f"leaderboard my_section: {e}")
        elif req_user and mode == "group":
            # Group: find requester within the loaded list
            for idx, e in enumerate(lb):
                if e.get("user_id") == req_user.id:
                    my_section = (
                        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊  <b>YOUR POSITION</b>\n"
                        f"   Rank:    #{idx + 1}\n"
                        f"   Score:   {e.get('correct_answers', 0)}\n"
                    )
                    break

        text = (
            f"🏆  <b>CLAT VISION • LEADERBOARD</b>\n"
            f"<i>{label} · Top {total}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<pre>{table}</pre>"
            f"{my_section}"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📄  Page {page}/{total_pages}"
        )

        kb = self._build_lb_keyboard(mode, page, total_pages, is_group)

        target = edit_msg or wait_msg
        if target:
            await self._edit(target, text, kb)
        else:
            await self._reply(update, text, reply_markup=kb)

    def _build_lb_keyboard(self, mode: str, page: int, total_pages: int,
                           is_group: bool) -> InlineKeyboardMarkup:
        """Build navigation + mode-tab keyboard."""
        # Navigation row — Prev disabled on first, Next on last
        prev_cb = f"lbp_{mode}_{page-1}" if page > 1 else "lb_noop"
        next_cb = f"lbp_{mode}_{page+1}" if page < total_pages else "lb_noop"
        prev_lbl = "◀️ Prev" if page > 1 else "▫️"
        next_lbl = "Next ▶️" if page < total_pages else "▫️"
        nav_row = [
            InlineKeyboardButton(prev_lbl, callback_data=prev_cb),
            InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="lb_noop"),
            InlineKeyboardButton(next_lbl, callback_data=next_cb),
        ]

        rows = [nav_row]
        if not is_group and mode != "group":
            rows.append([
                InlineKeyboardButton(
                    "🌍 Global ✦" if mode == "global" else "🌍 Global",
                    callback_data="lbp_global_1"),
                InlineKeyboardButton(
                    "📅 Weekly ✦" if mode == "weekly" else "📅 Weekly",
                    callback_data="lbp_weekly_1"),
                InlineKeyboardButton(
                    "🗓 Monthly ✦" if mode == "monthly" else "🗓 Monthly",
                    callback_data="lbp_monthly_1"),
            ])
        rows.append([
            InlineKeyboardButton("🎯 Play Quiz", callback_data="play_quiz"),
            InlineKeyboardButton("📊 My Stats",  callback_data="my_stats"),
        ])
        rows.append([InlineKeyboardButton("🏠 Home", callback_data="back_start")])
        return InlineKeyboardMarkup(rows)

    # ─── /addquiz ────────────────────────────────────────────

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
            f"➕  <b>𝐀𝐃𝐃  𝐐𝐔𝐄𝐒𝐓𝐈𝐎𝐍</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  <b>Format</b> (one item per line):\n"
            f"│\n"
            f"│  <code>/addquiz</code>\n"
            f"│  <code>Question text</code>\n"
            f"│  <code>Option A</code>\n"
            f"│  <code>Option B</code>\n"
            f"│  <code>Option C</code>\n"
            f"│  <code>Option D</code>\n"
            f"│  <code>Correct (1–4)</code>\n"
            f"│  <code>Category</code>\n"
            f"╰──────────────────────────────────────╯\n\n"
            f"<b>Example:</b>\n"
            f"<code>/addquiz\n"
            f"Which Article abolishes untouchability?\n"
            f"Article 14\nArticle 17\nArticle 19\nArticle 21\n"
            f"2\nConstitution</code>"
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
        result = self.quiz_manager.add_questions([{
            "question": question, "options": options,
            "correct_answer": correct, "category": category,
        }])

        added   = result.get("added", 0)
        dups    = result.get("rejected", {}).get("duplicates", 0)
        total   = len(self.quiz_manager.questions)
        mention = UI.mention(user.id, user.first_name or "Admin")

        if added > 0:
            text = (
                f"✅  <b>𝐐𝐔𝐄𝐒𝐓𝐈𝐎𝐍  𝐀𝐃𝐃𝐄𝐃</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"  Added by {mention}\n\n"
                f"╭──────────────────────────────────────╮\n"
                f"│  <b>{question[:60]}{'…' if len(question) > 60 else ''}</b>\n"
                f"│\n"
                f"│  A:  {options[0]}\n"
                f"│  B:  {options[1]}\n"
                f"│  C:  {options[2]}\n"
                f"│  D:  {options[3]}\n"
                f"│\n"
                f"│  ✅  Answer    ›  Option {correct+1} — <b>{options[correct]}</b>\n"
                f"│  📂  Category  ›  <b>{category}</b>\n"
                f"╰──────────────────────────────────────╯\n\n"
                f"  📦  Total in bank: <b>{total}</b>"
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

        await self._reply(update, text)

    # ─── /delquiz ────────────────────────────────────────────

    async def cmd_delquiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        # Reply-to-poll detection
        reply = update.effective_message.reply_to_message
        if reply and reply.poll:
            poll_id   = reply.poll.id
            poll_data = context.bot_data.get(f"poll_{poll_id}", {})
            q_id      = poll_data.get("question_id")

            if q_id is None and self.db:
                try:
                    q_id = self.db.get_quiz_id_from_poll(str(poll_id))
                except Exception:
                    pass

            if q_id is None:
                poll_q       = reply.poll.question or ""
                poll_q_clean = re.sub(r"^\S+\s+", "", poll_q.strip())
                for q in self.quiz_manager.questions:
                    if q.get("question", "").strip() == poll_q_clean.strip():
                        q_id = q.get("id")
                        break

            if q_id is not None:
                mention   = UI.mention(user.id, user.first_name or "Admin")
                q_info    = next((q for q in self.quiz_manager.questions
                                  if q.get("id") == q_id), {})
                q_preview = q_info.get("question", f"#{q_id}")[:55]

                msg = await self._reply(update, "🗑️")
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
                await self._reply(update,
                    f"⚠️ <b>Cannot Identify Question</b>\n"
                    f"{UI.LINE}\n\n"
                    "  Could not match this poll to any question.\n"
                    "  Use /delquiz without reply to pick from list."
                )
                return

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
            f"  Page <b>{page+1}</b> / <b>{pages}</b>  ·  Total: <b>{total}</b>\n"
            f"{UI.LINE}\n\n"
            f"Select a question to delete:\n"
        ]
        for q in questions[start:end]:
            qid   = q.get("id", "?")
            qtext = q.get("question", "")[:40]
            cat   = q.get("category", "General")
            emoji = UI.cat_emoji(cat)
            lines.append(f"  {emoji} <code>#{qid}</code>  {qtext}{'…' if len(q.get('question',''))>40 else ''}")

        return "\n".join(lines)

    def _delquiz_kb(self, questions: list, page: int, user_id: int) -> InlineKeyboardMarkup:
        per   = 8
        start = page * per
        total = len(questions)
        pages = (total + per - 1) // per
        rows  = []

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

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("🔵 ◀ Prev", callback_data=f"dq_page_{page-1}_{user_id}"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton("Next ▶ 🔵", callback_data=f"dq_page_{page+1}_{user_id}"))
        if nav:
            rows.append(nav)

        rows.append([InlineKeyboardButton("🔴 Cancel", callback_data=f"dq_cancel_{user_id}")])
        return InlineKeyboardMarkup(rows)

    async def _cb_delquiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data  = query.data
        actor = query.from_user

        parts  = data.split("_")
        action = parts[1]

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
            qid     = int(parts[2])
            q_info  = next((q for q in questions if q.get("id") == qid), None)
            preview = q_info.get("question", "")[:55] if q_info else f"#{qid}"

            success = self.quiz_manager.delete_question_by_db_id(qid)
            mention = UI.mention(actor.id, actor.first_name or "Admin")

            if success:
                remaining = len(self.quiz_manager.questions)
                text = (
                    f"✅ <b>DELETED</b>\n"
                    f"{UI.LINE}\n\n"
                    f"  By {mention}\n"
                    f"  <code>#{qid}</code> — {preview}…\n\n"
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

    # ─── /editquiz ───────────────────────────────────────────

    async def cmd_editquiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        if self._dev and hasattr(self._dev, "editquiz"):
            await self._dev.editquiz(update, context)
            return

        questions = self.quiz_manager.questions
        if not questions:
            await self._reply(update,
                f"📭  <b>EMPTY BANK</b>\n\n"
                "  No questions in database.\n"
                "  Use /addquiz to add some."
            )
            return

        total = len(questions)
        lines = [f"📋 <b>QUESTION BANK</b>  ·  {total} questions\n{UI.LINE}\n"]

        for q in questions[:20]:
            qid   = q.get("id", "?")
            qtext = q.get("question", "")[:45]
            cat   = q.get("category", "General")
            emoji = UI.cat_emoji(cat)
            lines.append(
                f"  {emoji} <code>#{qid}</code>  {qtext}"
                + ("…" if len(q.get("question", "")) > 45 else "")
            )

        if total > 20:
            lines.append(f"\n  <i>… and {total-20} more questions</i>")

        lines.append(
            f"\n{UI.LINE}\n"
            f"  /delquiz   Delete a question\n"
            f"  /addquiz   Add a question\n"
            f"  /reload    Sync from database"
        )

        await self._reply(update, "\n".join(lines))

    # ─── /dev ────────────────────────────────────────────────

    async def cmd_dev(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        if self._dev and hasattr(self._dev, "dev"):
            await self._dev.dev(update, context)
            return

        msg     = await self._reply(update, "👑")
        mention = UI.mention(user.id,
            OWNER_NAME if self._is_owner(user.id) else (user.first_name or "Dev"))
        q_count = len(self.quiz_manager.questions)
        chats   = len(self.quiz_manager.active_chats)
        users = groups = 0
        if self.db:
            try:
                users  = len(self.db.get_all_users_stats())
                groups = len(self.db.get_all_groups())
            except Exception:
                pass

        text = (
            f"╔══════════════════════════════════════════╗\n"
            f"║      👑  <b>𝐀𝐃𝐌𝐈𝐍  𝐏𝐀𝐍𝐄𝐋</b>  ·  {mention}      ║\n"
            f"╚══════════════════════════════════════════╝\n\n"

            f"📊  <b>𝐋𝐈𝐕𝐄  𝐒𝐓𝐀𝐓𝐒</b>\n"
            f"╭──────────────────────────────────────────╮\n"
            f"│  📚  Questions     ›  <b>{q_count}</b>\n"
            f"│  👥  Users         ›  <b>{users}</b>\n"
            f"│  💬  Groups        ›  <b>{groups}</b>\n"
            f"│  ⚡  Active Chats  ›  <b>{chats}</b>\n"
            f"╰──────────────────────────────────────────╯\n\n"

            f"📝  <b>𝐐𝐔𝐈𝐙  𝐌𝐀𝐍𝐀𝐆𝐄𝐌𝐄𝐍𝐓</b>\n"
            f"╭──────────────────────────────────────────╮\n"
            f"│  /addquiz      ›  Add a new question\n"
            f"│  /editquiz     ›  Edit existing question\n"
            f"│  /delquiz      ›  Delete a question\n"
            f"│  /importquiz  ›  Bulk import (JSON)\n"
            f"╰──────────────────────────────────────────╯\n\n"

            f"🛠️  <b>𝐒𝐘𝐒𝐓𝐄𝐌  &amp;  𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓</b>\n"
            f"╭──────────────────────────────────────────╮\n"
            f"│  /broadcast       ›  Message all users\n"
            f"│  /delbroadcast  ›  Delete last broadcast\n"
            f"│  /reload           ›  Reload questions\n"
            f"│  /restart     ›  Restart bot\n"
            f"╰──────────────────────────────────────────╯\n\n"

            f"📈  <b>𝐀𝐍𝐀𝐋𝐘𝐓𝐈𝐂𝐒</b>\n"
            f"╭──────────────────────────────────────────╮\n"
            f"│  /botstats   ›  User &amp; group overview\n"
            f"│  /devstats   ›  Developer metrics\n"
            f"│  /activity    ›  Activity logs\n"
            f"╰──────────────────────────────────────────╯\n\n"

            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  🆔  Owner ID  ›  <code>{OWNER_ID}</code>"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Bot Stats",    callback_data="botstats"),
             InlineKeyboardButton("📡 Broadcast",    callback_data="broadcast_prompt")],
            [InlineKeyboardButton("🔄 Reload",       callback_data="reload_questions"),
             InlineKeyboardButton("🏠 Home",          callback_data="back_start")],
        ])
        if msg:
            ok = await self._edit(msg, text, kb)
            if not ok:
                await self._reply(update, text, reply_markup=kb)
        else:
            await self._reply(update, text, reply_markup=kb)

    # ─── /broadcast ──────────────────────────────────────────

    async def cmd_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not self._is_owner(user.id):
            await self._unauthorized(update)
            return

        msg      = update.effective_message
        reply_to = msg.reply_to_message if msg else None
        raw      = (msg.text or "").replace("/broadcast", "").replace("/bc", "").strip() if msg else ""

        if not raw and not reply_to:
            await self._reply(update,
                f"📡  <b>𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"╭──────────────────────────────────────╮\n"
                f"│  Send to all users &amp; groups at once\n"
                f"╰──────────────────────────────────────╯\n\n"
                f"  <b>Usage:</b>\n"
                f"  <code>/broadcast Your message here</code>\n"
                f"  ↳ or reply to any message with /broadcast\n\n"
                f"  Supports HTML  ·  Alias: <code>/bc</code>\n"
                f"  Delete last broadcast: <code>/delbroadcast</code>"
            )
            return

        if not self.db:
            await self._reply(update, "❌ Database not available.")
            return

        users  = self.db.get_pm_accessible_users()
        groups = self.db.get_all_groups()
        total  = len(users) + len(groups)
        mode_label = "📨 Forward message" if reply_to else "📝 Text message"

        status = await self._reply(update,
            f"📡  <b>𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓𝐈𝐍𝐆</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  {mode_label}\n"
            f"│  👥  Users   ›  <b>{len(users)}</b>\n"
            f"│  💬  Groups  ›  <b>{len(groups)}</b>\n"
            f"│  📊  Total   ›  <b>{total}</b> recipients\n"
            f"╰──────────────────────────────────────╯\n\n"
            f"  ⏳  Sending..."
        )

        sent = failed = 0
        sent_msgs: dict = {}
        from_cid  = reply_to.chat_id     if reply_to else None
        from_mid  = reply_to.message_id  if reply_to else None

        for u in users:
            try:
                if reply_to:
                    m = await context.bot.copy_message(
                        chat_id=u["user_id"], from_chat_id=from_cid, message_id=from_mid)
                else:
                    m = await context.bot.send_message(
                        chat_id=u["user_id"], text=raw, parse_mode=ParseMode.HTML)
                sent_msgs[str(u["user_id"])] = m.message_id
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
                if reply_to:
                    m = await context.bot.copy_message(
                        chat_id=g["chat_id"], from_chat_id=from_cid, message_id=from_mid)
                else:
                    kwargs = {"chat_id": g["chat_id"], "text": raw, "parse_mode": ParseMode.HTML}
                    if tid: kwargs["message_thread_id"] = tid
                    m = await context.bot.send_message(**kwargs)
                sent_msgs[str(g["chat_id"])] = m.message_id
                sent += 1
                await asyncio.sleep(0.05)
            except TelegramError as e:
                if any(w in str(e).lower() for w in ("topic", "closed", "thread")):
                    try:
                        if reply_to:
                            m = await context.bot.copy_message(
                                chat_id=g["chat_id"], from_chat_id=from_cid, message_id=from_mid)
                        else:
                            m = await context.bot.send_message(
                                chat_id=g["chat_id"], text=raw, parse_mode=ParseMode.HTML)
                        sent_msgs[str(g["chat_id"])] = m.message_id
                        sent += 1
                    except Exception:
                        failed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"BC group {g.get('chat_id')}: {e}")
                failed += 1

        # Save for /delbroadcast
        if sent_msgs:
            try:
                self.db.save_broadcast({
                    "broadcast_id": f"bc_{int(time.time())}_{user.id}",
                    "admin_id":     user.id,
                    "messages":     sent_msgs,
                    "type":         "reply" if reply_to else "text",
                })
            except Exception as e:
                logger.warning(f"save_broadcast: {e}")

        rate = int(sent / total * 100) if total else 0
        result_text = (
            f"✅  <b>𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓  𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐄</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  ✅  Sent     ›  <b>{sent}</b>\n"
            f"│  ❌  Failed   ›  <b>{failed}</b>\n"
            f"│  📊  Total    ›  <b>{total}</b>\n"
            f"╰──────────────────────────────────────╯\n\n"
            f"  {UI.pbar(rate)}  <b>{rate}%</b> delivery rate\n\n"
            f"  🗑  To undo: <code>/delbroadcast</code>"
        )
        if status:
            ok = await self._edit(status, result_text)
            if not ok:
                await self._reply(update, result_text)
        else:
            await self._reply(update, result_text)

    # ─── /delbroadcast ────────────────────────────────────────

    async def cmd_delbroadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not self._is_owner(user.id):
            await self._unauthorized(update)
            return

        if not self.db:
            await self._reply(update, "❌ Database not available.")
            return

        bc = self.db.get_latest_broadcast()
        if not bc or not bc.get("messages"):
            await self._reply(update,
                f"🗑  <b>𝐃𝐄𝐋𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"  ❌  No broadcast found to delete."
            )
            return

        msgs  = bc.get("messages", {})
        total = len(msgs)
        bc_type = bc.get("type", "text")

        status = await self._reply(update,
            f"🗑  <b>𝐃𝐄𝐋𝐄𝐓𝐈𝐍𝐆  𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"  📊  {total} messages to delete...\n"
            f"  ⏳  Working..."
        )

        deleted = failed = 0
        for chat_id_str, msg_id in msgs.items():
            try:
                await context.bot.delete_message(
                    chat_id=int(chat_id_str), message_id=msg_id)
                deleted += 1
                await asyncio.sleep(0.04)
            except Exception:
                failed += 1

        try:
            bid = bc.get("id")
            if bid is not None:
                self.db.delete_broadcast(bid)
        except Exception as e:
            logger.warning(f"delete_broadcast DB: {e}")

        rate = int(deleted / total * 100) if total else 0
        result_text = (
            f"🗑  <b>𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓  𝐃𝐄𝐋𝐄𝐓𝐄𝐃</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  🗑  Deleted  ›  <b>{deleted}</b>\n"
            f"│  ❌  Failed   ›  <b>{failed}</b>  <i>(already gone)</i>\n"
            f"│  📊  Total    ›  <b>{total}</b>\n"
            f"╰──────────────────────────────────────╯\n\n"
            f"  {UI.pbar(rate)}  <b>{rate}%</b> removed"
        )
        if status:
            ok = await self._edit(status, result_text)
            if not ok:
                await self._reply(update, result_text)
        else:
            await self._reply(update, result_text)

    # ─── /reload ─────────────────────────────────────────────

    async def cmd_reload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        mention = UI.mention(user.id,
            OWNER_NAME if self._is_owner(user.id) else (user.first_name or "Admin"))
        msg = await self._reply(update, "🔄")
        try:
            old  = len(self.quiz_manager.questions)
            self.quiz_manager.reload_data()
            new  = len(self.quiz_manager.questions)
            diff = new - old
            sign = "+" if diff >= 0 else ""
            text = (
                f"✅  <b>𝐑𝐄𝐋𝐎𝐀𝐃  𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐄</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"  By {mention}\n\n"
                f"╭──────────────────────────────────────╮\n"
                f"│  📚  Questions  ›  <b>{new}</b>  <i>({sign}{diff})</i>\n"
                f"│  🗄  Source     ›  MongoDB Atlas\n"
                f"│  🔄  Cache      ›  ✅ Refreshed\n"
                f"╰──────────────────────────────────────╯"
            )
        except Exception as e:
            text = (
                f"❌  <b>𝐑𝐄𝐋𝐎𝐀𝐃  𝐅𝐀𝐈𝐋𝐄𝐃</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"  <code>{e}</code>"
            )
        if msg: await self._edit(msg, text)

    # ─── /restart ────────────────────────────────────────────

    async def cmd_restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not self._is_owner(user.id):
            await self._unauthorized(update)
            return

        mention = UI.mention(user.id, OWNER_NAME)
        await self._reply(update,
            f"🔄  <b>𝐑𝐄𝐒𝐓𝐀𝐑𝐓𝐈𝐍𝐆</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  By {mention}\n"
            f"│  ⏳  Shutting down gracefully...\n"
            f"│  ✅  Back online in seconds!\n"
            f"╰──────────────────────────────────────╯"
        )
        import sys
        os.makedirs("data", exist_ok=True)
        open("data/.restart_flag", "w").close()
        await asyncio.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    # ─── /importquiz ─────────────────────────────────────────

    async def cmd_importquiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        text = (
            f"📥  <b>𝐔𝐍𝐈𝐕𝐄𝐑𝐒𝐀𝐋  𝐈𝐌𝐏𝐎𝐑𝐓  𝐄𝐍𝐆𝐈𝐍𝐄</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"  Send a <b>.txt file</b> — any format.\n\n"
            f"📋  <b>𝐅𝐎𝐑𝐌𝐀𝐓𝐒  𝐒𝐔𝐏𝐏𝐎𝐑𝐓𝐄𝐃</b>\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  ◈  Inline MCQ  — Q+opts+ans one line\n"
            f"│  ◈  Multi-line  — opts on sep. lines\n"
            f"│  ◈  Answer key  — at end / per chapter\n"
            f"│  ◈  Solution bk — with explanations\n"
            f"│  ◈  True/False  — auto-converted\n"
            f"│  ◈  Exam PDFs   — OCR noise removed\n"
            f"│  ◈  Mixed files — all types together\n"
            f"╰──────────────────────────────────────╯\n\n"
            f"🧠  <b>𝐀𝐔𝐓𝐎  𝐃𝐄𝐓𝐄𝐂𝐓𝐈𝐎𝐍</b>\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  ✅  End-of-file answer key matching\n"
            f"│  ✅  Chapter-end answer key matching\n"
            f"│  ✅  Answer text → option mapping\n"
            f"│  ✅  Duplicate & near-dupe detection\n"
            f"│  ✅  Auto category tagging\n"
            f"│  ✅  PDF noise / page# removal\n"
            f"╰──────────────────────────────────────╯\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  <i>Drop any .txt question bank to begin →</i>"
        )
        await self._reply(update, text)

    # ─── DOCUMENT HANDLER — Bulk .txt import ─────────────────

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user

        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        doc = update.effective_message.document
        if not doc:
            return

        mention = UI.mention(user.id,
            OWNER_NAME if self._is_owner(user.id) else (user.first_name or "Admin"))

        fname  = doc.file_name or ""
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

        if doc.file_size and doc.file_size > 2 * 1024 * 1024:
            await self._reply(update,
                f"❌ <b>File Too Large</b>\n"
                f"{UI.LINE}\n\n"
                f"  Maximum size: 2 MB.\n"
                f"  Split into smaller files."
            )
            return

        msg = await self._reply(update,
            f"📥 <b>IMPORT STARTED</b>\n"
            f"{UI.LINE}\n\n"
            f"  By {mention}\n"
            f"  📄 <code>{fname}</code>\n"
            f"  Size: <code>{doc.file_size or 0:,} bytes</code>\n\n"
            f"  ⏳ Parsing questions..."
        )

        try:
            file_obj  = await context.bot.get_file(doc.file_id,
                read_timeout=60, write_timeout=60, connect_timeout=60)
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

        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw_bytes.decode("latin-1")
            except Exception:
                if msg:
                    await self._edit(msg,
                        f"❌ <b>Encoding Error</b>\n"
                        f"{UI.LINE}\n\n"
                        f"  Please save the file as UTF-8 and retry."
                    )
                return

        if msg:
            await self._edit(msg,
                f"📥 <b>IMPORT STARTED</b>\n"
                f"{UI.LINE}\n\n"
                f"  By {mention}\n"
                f"  📄 <code>{fname}</code>\n\n"
                f"  🔍 Analyzing {len(text.splitlines())} lines..."
            )

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

        detected    = result.get("total_detected", 0)
        imported    = result.get("imported", 0)
        skipped     = result.get("skipped", 0)
        failed      = result.get("failed", 0)
        errors      = result.get("errors", [])
        auto_fixed  = result.get("auto_fixed", 0)
        key_applied = result.get("key_applied", 0)
        fmt         = result.get("format_detected", "MCQ")
        lines_scnd  = result.get("lines_scanned", 0)
        total_q     = len(self.quiz_manager.questions)

        rate = int(imported / max(detected, 1) * 100)

        extra = ""
        if key_applied:
            extra += f"│  🗝  Key Match  ›  <b>{key_applied}</b> answers from key\n"
        if auto_fixed:
            extra += f"│  🔧  Repaired   ›  <b>{auto_fixed}</b> auto-fixed\n"

        text_out = (
            f"📊  <b>𝐈𝐌𝐏𝐎𝐑𝐓  𝐑𝐄𝐏𝐎𝐑𝐓</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"  By {mention}\n"
            f"  📄 <code>{fname}</code>\n"
            f"  🧠 <i>{fmt}</i>\n\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  📄  Scanned   ›  <b>{lines_scnd}</b> lines\n"
            f"│  🔍  Detected  ›  <b>{detected}</b> questions\n"
            f"│  ✅  Imported  ›  <b>{imported}</b>\n"
            f"│  ⏭  Skipped   ›  <b>{skipped}</b>  <i>(duplicates)</i>\n"
            f"{extra}"
            f"│  ❌  Invalid   ›  <b>{failed}</b>\n"
            f"│  📦  Total DB  ›  <b>{total_q}</b>\n"
            f"╰──────────────────────────────────────╯\n\n"
            f"  {UI.pbar(rate)}  <b>{rate}%</b> success rate\n"
        )
        if errors:
            text_out += f"\n<b>Issues:</b>\n"
            for err in errors[:3]:
                text_out += f"  <code>{str(err)[:65]}</code>\n"

        text_out += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n  <i>Use /quiz to test your new questions!</i>"

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🟢 Play Quiz", callback_data="play_quiz"),
        ]])
        if msg:
            await self._edit(msg, text_out, kb)
        else:
            await self._reply(update, text_out, reply_markup=kb)

    # ─── INLINE QUIZ ANSWER (fallback mode) ───────────────────

    async def _handle_inline_quiz_answer(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str
    ):
        """Handle answer taps on inline-keyboard fallback quizzes."""
        query = update.callback_query
        try:
            # data format: aq_ans_{q_id}_{chosen}_{correct}
            parts   = data.split("_")
            chosen  = int(parts[4])
            correct = int(parts[5])
        except (IndexError, ValueError):
            return

        user_id    = query.from_user.id
        is_correct = (chosen == correct)

        try:
            self.quiz_manager.record_attempt(user_id, is_correct)
        except Exception:
            pass

        icon = "✅" if is_correct else "❌"
        result_text = "Correct!" if is_correct else "Wrong answer."
        try:
            await query.answer(f"{icon} {result_text}", show_alert=False)
        except Exception:
            pass

    # ─── ERROR HANDLER ────────────────────────────────────────

    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        from telegram.error import TimedOut, NetworkError
        if isinstance(context.error, (TimedOut, NetworkError)):
            logger.debug(f"Network error (ignored): {context.error}")
        else:
            logger.error(f"Unhandled error: {context.error}", exc_info=context.error)

    # ─── CALLBACK HANDLER ─────────────────────────────────────

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        data  = query.data

        if   data == "play_quiz":   await self.cmd_quiz(update, context)
        elif data == "my_stats":    await self.cmd_stats(update, context)
        elif data == "help":        await self.cmd_help(update, context)
        elif data == "back_start":  await self.cmd_start(update, context)

        elif data == "leaderboard":
            await self._show_leaderboard(update, context, mode="global", page=1)

        elif data == "lb_noop":
            pass  # disabled nav button / page indicator — already answered

        elif data and data.startswith("lbp_"):
            # Paginated navigation: lbp_{mode}_{page}
            parts = data.split("_")
            mode  = parts[1] if len(parts) > 1 else "global"
            try:
                pg = int(parts[2]) if len(parts) > 2 else 1
            except ValueError:
                pg = 1
            if mode not in ("global", "weekly", "monthly", "group"):
                mode = "global"
            await self._show_leaderboard(update, context, mode=mode, page=pg,
                                         edit_msg=query.message)

        # ── Legacy aliases (kept for old messages) ──
        elif data == "lb_global":
            await self._show_leaderboard(update, context, mode="global", page=1,
                                         edit_msg=query.message)
        elif data == "lb_weekly":
            await self._show_leaderboard(update, context, mode="weekly", page=1,
                                         edit_msg=query.message)
        elif data == "lb_monthly":
            await self._show_leaderboard(update, context, mode="monthly", page=1,
                                         edit_msg=query.message)

        elif data == "achievements":
            await self.cmd_achievements(update, context)

        elif data == "botstats":
            await self.cmd_botstats(update, context)

        elif data == "reload_questions":
            await self.cmd_reload(update, context)

        elif data == "broadcast_prompt":
            await query.message.reply_text(
                f"📡  <b>𝐁𝐑𝐎𝐀𝐃𝐂𝐀𝐒𝐓</b>\n\n"
                f"Send your message using the command:\n"
                f"  <code>/broadcast Your message here</code>\n\n"
                f"Alias: <code>/bc</code>",
                parse_mode=ParseMode.HTML
            )

        elif data == "categories":
            await self.cmd_categories(update, context)

        elif data == "devstats_prompt":
            await self.cmd_botstats(update, context)

        elif data and data.startswith("aq_ans_"):
            await self._handle_inline_quiz_answer(update, context, data)
