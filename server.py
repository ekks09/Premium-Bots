# server.py
import os
import logging
from flask import Flask, request, jsonify
from bot import create_application, PENDING_PAYMENTS
from product_service import ProductService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Telegram bot application
application = create_application()
product_service = ProductService()

# ----------------- Webhook for Telegram -----------------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = application.bot.update_queue.put_nowait(request.get_json(force=True))
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
                    application.bot.send_message(chat_id=user_id, text=message)
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

# ----------------- Run Flask -----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
