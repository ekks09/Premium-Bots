import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application

from bot import start, show_products, handle_product_selection, handle_phone_number, help_command

# Create Flask app
app = Flask(__name__)

# Your bot token from environment variable
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Telegram application
application = (
    Application.builder()
    .token(BOT_TOKEN)
    .build()
)

# Register handlers
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("products", show_products))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CallbackQueryHandler(handle_product_selection))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_number))


# Telegram webhook URL
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-app-name.herokuapp.com/webhook


@app.route("/webhook", methods=["POST"])
def webhook():
    json_update = request.get_json(force=True)
    update = Update.de_json(json_update, application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200


@app.route("/", methods=["GET"])
def index():
    return "Bot is running."


if __name__ == "__main__":
    # Start webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 8443)),
        url_path="webhook",
        webhook_url=WEBHOOK_URL
    )
