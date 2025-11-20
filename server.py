import os
import logging
import requests
from flask import Flask, request
from bot import create_application

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TELEGRAM_TOKEN:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN environment variable")

# Create the application using the function from bot.py
application = create_application()

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

# Set webhook when the server starts
if WEBHOOK_URL:
    # Set the webhook for Telegram
    url = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
            params={"url": url},
            timeout=10
        )
        logger.info("Webhook set response: %s", resp.text)
    except Exception as e:
        logger.exception("Failed to set webhook: %s", e)
