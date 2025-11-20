# server.py
import os
import logging
from flask import Flask, request, jsonify
from bot import handle_update, send_message, PENDING_PAYMENTS, set_webhook
from paystack_handler import PaystackHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
paystack_handler = PaystackHandler()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

@app.route("/", methods=["GET"])
def index():
    return "Bot is running."

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update_json = request.get_json(force=True)
        handle_update(update_json)
        return "OK", 200
    except Exception as e:
        logger.exception("Webhook handling failed: %s", e)
        return "Error", 500

@app.route("/paystack-callback", methods=["POST"])
def paystack_callback():
    try:
        data = request.get_json(force=True)
        event = data.get("event")
        if event != "charge.success":
            return jsonify({"status": "ignored"}), 200

        reference = data.get("data", {}).get("reference")
        if not reference:
            return jsonify({"status": "failed"}), 400

        payment_info = PENDING_PAYMENTS.get(reference)
        if not payment_info:
            return jsonify({"status": "unknown_reference"}), 404

        verification = paystack_handler.verify_payment(reference)
        if verification.get("status") != "success":
            return jsonify({"status": "failed_verification"}), 400

        user_id = payment_info["user_id"]
        message = (
            "🎉 Payment confirmed!\n\n"
            f"📦 {verification['product_name']}\n"
            f"🔗 {verification['download_link']}\n\n"
            "Enjoy your product!"
        )

        send_message(chat_id=user_id, text=message)
        del PENDING_PAYMENTS[reference]

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.exception("Callback error: %s", e)
        return jsonify({"status": "error"}), 500

def set_telegram_webhook():
    try:
        from bot import TELEGRAM_TOKEN
        webhook_url = f"{request.url_root}telegram-webhook"
        tele_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}"
        requests.get(tele_url)
        logger.info(f"Webhook set to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set Telegram webhook: {e}")


