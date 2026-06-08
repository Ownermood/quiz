import dns.resolver
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ["8.8.8.8", "8.8.4.4"]

"""
CLAT Vision Quiz Bot — Entry point
"""

import os
import sys
import logging
import asyncio
import threading
from datetime import datetime
from waitress import serve
from src.core.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.INFO)


def send_restart_confirmation_sync(config: Config):
    restart_flag_path = "data/.restart_flag"
    if not os.path.exists(restart_flag_path):
        return
    try:
        async def _send():
            from telegram import Bot
            bot = Bot(token=config.telegram_token)
            await bot.send_message(
                chat_id=config.owner_id,
                text=(
                    "✅ Bot restarted and is online!\n\n"
                    f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    "⚡ All systems operational"
                )
            )
        asyncio.run(_send())
        os.remove(restart_flag_path)
        logger.info("Restart confirmation sent to owner")
    except Exception as e:
        logger.error(f"Restart confirmation failed: {e}")


def cleanup_webhook_sync(token: str):
    async def _cleanup():
        from telegram import Bot
        from telegram.error import NetworkError, TimedOut
        for attempt in range(3):
            try:
                bot = Bot(token=token)
                webhook_info = await bot.get_webhook_info()
                if webhook_info.url:
                    logger.info(f"⚠️  Found webhook: {webhook_info.url} — deleting…")
                    await bot.delete_webhook(drop_pending_updates=True)
                    logger.info("✅ Webhook deleted")
                    await asyncio.sleep(2)
                else:
                    logger.info("✅ No webhook — polling mode ready")
                return
            except (NetworkError, TimedOut) as e:
                if attempt < 2:
                    logger.warning(f"Webhook cleanup attempt {attempt+1}/3: {e}")
                    await asyncio.sleep(3)
                else:
                    logger.warning(f"Webhook cleanup skipped (network timeout) — continuing in polling mode")
                    return
    asyncio.run(_cleanup())


def run_polling_mode(config: Config):
    from src.core.database import DatabaseManager
    from src.core.quiz import QuizManager
    import src.web.app as web_app

    logger.info("🚀 Starting in POLLING mode")

    cleanup_webhook_sync(config.telegram_token)

    mongo_url = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
    db_mgr = DatabaseManager(mongo_url=mongo_url)
    logger.info("✅ Shared DatabaseManager created")

    quiz_mgr = QuizManager(db_manager=db_mgr)

    real_flask = web_app.create_app(injected_db=db_mgr, injected_quiz=quiz_mgr)

    flask_thread = threading.Thread(
        target=lambda: serve(real_flask, host=config.host, port=config.port, threads=4),
        daemon=True
    )
    flask_thread.start()
    logger.info(f"✅ Flask (Waitress) on {config.host}:{config.port}")
    logger.info(f"   Admin panel: http://localhost:{config.port}/admin")

    send_restart_confirmation_sync(config)

    async def _run_all():
        from src.bot.handlers import TelegramQuizBot
        from src.utils.scheduler import AutoQuizScheduler

        bot = TelegramQuizBot(quiz_mgr, db_manager=db_mgr)
        await bot.initialize(config.telegram_token)
        logger.info("✅ Bot initialized — handlers registered")
        logger.info(f"✅ Questions loaded: {len(quiz_mgr.questions)}")

        # Pre-populate active_chats from MongoDB groups for restart resilience
        try:
            groups = db_mgr.get_all_groups()
            for g in groups:
                cid = g.get("chat_id")
                if cid and cid not in quiz_mgr.active_chats:
                    quiz_mgr.active_chats.append(cid)
            if groups:
                logger.info(f"✅ Pre-loaded {len(groups)} active groups from DB")
        except Exception as e:
            logger.warning(f"Could not pre-load groups: {e}")

        scheduler = AutoQuizScheduler(bot, quiz_mgr, db_manager=db_mgr, interval_minutes=30)

        logger.info("🎯 Bot is live! Listening for messages… (Ctrl+C to stop)")
        async with bot.application:
            await bot.application.start()
            scheduler.start()

            # ── Startup greetings ──────────────────────────────
            try:
                from src.core.config import OWNER_ID
                from telegram import InlineKeyboardMarkup, InlineKeyboardButton

                total_q = len(quiz_mgr.questions)
                total_u = len(db_mgr.get_pm_accessible_users()) if db_mgr else 0
                total_g = len(db_mgr.get_all_groups()) if db_mgr else 0
                now     = datetime.now().strftime("%d %b %Y  •  %I:%M %p")

                # ── Owner: technical status card ──
                if OWNER_ID:
                    owner_msg = (
                        f"🌿  <b>𝐂𝐋𝐀𝐓  𝐕𝐈𝐒𝐈𝐎𝐍  —  𝐁𝐎𝐓  𝐋𝐈𝐕𝐄</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"  👋  Assalamu Alaikum, Owner!\n"
                        f"  All systems are up and running.\n\n"
                        f"╭──────────────────────────────────────╮\n"
                        f"│  🕒  {now}\n"
                        f"│  📚  Questions  ›  <b>{total_q:,}</b>\n"
                        f"│  👥  Users      ›  <b>{total_u:,}</b>\n"
                        f"│  💬  Groups     ›  <b>{total_g:,}</b>\n"
                        f"╰──────────────────────────────────────╯\n\n"
                        f"  ⚡  Ready · /dev for controls"
                    )
                    await bot.application.bot.send_message(
                        chat_id=OWNER_ID, text=owner_msg, parse_mode="HTML")
                    logger.info("✅ Owner startup card sent")

                # ── All PM users: warm greeting broadcast ──
                users = db_mgr.get_pm_accessible_users() if db_mgr else []
                if users:
                    user_greeting = (
                        f"🌸  <b>𝐂𝐋𝐀𝐓  𝐕𝐈𝐒𝐈𝐎𝐍  𝐈𝐒  𝐁𝐀𝐂𝐊!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"  Assalamu Alaikum! 🌙\n\n"
                        f"╭──────────────────────────────────────╮\n"
                        f"│  Your CLAT Quiz Bot is online &amp;\n"
                        f"│  ready to power your preparation! 🚀\n"
                        f"╰──────────────────────────────────────╯\n\n"
                        f"  📚  <b>{total_q:,}</b> questions ready to quiz you\n"
                        f"  🏆  Leaderboard &amp; streaks updated\n"
                        f"  🎯  New questions may have been added\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"  Let's go — your rank awaits! 💪"
                    )
                    kb = InlineKeyboardMarkup([[
                        InlineKeyboardButton("🎯 Play Quiz",      callback_data="play_quiz"),
                        InlineKeyboardButton("🏆 Leaderboard",    callback_data="leaderboard"),
                    ]])
                    sent = 0
                    for u in users:
                        if u.get("user_id") == OWNER_ID:
                            continue  # owner already got the status card
                        try:
                            await bot.application.bot.send_message(
                                chat_id=u["user_id"],
                                text=user_greeting,
                                parse_mode="HTML",
                                reply_markup=kb,
                            )
                            sent += 1
                            await asyncio.sleep(0.05)
                        except Exception:
                            pass
                    logger.info(f"✅ Startup greeting sent to {sent} users")

                # ── Groups: brief online notice ──
                groups = db_mgr.get_all_groups() if db_mgr else []
                if groups:
                    group_msg = (
                        f"🌸  <b>𝐂𝐋𝐀𝐓  𝐕𝐈𝐒𝐈𝐎𝐍  𝐈𝐒  𝐁𝐀𝐂𝐊!</b>\n\n"
                        f"  Assalamu Alaikum! 🌙\n"
                        f"  Your quiz bot is online and ready.\n\n"
                        f"  📚  <b>{total_q:,}</b> questions  ·  🏆 Leaderboard live\n\n"
                        f"  Tap below to start! 🎯"
                    )
                    grp_kb = InlineKeyboardMarkup([[
                        InlineKeyboardButton("🎯 Start Quiz", callback_data="play_quiz"),
                    ]])
                    for g in groups:
                        try:
                            await bot.application.bot.send_message(
                                chat_id=g["chat_id"],
                                text=group_msg,
                                parse_mode="HTML",
                                reply_markup=grp_kb,
                            )
                            await asyncio.sleep(0.05)
                        except Exception:
                            pass
                    logger.info(f"✅ Startup notice sent to {len(groups)} groups")

            except Exception as e:
                logger.warning(f"Startup greeting error: {e}")
            await bot.application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "poll_answer", "callback_query"],
            )
            try:
                await asyncio.Event().wait()
            finally:
                scheduler.stop()
                await bot.application.updater.stop()
                await bot.application.stop()

    asyncio.run(_run_all())


config = Config.load(validate=False)

if __name__ == "__main__":
    try:
        config.validate()
        mode = config.get_mode()

        if mode == "webhook":
            logger.info("🌐 WEBHOOK MODE")
            from src.web.app import get_app, init_bot_webhook
            webhook_url = config.get_webhook_url()
            if webhook_url:
                logger.info(f"✅ Webhook URL: {webhook_url}")
                init_bot_webhook(webhook_url)
            else:
                logger.error("❌ WEBHOOK_URL not set!")
            app = get_app()
            app.run(host=config.host, port=config.port, debug=False)
        else:
            run_polling_mode(config)

    except KeyboardInterrupt:
        logger.info("👋 Shutdown requested — bye!")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
