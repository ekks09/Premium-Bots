# server.py
import os
import logging
from flask import Flask, request, jsonify
from bot import handle_update, send_message, PENDING_PAYMENTS
from product_service import ProductService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
product_service = ProductService()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-render-app.onrender.com

if not TELEGRAM_BOT_TOKEN:
    logger.error("Missing TELEGRAM_BOT_TOKEN environment variable")
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN")

# Health and index
@app.route("/", methods=["GET"])
def index():
    return "Bot is running."

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

# Telegram webhook receiver
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update_json = request.get_json(force=True)
        logger.info("Received update: %s", update_json)
        # delegate to bot handler (synchronous)
        handle_update(update_json)
        return "OK", 200
    except Exception as e:
        logger.exception("Webhook handling failed: %s", e)
        return "Error", 500

# M-Pesa STK callback route (Daraja will POST here)
@app.route("/mpesa-callback", methods=["POST"])
def mpesa_callback():
    try:
        data = request.get_json(force=True)
        logger.info("M-Pesa callback received: %s", data)

        # Common structure for Daraja STK push callback:
        callback_data = data.get("Body", {}).get("stkCallback", {}) or {}
        result_code = callback_data.get("ResultCode")
        checkout_request_id = callback_data.get("CheckoutRequestID")
        callback_metadata = callback_data.get("CallbackMetadata", {})

        if result_code == 0 or str(result_code) == "0":
            # successful payment
            logger.info("Payment success for checkout: %s", checkout_request_id)
            payment_info = PENDING_PAYMENTS.get(checkout_request_id)
            if payment_info:
                user_id = payment_info["user_id"]
                product_id = payment_info["product_id"]
                # Get product link from ProductService
                product = product_service.get_product(product_id)
                if product:
                    download_link = product.get("pixeldrain_link", "No link available")
                    message = (
                        "✅ Payment confirmed!\n\n"
                        f"📦 Product: {product['name']}\n"
                        f"🔗 Download Link: {download_link}\n\n"
                        "Thank you for your purchase!"
                    )
                    try:
                        send_message(chat_id=user_id, text=message)
                        logger.info("Download link sent to user %s", user_id)
                    except Exception as e:
                        logger.exception("Failed to send Telegram message: %s", e)
                # remove pending payment
                del PENDING_PAYMENTS[checkout_request_id]
            else:
                logger.warning("No pending payment match for checkout: %s", checkout_request_id)
        else:
            logger.warning("Payment failed or canceled for checkout %s: %s", checkout_request_id, callback_data.get("ResultDesc"))

        # Daraja expects a 200 JSON response
        return jsonify({"ResultCode": 0, "ResultDesc": "Success"})

    except Exception as e:
        logger.exception("Error processing M-Pesa callback: %s", e)
        return jsonify({"ResultCode": 1, "ResultDesc": "Failed"}), 500


def set_telegram_webhook():
    """Set Telegram webhook to WEBHOOK_URL + /webhook (called at startup)."""
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set; webhook will not be registered automatically.")
        return
    url = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    # Build the setWebhook call (use bot send)
    try:
        from bot import set_webhook as bot_set_hook
        bot_set_hook(url)
        logger.info("Set Telegram webhook to %s", url)
    except Exception as e:
        logger.exception("Failed to set webhook: %s", e)


# set webhook at startup (Render will import/run this file)
set_telegram_webhook()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
