import os
import logging
from flask import Flask, request, jsonify
from bot import create_application, PENDING_PAYMENTS
from product_service import ProductService
import asyncio
from telegram import Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
product_service = ProductService()

# Telegram bot application
application = create_application()
bot = application.bot

# -------------------------------
# Telegram webhook
# -------------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        json_update = request.get_json(force=True)
        update = Update.de_json(json_update, bot)
        asyncio.get_event_loop().create_task(application.update_queue.put(update))
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500


# -------------------------------
# M-Pesa callback
# -------------------------------
@app.route("/mpesa-callback", methods=["POST"])
def mpesa_callback():
    try:
        data = request.get_json()
        callback_data = data.get('Body', {}).get('stkCallback', {})
        result_code = callback_data.get('ResultCode')
        checkout_request_id = callback_data.get('CheckoutRequestID')

        if result_code == 0:
            payment_info = PENDING_PAYMENTS.get(checkout_request_id)
            if payment_info:
                user_id = payment_info["user_id"]
                product_id = payment_info["product_id"]
                product = product_service.get_product(product_id)

                if product:
                    download_link = product['pixeldrain_link']
                    message = f"""
✅ Payment confirmed!

📦 Product: {product['name']}
🔗 Download Link: {download_link}

Thank you for your purchase!
"""
                    asyncio.get_event_loop().create_task(bot.send_message(chat_id=user_id, text=message))

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


# -------------------------------
# Webhook setup
# -------------------------------
def set_webhook():
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set")
        return

    url = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    try:
        bot.set_webhook(url)
        logger.info(f"Webhook set successfully: {url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")


set_webhook()


# -------------------------------
# Run Flask + bot
# -------------------------------
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(application.initialize())
    loop.create_task(application.start())
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
