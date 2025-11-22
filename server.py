# server.py
import os
import logging
from flask import Flask, request, jsonify
from telegram import Bot
from paystack_handler import PaystackHandler
from bot import PENDING_PAYMENTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
paystack = PaystackHandler()

@app.route("/")
def home():
    return "Bot alive", 200

@app.route("/paystack-callback", methods=["GET", "POST"])
def paystack_callback():
    try:
        data = request.args if request.method == "GET" else request.json
        reference = data.get("reference")

        if not reference:
            return jsonify({"status": False, "message": "Missing reference"}), 400

        result = paystack.verify_payment(reference)

        if result.get("status") == "success":
            payment_data = PENDING_PAYMENTS.pop(reference, None)
            if not payment_data:
                logger.warning("Payment received but reference not found: %s", reference)
                return jsonify({"status": True, "message": "Payment verified but no session found"})

            user_id = payment_data["user_id"]
            product_name = result["product_name"]
            link = result["download_link"]

            bot.send_message(
                chat_id=user_id,
                text=f"🎉 Payment confirmed for *{product_name}*!\n\nDownload here:\n{link}",
                parse_mode="Markdown"
            )
            return jsonify({"status": True, "message": "Delivered"})

        return jsonify({"status": False, "message": "Payment not successful"})

    except Exception as e:
        logger.exception("Error in callback: %s", e)
        return jsonify({"status": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
