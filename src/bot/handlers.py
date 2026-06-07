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
        "legal":     ("⚖️",  "Legal Reasoning"),
        "english":   ("📖",  "English"),
        "gk":        ("🌐",  "General Knowledge"),
        "current":   ("📰",  "Current Affairs"),
        "polity":    ("🏛️",  "Polity"),
        "math":      ("🔢",  "Mathematics"),
        "reasoning": ("🧠",  "Logical Reasoning"),
        "history":   ("📜",  "History"),
        "default":   ("📚",  "General"),
    }

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
        self.quiz_manager             = quiz_manager
        self.db                       = db_manager
        self.application: Optional[Application] = None
        self._dev                     = None
        self._del_page: dict          = {}

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
        app.add_handler(CommandHandler("ping",        self.cmd_ping))
        app.add_handler(CommandHandler("info",        self.cmd_info))

        # Admin commands
        app.add_handler(CommandHandler("addquiz",     self.cmd_addquiz))
        app.add_handler(CommandHandler("importquiz",  self.cmd_importquiz))
        app.add_handler(CommandHandler("delquiz",     self.cmd_delquiz))
        app.add_handler(CommandHandler("editquiz",    self.cmd_editquiz))
        app.add_handler(CommandHandler("dev",         self.cmd_dev))
        app.add_handler(CommandHandler("broadcast",   self.cmd_broadcast))
        app.add_handler(CommandHandler("bc",          self.cmd_broadcast))
        app.add_handler(CommandHandler("reload",      self.cmd_reload))
        app.add_handler(CommandHandler("restart",     self.cmd_restart))

        # Poll + Callbacks
        app.add_handler(PollAnswerHandler(self.handle_poll_answer))
        app.add_handler(CallbackQueryHandler(
            self._cb_delquiz, pattern=r"^dq_"))
        app.add_handler(CallbackQueryHandler(self.handle_callback))

        # Bulk import: .txt file
        app.add_handler(MessageHandler(
            filters.Document.TXT | filters.Document.TEXT,
            self.handle_document))

        # Dev module
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
            logger.error(f"_edit error: {e}")
            return False

    async def _unauthorized(self, update: Update):
        """Professional access denied — auto-deletes after 7s."""
        user    = update.effective_user
        mention = UI.mention(user.id, user.first_name or "User")
        text = (
            f"🔒 <b>ACCESS RESTRICTED</b>\n"
            f"{UI.LINE}\n\n"
            f"  {mention}, this command requires\n"
            f"  elevated privileges.\n\n"
            f"  ◈ Owner or Developer access only.\n\n"
            f"{UI.THIN}\n"
            f"  <i>Contact {COMMUNITY} for access.</i>"
        )
        msg = await self._reply(update, text)
        await asyncio.sleep(7)
        try:
            if msg:
                await msg.delete()
            await update.effective_message.delete()
        except Exception:
            pass

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

        prog_bar = UI.pbar(rate)
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
            text = (
                f"🎓  <b>𝐂𝐋𝐀𝐓 𝐕𝐈𝐒𝐈𝐎𝐍</b>  ·  Quiz Academy\n\n"
                f"🌟  <b>Welcome,</b>  {mention}!\n"
                f"<i>Use /quiz to start practising!</i>"
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
            f"╰──────────────────────────────────────────╯\n"
            f"  📚  <i>Topics:</i>  <code>legal  ·  english  ·  gk</code>\n"
            f"  <code>           polity  ·  history  ·  reasoning</code>\n\n"

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
        await self._reply(update, text, reply_markup=kb)

    # ─── /ping ───────────────────────────────────────────────

    async def cmd_ping(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        t0  = time.time()
        msg = await self._reply(update, "🏓 <i>Measuring latency...</i>")
        ms  = int((time.time() - t0) * 1000)
        if not msg:
            return

        q_count = len(self.quiz_manager.questions)
        bar     = UI.bar(min(100, ms / 10))
        if   ms < 100: status = "⚡ Blazing fast"
        elif ms < 300: status = "✅ Fast"
        elif ms < 600: status = "🟡 Normal"
        else:          status = "🔴 Slow"

        text = (
            f"🏓 <b>PONG</b>\n"
            f"{UI.LINE}\n\n"
            f"  Latency   ›  <code>{ms} ms</code>\n"
            f"  [{bar}]\n"
            f"  Status    ›  <b>{status}</b>\n\n"
            f"  Questions ›  <b>{q_count}</b> loaded\n"
            f"  Bot       ›  🟢 Online\n\n"
            f"{UI.LINE}\n"
            f"  <i>CLAT Vision Quiz Bot</i>"
        )
        await self._edit(msg, text)

    # ─── /info ───────────────────────────────────────────────

    async def cmd_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat      = update.effective_chat
        thread_id = get_thread_id(update)
        q_count   = len(self.quiz_manager.questions)
        is_forum  = getattr(chat, "is_forum", False)

        text = (
            f"ℹ️ <b>BOT INFORMATION</b>\n"
            f"{UI.LINE}\n\n"
            f"<b>BOT</b>\n"
            f"  Name      ›  CLAT Vision Quiz Bot\n"
            f"  Questions ›  <b>{q_count}</b>\n"
            f"  Database  ›  MongoDB Atlas ✅\n"
            f"  Owner     ›  {OWNER_NAME}\n\n"
            f"<b>THIS CHAT</b>\n"
            f"  ID    ›  <code>{chat.id}</code>\n"
            f"  Type  ›  <code>{chat.type}</code>\n"
            f"  Forum ›  <code>{is_forum}</code>\n"
        )
        if thread_id:
            text += f"  Topic ›  <code>{thread_id}</code>\n"
        text += (
            f"\n{UI.LINE}\n"
            f"  ⚡ {COMMUNITY}  ·  CLAT 2027"
        )
        await self._reply(update, text)

    # ─── /quiz ───────────────────────────────────────────────

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
                + "  The question bank is empty.\n\n"
                "  Use /addquiz to add questions."
            )
            await self._reply(update, text, reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🟠 Try Again", callback_data="play_quiz")
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
                f"📚 {cat}  ·  🆔 Q#{q_id}"
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
                self.db.upsert_user(user_id, {
                    "user_id":       user_id,
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
        acc_bar         = UI.bar(rate)
        rank_pos        = self._get_user_rank_position(user.id)
        pos_text        = f"#{rank_pos}" if rank_pos else "—"

        acc_pbar = UI.pbar(rate)

        text = (
            f"🏆  <b>𝐒𝐂𝐎𝐑𝐄𝐂𝐀𝐑𝐃</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"  {mention}\n\n"
            f"╭──────────────────────────────────────╮\n"
            f"│  🎖  <b>Rank</b>       ›  {rank_txt}  <i>({grade})</i>\n"
            f"│  📈  <b>Level</b>      ›  {level_txt}\n"
            f"│  🌍  <b>Position</b>  ›  <b>{pos_text} Global</b>\n"
            f"╰──────────────────────────────────────╯\n\n"
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
        await self._reply(update, text, reply_markup=kb)

    # ─── /stats ──────────────────────────────────────────────

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user    = update.effective_user
        mention = UI.mention(user.id, user.first_name or "User")

        msg = await self._reply(update, "📊 <i>Crunching your analytics...</i>")
        await asyncio.sleep(0.4)

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
        acc_bar         = UI.bar(rate)
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
        await self._reply(update, "\n".join(lines), reply_markup=kb)

    # ─── /botstats ───────────────────────────────────────────

    async def cmd_botstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = await self._reply(update, "📊 <i>Loading analytics...</i>")
        await asyncio.sleep(0.4)

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
        if msg:
            ok = await self._edit(msg, text)
            if not ok:
                await self._reply(update, text)
        else:
            await self._reply(update, text)

    # ─── /leaderboard ────────────────────────────────────────

    async def cmd_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._show_leaderboard(update, context, mode="global")

    async def _show_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                mode: str = "global", edit_msg=None):
        """
        mode: 'global' | 'weekly' | 'monthly' | 'group'
        edit_msg: message to edit (for callback updates)
        """
        chat      = update.effective_chat
        thread_id = get_thread_id(update)
        is_group  = chat.type in ("group", "supergroup")

        # Show initial loading only when not editing
        if edit_msg is None:
            wait_msg = await self._reply(update, "🏆 <i>Loading rankings...</i>")
            await asyncio.sleep(0.3)
        else:
            wait_msg = None

        # Determine leaderboard data source
        if is_group and mode == "global":
            mode = "group"

        if mode == "group":
            data    = self.quiz_manager.get_group_leaderboard(chat.id)
            lb      = data.get("leaderboard", [])
            total_q = data.get("total_quizzes", 0)
            acc_g   = data.get("group_accuracy", 0)
            title   = f"🏆 <b>GROUP LEADERBOARD</b>"
            footer  = f"\n  Attempts: <b>{total_q}</b>  ·  Group accuracy: <b>{acc_g}%</b>"
        elif mode == "weekly" and self.db:
            lb      = self.db.get_leaderboard_by_period(days=7)
            title   = "🏆 <b>WEEKLY LEADERBOARD</b>  <i>(last 7 days)</i>"
            footer  = ""
        elif mode == "monthly" and self.db:
            lb      = self.db.get_leaderboard_by_period(days=30)
            title   = "🏆 <b>MONTHLY LEADERBOARD</b>  <i>(last 30 days)</i>"
            footer  = ""
        else:
            lb      = self.quiz_manager.get_leaderboard()
            title   = "🏆 <b>GLOBAL LEADERBOARD</b>  <i>(all time)</i>"
            footer  = ""

        if not lb:
            text = (
                f"🏆  <b>𝐋𝐄𝐀𝐃𝐄𝐑𝐁𝐎𝐀𝐑𝐃</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "  No scores yet — be the first! 🥇\n\n"
                "  Use /quiz to start playing."
            )
            if edit_msg:
                await self._edit(edit_msg, text)
            elif wait_msg:
                await self._edit(wait_msg, text)
            return

        lines = [f"{title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"]

        for i, entry in enumerate(lb[:10]):
            uid   = entry.get("user_id")
            score = entry.get("correct_answers", entry.get("score", 0))
            acc   = entry.get("accuracy", 0)
            pos   = i + 1

            display = f"User {str(uid)[-4:]}"
            if uid == OWNER_ID:
                display = OWNER_NAME
            elif self.db:
                try:
                    doc = self.db.users_col.find_one(
                        {"user_id": uid}, {"name": 1, "username": 1})
                    if doc:
                        display = (doc.get("name") or doc.get("username") or display)[:20]
                except Exception:
                    pass

            mention = UI.mention(uid, display)

            if pos == 1:
                lines.append(f"\n🥇  {mention}\n     ▸  <b>{score} correct</b>  ·  <i>{acc}% accuracy</i>")
            elif pos == 2:
                lines.append(f"\n🥈  {mention}\n     ▸  <b>{score} correct</b>  ·  <i>{acc}% accuracy</i>")
            elif pos == 3:
                lines.append(f"\n🥉  {mention}\n     ▸  <b>{score} correct</b>  ·  <i>{acc}% accuracy</i>")
            else:
                lines.append(f"\n  <b>{pos}.</b>  {mention}  ·  <b>{score} pts</b>  <i>{acc}%</i>")

        if footer:
            lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{footer}")

        lines.append(f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n  <i>Play /quiz to climb the ranks! 🚀</i>")
        text = "\n".join(lines)

        # Leaderboard tab buttons — semantic colors
        if is_group or mode == "group":
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("🎯 Play Quiz", callback_data="play_quiz"),
                InlineKeyboardButton("📊 My Stats",  callback_data="my_stats"),
            ]])
        else:
            global_btn  = InlineKeyboardButton(
                "🌍 Global ✦" if mode == "global"  else "🌍 Global",
                callback_data="lb_global")
            weekly_btn  = InlineKeyboardButton(
                "📅 Weekly ✦" if mode == "weekly"  else "📅 Weekly",
                callback_data="lb_weekly")
            monthly_btn = InlineKeyboardButton(
                "🗓 Monthly ✦" if mode == "monthly" else "🗓 Monthly",
                callback_data="lb_monthly")
            kb = InlineKeyboardMarkup([
                [global_btn, weekly_btn, monthly_btn],
                [InlineKeyboardButton("🎯 Play Quiz", callback_data="play_quiz"),
                 InlineKeyboardButton("📊 My Stats",  callback_data="my_stats")],
            ])

        if edit_msg:
            await self._edit(edit_msg, text, kb)
        elif wait_msg:
            await self._edit(wait_msg, text, kb)
        else:
            await self._reply(update, text, reply_markup=kb)

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
            f"➕ <b>ADD QUESTION</b>\n"
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
        await asyncio.sleep(0.3)

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
                f"✅ <b>QUESTION ADDED</b>\n"
                f"{UI.LINE}\n\n"
                f"  Added by {mention}\n\n"
                f"<b>PREVIEW</b>\n"
                f"{UI.THIN}\n"
                f"  {question[:65]}{'…' if len(question) > 65 else ''}\n\n"
                f"  A: {options[0]}\n  B: {options[1]}\n"
                f"  C: {options[2]}\n  D: {options[3]}\n\n"
                f"  ✅ Answer   ›  Option {correct+1} — <b>{options[correct]}</b>\n"
                f"  📂 Category ›  <b>{category}</b>\n\n"
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

        if msg: await self._edit(msg, "\n".join(lines))

    # ─── /dev ────────────────────────────────────────────────

    async def cmd_dev(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        if self._dev and hasattr(self._dev, "dev"):
            await self._dev.dev(update, context)
            return

        msg = await self._reply(update, "🛠️ <i>Loading developer panel...</i>")
        await asyncio.sleep(0.3)

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
            f"│  /broadcast  ›  Message all users\n"
            f"│  /reload      ›  Reload questions\n"
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

        if self._dev and hasattr(self._dev, "broadcast"):
            await self._dev.broadcast(update, context)
            return

        raw = (update.effective_message.text or "")\
            .replace("/broadcast", "").replace("/bc", "").strip()

        if not raw:
            await self._reply(update,
                f"📡 <b>BROADCAST</b>\n"
                f"{UI.LINE}\n\n"
                "<b>Usage:</b>\n"
                "  <code>/broadcast Your message here</code>\n\n"
                "Supports HTML: <code>&lt;b&gt;</code> <code>&lt;i&gt;</code>\n"
                "Alias: <code>/bc</code>"
            )
            return

        if not self.db:
            await self._reply(update, "❌ Database not available.")
            return

        users  = self.db.get_pm_accessible_users()
        groups = self.db.get_all_groups()
        total  = len(users) + len(groups)

        status = await self._reply(update,
            f"📡 <b>BROADCASTING</b>\n"
            f"{UI.LINE}\n\n"
            f"  By {OWNER_NAME}\n\n"
            f"  Users  ›  <b>{len(users)}</b>\n"
            f"  Groups ›  <b>{len(groups)}</b>\n"
            f"  Total  ›  <b>{total}</b>\n\n"
            f"  <i>Sending...</i>"
        )

        sent = failed = 0
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
                if any(w in str(e).lower() for w in ("topic", "closed", "thread")):
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
                f"  Sent    ›  <b>{sent}</b>\n"
                f"  Failed  ›  <b>{failed}</b>\n"
                f"  Rate    ›  [{UI.bar(rate)}] <b>{rate}%</b>"
            )

    # ─── /reload ─────────────────────────────────────────────

    async def cmd_reload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not await self._is_authorized(user.id):
            await self._unauthorized(update)
            return

        mention = UI.mention(user.id,
            OWNER_NAME if self._is_owner(user.id) else (user.first_name or "Admin"))
        msg = await self._reply(update, "🔄 <i>Syncing from MongoDB...</i>")
        await asyncio.sleep(0.4)

        try:
            old = len(self.quiz_manager.questions)
            self.quiz_manager.reload_data()
            new  = len(self.quiz_manager.questions)
            diff = new - old
            sign = "+" if diff >= 0 else ""
            text = (
                f"✅ <b>RELOAD COMPLETE</b>\n"
                f"{UI.LINE}\n\n"
                f"  By {mention}\n\n"
                f"  Questions ›  <b>{new}</b>  <i>({sign}{diff})</i>\n"
                f"  Source    ›  MongoDB Atlas\n"
                f"  Cache     ›  ✅ Refreshed"
            )
        except Exception as e:
            text = (
                f"❌ <b>RELOAD FAILED</b>\n"
                f"{UI.LINE}\n\n"
                f"  Error: <code>{e}</code>"
            )
        if msg: await self._edit(msg, text)

    # ─── /restart ────────────────────────────────────────────

    async def cmd_restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not self._is_owner(user.id):
            await self._unauthorized(update)
            return

        await self._reply(update,
            f"🔄 <b>RESTARTING</b>\n"
            f"{UI.LINE}\n\n"
            f"  Initiated by {OWNER_NAME}\n"
            f"  Shutting down gracefully...\n"
            f"  ✅ Back online in seconds!"
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
            f"📥 <b>BULK IMPORT</b>\n"
            f"{UI.LINE}\n\n"
            f"  Send a <b>.txt file</b> to this chat.\n\n"
            f"<b>AUTO-DETECTED FORMATS</b>\n"
            f"{UI.THIN}\n"
            f"  ◈ Numbered  —  1. / Q1:\n"
            f"  ◈ Options   —  A) B) C) D)\n"
            f"  ◈ Answer    —  Answer: B / Ans: 2\n"
            f"  ◈ Inline    —  All on same line\n"
            f"  ◈ Asterisk  —  C) opt *\n\n"
            f"<b>PROTECTION</b>\n"
            f"{UI.THIN}\n"
            f"  ✅ Duplicate detection\n"
            f"  ✅ Format validation\n"
            f"  ✅ Auto category tagging\n"
            f"  ✅ Import report\n\n"
            f"{UI.LINE}\n"
            f"  <i>Send your .txt file to begin →</i>"
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

        detected = result.get("total_detected", 0)
        imported = result.get("imported", 0)
        skipped  = result.get("skipped", 0)
        failed   = result.get("failed", 0)
        errors   = result.get("errors", [])
        total_q  = len(self.quiz_manager.questions)

        rate = int(imported / max(detected, 1) * 100)
        bar  = UI.bar(rate)

        text_out = (
            f"📊 <b>IMPORT REPORT</b>\n"
            f"{UI.LINE}\n\n"
            f"  By {mention}\n"
            f"  📄 <code>{fname}</code>\n\n"
            f"<b>RESULTS</b>\n"
            f"{UI.THIN}\n"
            f"  Detected  ›  <b>{detected}</b>\n"
            f"  Imported  ›  <b>{imported}</b>\n"
            f"  Skipped   ›  <b>{skipped}</b>  <i>(duplicates)</i>\n"
            f"  Failed    ›  <b>{failed}</b>\n\n"
            f"  Success   ›  [{bar}] <b>{rate}%</b>\n\n"
            f"  📦 Total in DB: <b>{total_q}</b>\n"
        )
        if errors:
            text_out += f"\n<b>ERRORS (first {min(len(errors), 3)}):</b>\n"
            for err in errors[:3]:
                text_out += f"  <code>{str(err)[:65]}</code>\n"

        text_out += f"\n{UI.LINE}\n  <i>Use /quiz to test your new questions!</i>"

        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🟢 Play Quiz", callback_data="play_quiz"),
        ]])
        if msg:
            await self._edit(msg, text_out, kb)
        else:
            await self._reply(update, text_out, reply_markup=kb)

    # ─── CALLBACK HANDLER ─────────────────────────────────────

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data  = query.data

        if   data == "play_quiz":   await self.cmd_quiz(update, context)
        elif data == "my_stats":    await self.cmd_stats(update, context)
        elif data == "help":        await self.cmd_help(update, context)
        elif data == "back_start":  await self.cmd_start(update, context)

        elif data == "leaderboard":
            await self._show_leaderboard(update, context, mode="global")

        elif data == "lb_global":
            await self._show_leaderboard(update, context, mode="global",
                                         edit_msg=query.message)

        elif data == "lb_weekly":
            await self._show_leaderboard(update, context, mode="weekly",
                                         edit_msg=query.message)

        elif data == "lb_monthly":
            await self._show_leaderboard(update, context, mode="monthly",
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
