import re

with open('/data/data/com.termux/files/home/cv-quiz/main.py', 'r') as f:
    content = f.read()

old = '''def run_polling_mode(config: Config):
    from src.core.database import DatabaseManager
    from src.core.quiz import QuizManager
    import src.web.app as web_app                                          
    logger.info("🚀 Starting in POLLING mode")

    # 1. Clean any existing webhook (uses its own asyncio.run)
    cleanup_webhook_sync(config.telegram_token)                            
    # 2. Create shared DB + quiz managers
    mongo_url = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
    db_mgr    = DatabaseManager(mongo_url=mongo_url)
    logger.info("✅ Shared DatabaseManager created")
                                                                               quiz_mgr  = QuizManager(db_manager=db_mgr)

    # 3. Inject into Flask (no second DB connection)
    real_flask = web_app.create_app(injected_db=db_mgr, injected_quiz=quiz_mgr)

    # 4. Flask runs in a background daemon thread
    flask_thread = threading.Thread(
        target=lambda: serve(real_flask, host=config.host, port=config.port, threads=4),
        daemon=True                                                            )
    flask_thread.start()
    logger.info(f"✅ Flask (Waitress) on {config.host}:{config.port}")
    logger.info(f"   Admin panel: http://localhost:{config.port}/admin")
                                                                               # 5. Init bot (uses its own asyncio.run — loop closed after)
    bot = setup_bot_sync(config.telegram_token, quiz_mgr, db_mgr)
                                                                               # 6. Send restart confirmation if flag exists
    send_restart_confirmation_sync(config)
                                                                               logger.info(f"✅ Questions loaded: {len(quiz_mgr.questions)}")
    logger.info("🎯 Bot is live! Listening for messages… (Ctrl+C to stop)")
                                                                               # 7. run_polling() is a BLOCKING sync call — it creates its own event loop.
    #    close_loop=False means the loop stays alive for clean restart via execv.
    bot.application.run_polling(
        drop_pending_updates=True,                                                 allowed_updates=["message", "poll_answer", "callback_query"],
    )'''

new = '''def run_polling_mode(config: Config):
    from src.core.database import DatabaseManager
    from src.core.quiz import QuizManager
    import src.web.app as web_app
    logger.info("🚀 Starting in POLLING mode")

    mongo_url = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
    db_mgr    = DatabaseManager(mongo_url=mongo_url)
    logger.info("✅ Shared DatabaseManager created")
    quiz_mgr  = QuizManager(db_manager=db_mgr)

    real_flask = web_app.create_app(injected_db=db_mgr, injected_quiz=quiz_mgr)

    flask_thread = threading.Thread(
        target=lambda: serve(real_flask, host=config.host, port=config.port, threads=4),
        daemon=True
    )
    flask_thread.start()
    logger.info(f"✅ Flask (Waitress) on {config.host}:{config.port}")
    logger.info(f"   Admin panel: http://localhost:{config.port}/admin")

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

    asyncio.run(_run_all())'''

if old.split('\n')[0] in content:
    content = content.replace(old, new)
    print("✅ Pattern matched and replaced!")
else:
    print("❌ Pattern not matched — trying line-based fix...")

with open('/data/data/com.termux/files/home/cv-quiz/main.py', 'w') as f:
    f.write(content)
