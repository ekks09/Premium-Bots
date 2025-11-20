# server.py
import os
import logging
from flask import Flask, request
from bot import create_application

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Create the Telegram application using your existing function
application = create_application()

# Webhook route
@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming Telegram updates via webhook"""
    try:
        json_update = request.get_json(force=True)
        update = type('Update', (object,), json_update)  # Simple object creation
        application.update_queue.put_nowait(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500

@app.route("/", methods=["GET"])
def index():
    return "Bot is running."

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

# Set webhook on startup
def set_webhook():
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not WEBHOOK_URL or not BOT_TOKEN:
        logger.warning("WEBHOOK_URL or TELEGRAM_BOT_TOKEN not set")
        return
    
    url = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    try:
        # Use the bot instance from your application
        result = application.bot.set_webhook(url)
        logger.info(f"Webhook set successfully: {url}")
        return result
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

# Set webhook when the app starts
set_webhook()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
