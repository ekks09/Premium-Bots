# server.py
import os
import logging
from flask import Flask, request, jsonify
from telegram import Bot
from paystack_handler import PRODUCTS
from bot import PENDING_PAYMENTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)

DOWNLOAD_LINK = "https://pixeldrain.com/u/aakwH36V"

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Bot server running"}), 200

@app.route("/paystack-callback", methods=["POST"])
def paystack_callback():
    try:
        data = request.get_json(force=True)
        logger.info("Paystack webhook: %s", data)

        event = data.get("event")
        if event != "charge.success":
            return jsonify({"status": "ignored"}), 200

        reference = data["data"].get("reference")
        payment = PENDING_PAYMENTS.pop(reference, None)

        if not payment:
            return jsonify({"error": "reference not found"}), 404

        user_id = payment["user_id"]

        bot.send_message(chat_id=user_id, text=f"Payment confirmed 🎉\nHere’s your download:\n{DOWNLOAD_LINK}")

        return jsonify({"status": "sent"}), 200

    except Exception as e:
        logger.error(f"callback error: {e}")
        return jsonify({"error": "server error"}), 500

if __name__ == "__main__":
    app.run(port=5000)
