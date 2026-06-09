"""WSGI entry point — imports Flask app and starts bot background thread."""

import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the Flask app directly — routes are registered at import time
from src.web.app import app, init_bot_webhook  # noqa: E402

# Start the Telegram bot in background if token + webhook URL are available
_token       = os.environ.get("TELEGRAM_TOKEN", "")
_webhook_url = os.environ.get("WEBHOOK_URL", "").rstrip("/")
_render_url  = os.environ.get("RENDER_URL", "").rstrip("/")
_base_url    = _render_url or _webhook_url

if _token and _base_url:
    logger.info(f"Starting webhook bot → {_base_url}/webhook")
    init_bot_webhook(_base_url)
    logger.info("✅ Bot background thread started")
else:
    logger.warning("TELEGRAM_TOKEN or WEBHOOK_URL missing — bot not started")

logger.info("✅ WSGI app ready")

# 'app' is re-exported here so Gunicorn (src.web.wsgi:app) finds it
