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
                    raise RuntimeError(f"Webhook cleanup failed: {e}")
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
        bot = TelegramQuizBot(quiz_mgr, db_manager=db_mgr)
        await bot.initialize(config.telegram_token)
        logger.info("✅ Bot initialized — handlers registered")
        logger.info(f"✅ Questions loaded: {len(quiz_mgr.questions)}")
        logger.info("🎯 Bot is live! Listening for messages… (Ctrl+C to stop)")
        await bot.application.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "poll_answer", "callback_query"],
        )

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
