# server.py
import os
import logging
from flask import Flask, request, jsonify
from bot import create_application, PENDING_PAYMENTS
from product_service import ProductService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Telegram bot application - using Updater for PTB v13.x
updater = create_application()
product_service = ProductService()

# ----------------- Webhook for Telegram -----------------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        json_data = request.get_json(force=True)
        update = updater.bot.get_updates([json_data])[0]
        updater.dispatcher.process_update(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500

# ----------------- M-Pesa callback -----------------
@app.route("/mpesa-callback", methods=["POST"])
def mpesa_callback():
    try:
        data = request.get_json()
        logger.info(f"M-Pesa callback: {data}")

        callback_data = data.get("Body", {}).get("stkCallback", {})
        result_code = callback_data.get("ResultCode")
        checkout_request_id = callback_data.get("CheckoutRequestID")

        if result_code == 0 and checkout_request_id in PENDING_PAYMENTS:
            payment = PENDING_PAYMENTS[checkout_request_id]
            user_id = payment["user_id"]
            product_id = payment["product_id"]
            product = product_service.get_product(product_id)

            if product:
                message = (
                    f"✅ Payment confirmed!\n\n"
                    f"📦 Product: {product['name']}\n"
                    f"🔗 Download Link: {product['pixeldrain_link']}\n\n"
                    "Thank you for your purchase!"
                )
                try:
                    updater.bot.send_message(chat_id=user_id, text=message)
                    logger.info(f"Sent download link to {user_id}")
                except Exception as e:
                    logger.error(f"Failed to send message to {user_id}: {e}")

            del PENDING_PAYMENTS[checkout_request_id]
        else:
            logger.warning(f"Payment failed or not found: {checkout_request_id}")

        return jsonify({"ResultCode": 0, "ResultDesc": "Success"})

    except Exception as e:
        logger.error(f"Callback error: {e}")
        return jsonify({"ResultCode": 1, "ResultDesc": "Failed"}), 500

# ----------------- Health check -----------------
@app.route("/", methods=["GET"])
def index():
    return "Bot is running."

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

# ----------------- Set webhook on startup -----------------
def set_webhook():
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set")
        return
    
    url = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    try:
        updater.bot.set_webhook(url)
        logger.info(f"Webhook set successfully: {url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

# Set webhook when app starts
set_webhook()

# ----------------- Run Flask -----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
