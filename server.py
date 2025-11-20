# server.py
import os
import logging
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot import start, show_products, handle_product_selection, handle_phone_number, help_command

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-render-app.onrender.com

if not BOT_TOKEN:
    logger.error("Missing TELEGRAM_BOT_TOKEN environment variable")
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN")

# --- Telegram Application Setup ---
telegram_app = Application.builder().token(BOT_TOKEN).build()

# Register handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("products", show_products))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CallbackQueryHandler(handle_product_selection))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_number))

# Start the bot in async background
import asyncio
asyncio.create_task(telegram_app.initialize())  # Prepares the app (PTB v20+)
asyncio.create_task(telegram_app.start())       # Starts the bot background tasks

# --- Flask routes ---
@app.route("/", methods=["GET"])
def index():
    return "Bot is running."


@app.route("/webhook", methods=["POST"])
def webhook():
    """Receive updates from Telegram webhook."""
    json_update = request.get_json(force=True)
    update = Update.de_json(json_update, telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "OK", 200


@app.before_first_request
def set_webhook():
    """Register Telegram webhook on first request."""
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set; webhook will not be registered automatically.")
        return

    url = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    logger.info(f"Registering webhook at: {url}")
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            params={"url": url},
            timeout=10
        )
        logger.info("setWebhook response: %s", resp.text)
    except Exception as e:
        logger.exception("Failed to set webhook: %s", e)
