"""
Flask web app for CLAT Vision Quiz Bot.
BUG FIX: create_app() now accepts an injected db_manager so it reuses the
existing DatabaseManager instead of creating a second connection.
New routes: /api/metrics, /api/users, /api/broadcast, /api/reload
"""

import os
import logging
import asyncio
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response
from telegram import Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Module-level singletons
quiz_manager  = None
telegram_bot  = None
db_manager    = None
event_loop    = None
loop_thread   = None
app_start_time = datetime.now()


def start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def run_coroutine_threadsafe(coro, loop):
    if loop and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, loop)

        def done_callback(fut):
            try:
                fut.result()
            except Exception as e:
                logger.error(f"Update processing error: {e}", exc_info=True)

        future.add_done_callback(done_callback)
    else:
        logger.error("Event loop not running, cannot process update")


def create_app(injected_db=None, injected_quiz=None):
    """
    Flask app factory.
    BUG FIX: accepts pre-built db/quiz managers so we don't open a second
    MongoDB connection when both the bot and Flask share the same process.
    """
    global quiz_manager, db_manager

    session_secret = os.environ.get("SESSION_SECRET", "fallback_secret_dev")

    flask_app = Flask(
        __name__,
        template_folder=os.path.join(root_dir, 'templates'),
        static_folder=os.path.join(root_dir, 'static')
    )
    flask_app.secret_key = session_secret

    # Use injected managers (polling mode) or create new ones (standalone)
    if injected_db:
        db_manager   = injected_db
        quiz_manager = injected_quiz
    elif quiz_manager is None:
        try:
            from src.core.database import DatabaseManager
            from src.core.quiz import QuizManager
            db_manager   = DatabaseManager()
            quiz_manager = QuizManager(db_manager=db_manager)
            logger.info("QuizManager initialized in Flask app factory")
        except Exception as e:
            logger.error(f"Failed to initialize managers in app factory: {e}")
            raise

    return flask_app


# ── Deferred proxy ────────────────────────────────────────────────────────────

class _AppProxy:
    """Proxy that defers Flask app creation until first use."""

    def __init__(self):
        self._real_app = None
        self._deferred = []

    def _get_real_app(self):
        if self._real_app is None:
            self._real_app = create_app()
            for method, args, kwargs, func in self._deferred:
                getattr(self._real_app, method)(*args, **kwargs)(func)
            self._deferred.clear()
        return self._real_app

    def route(self, *args, **kwargs):
        def decorator(func):
            self._deferred.append(('route', args, kwargs, func))
            return func
        return decorator

    def __call__(self, environ, start_response):
        return self._get_real_app()(environ, start_response)

    def __getattr__(self, name):
        return getattr(self._get_real_app(), name)


app = _AppProxy()


# ── Webhook bot helpers ───────────────────────────────────────────────────────

def get_app():
    return app._get_real_app()


async def _bot_lifecycle():
    """Single coroutine that inits, starts, and keeps the bot running forever.
    Runs in one persistent event loop — same loop used for process_update calls."""
    global telegram_bot

    from src.core.database import DatabaseManager
    from src.core.quiz import QuizManager
    from src.bot.handlers import TelegramQuizBot

    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not token:
        raise ValueError("TELEGRAM_TOKEN not set")

    mongo_url = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
    db_mgr    = DatabaseManager(mongo_url=mongo_url)
    q_mgr     = QuizManager(db_manager=db_mgr)
    bot       = TelegramQuizBot(q_mgr, db_manager=db_mgr)

    create_app(injected_db=db_mgr, injected_quiz=q_mgr)

    webhook_url = os.environ.get("WEBHOOK_URL", "")
    render_url  = os.environ.get("RENDER_URL", "")
    final_url   = (render_url or webhook_url).rstrip("/") + "/webhook"

    await bot.initialize_webhook(token, final_url)
    await bot.application.start()   # start the dispatcher — required in PTB v20+
    telegram_bot = bot
    logger.info("✅ Telegram bot ready (background init complete)")

    await asyncio.Event().wait()    # run forever until process exits


def init_bot_webhook(webhook_url: str):
    """Launch bot lifecycle in a background thread; event_loop set before thread
    starts so the webhook route can use it immediately (no race condition)."""
    global event_loop

    new_loop      = asyncio.new_event_loop()
    event_loop    = new_loop          # assign first — webhook route reads this

    def _run():
        asyncio.set_event_loop(new_loop)
        try:
            new_loop.run_until_complete(_bot_lifecycle())
        except Exception as e:
            logger.error(f"❌ Bot lifecycle error: {e}", exc_info=True)

    threading.Thread(target=_run, daemon=True, name="bot-main").start()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'bot': 'CLAT Vision Quiz Bot'})


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'uptime_s': int((datetime.now() - app_start_time).total_seconds())})


@app.route('/admin')
def admin_panel():
    return render_template('admin.html')


@app.route('/webhook', methods=['POST'])
def webhook():
    global telegram_bot, event_loop
    try:
        if not telegram_bot or not telegram_bot.application:
            return jsonify({'status': 'error', 'message': 'Bot not initialized'}), 500

        update_data = request.get_json(force=True)
        if not update_data:
            return jsonify({'status': 'ok'}), 200

        update = Update.de_json(update_data, telegram_bot.application.bot)
        run_coroutine_threadsafe(
            telegram_bot.application.process_update(update), event_loop)
        return jsonify({'status': 'ok'}), 200

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── Admin API ─────────────────────────────────────────────────────────────────

@app.route('/api/questions', methods=['GET'])
def api_get_questions():
    if not quiz_manager:
        return jsonify({'error': 'Not ready'}), 500
    qs = quiz_manager.questions  # already formatted with category
    return jsonify({'questions': qs, 'total': len(qs)})


@app.route('/api/questions', methods=['POST'])
def api_add_question():
    try:
        if not quiz_manager:
            return jsonify({'success': False, 'error': 'Not ready'}), 500
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data'}), 400

        result = quiz_manager.add_questions([{
            'question':       data['question'],
            'options':        data['options'],
            'correct_answer': int(data['correct_answer']),
            'category':       data.get('category', 'General'),
        }])

        added = result.get('added', 0) if isinstance(result, dict) else 0
        if added > 0:
            # Get new ID from the last added question
            new_id = None
            if quiz_manager.questions:
                last_q = quiz_manager.questions[-1]
                new_id = last_q.get('id') if isinstance(last_q, dict) else None
            return jsonify({'success': True, 'id': new_id})
        elif result.get('rejected', {}).get('duplicates', 0) > 0:
            return jsonify({'success': False, 'error': 'Duplicate question'}), 409
        else:
            errors = result.get('errors', [])
            return jsonify({'success': False, 'error': errors[0] if errors else 'Unknown'}), 500

    except KeyError as e:
        return jsonify({'success': False, 'error': f'Missing field: {e}'}), 400
    except Exception as e:
        logger.error(f"api_add_question: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/questions/<int:qid>', methods=['PUT'])
def api_edit_question(qid):
    try:
        if not quiz_manager:
            return jsonify({'success': False, 'error': 'Not ready'}), 500
        data = request.get_json()
        ok   = quiz_manager.edit_question_by_db_id(qid, data)
        return jsonify({'success': ok}) if ok else (jsonify({'success': False, 'error': 'Not found'}), 404)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/questions/<int:qid>', methods=['DELETE'])
def api_delete_question(qid):
    try:
        if not quiz_manager:
            return jsonify({'success': False, 'error': 'Not ready'}), 500
        ok = quiz_manager.delete_question_by_db_id(qid)
        return jsonify({'success': ok}) if ok else (jsonify({'success': False, 'error': 'Not found'}), 404)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/metrics')
def api_metrics():
    try:
        if db_manager:
            data = db_manager.get_metrics_summary()
            if quiz_manager:
                data['total_questions'] = len(quiz_manager.questions)
            return jsonify(data)
        return jsonify({'error': 'DB not ready'}), 500
    except Exception as e:
        logger.error(f"api_metrics: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/users')
def api_users():
    try:
        if not db_manager:
            return jsonify({'users': [], 'error': 'DB not ready'}), 500
        users = db_manager.get_all_users_stats()
        return jsonify({'users': users, 'total': len(users)})
    except Exception as e:
        return jsonify({'users': [], 'error': str(e)}), 500


@app.route('/api/broadcast', methods=['POST'])
def api_broadcast():
    try:
        if not db_manager:
            return jsonify({'error': 'DB not ready'}), 500
        data    = request.get_json()
        message = (data or {}).get('message', '').strip()
        if not message:
            return jsonify({'error': 'Empty message'}), 400

        users  = db_manager.get_pm_accessible_users()
        groups = db_manager.get_all_groups()
        # Return counts (actual sending needs the bot; this is the admin API stub)
        return jsonify({
            'queued': True,
            'users':  len(users),
            'groups': len(groups),
            'total':  len(users) + len(groups),
            'sent':   0,
            'failed': 0,
            'note':   'Use /broadcast command in Telegram for live sending.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reload', methods=['POST'])
def api_reload():
    try:
        if not quiz_manager:
            return jsonify({'success': False, 'error': 'Not ready'}), 500
        quiz_manager.reload_data()
        return jsonify({'success': True, 'total': len(quiz_manager.questions)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/metrics')
def prometheus_metrics():
    """Prometheus/plain-text metrics endpoint."""
    try:
        uptime = (datetime.now() - app_start_time).total_seconds()
        lines  = [f"bot_uptime_seconds {uptime:.0f}"]

        if db_manager:
            d = db_manager.get_metrics_summary()
            for k, v in d.items():
                try:
                    lines.append(f"bot_{k} {float(v):.2f}")
                except (TypeError, ValueError):
                    pass

        if quiz_manager:
            lines.append(f"bot_questions_loaded {len(quiz_manager.questions)}")

        return Response('\n'.join(lines) + '\n', mimetype='text/plain')
    except Exception as e:
        return Response(f"# Error: {e}\n", mimetype='text/plain'), 500
