# server.py
import os
import logging
from flask import Flask, request, jsonify
from bot import create_application, PENDING_PAYMENTS
from product_service import ProductService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app_app = create_application()
product_service = ProductService()

@app.route("/webhook", methods=["POST"])
def webhook():
    """Telegram updates via webhook"""
    try:
        json_update = request.get_json(force=True)
        update = app_app.bot.de_json(json_update)
        app_app.update_queue.put_nowait(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500

@app.route("/mpesa-callback", methods=["POST"])
def mpesa_callback():
    try:
        data = request.get_json()
        callback = data.get("Body", {}).get("stkCallback", {})
        result_code = callback.get("ResultCode")
        checkout_request_id = callback.get("CheckoutRequestID")

        if result_code == 0:
            payment_info = PENDING_PAYMENTS.get(checkout_request_id)
            if payment_info:
                user_id = payment_info["user_id"]
                product_id = payment_info["product_id"]
                product = product_service.get_product(product_id)
                if product:
                    download_link = product["pixeldrain_link"]
                    msg = f"✅ Payment confirmed!\n📦 {product['name']}\n🔗 {download_link}"
                    try:
                        app_app.bot.send_message(chat_id=user_id, text=msg)
                        logger.info(f"Sent download link to user {user_id}")
                    except Exception as e:
                        logger.error(f"Send message failed: {e}")
                del PENDING_PAYMENTS[checkout_request_id]
        return jsonify({"ResultCode": 0, "ResultDesc": "Success"})
    except Exception as e:
        logger.error(f"Callback error: {e}")
        return jsonify({"ResultCode": 1, "ResultDesc": "Failed"}), 500

@app.route("/", methods=["GET"])
def index():
    return "Bot is running."

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
