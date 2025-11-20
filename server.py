# server.py
import os
import logging
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from bot import start, show_products, handle_product_selection, handle_phone_number, help_command

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not BOT_TOKEN:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN environment variable")

# Async Application for python-telegram-bot v20+
application = Application.builder().token(BOT_TOKEN).build()

# Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("products", show_products))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CallbackQueryHandler(handle_product_selection))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_number))

# Webhook route
@app.route("/webhook", methods=["POST"])
def webhook():
    json_update = request.get_json(force=True)
    update = Update.de_json(json_update, application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "Bot is running."

# Set webhook
@app.before_first_request
def set_webhook():
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set; webhook won't be registered automatically.")
        return
    url = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
            params={"url": url},
            timeout=10
        )
        logger.info("Webhook response: %s", resp.text)
    except Exception as e:
        logger.exception("Failed to set webhook: %s", e)
