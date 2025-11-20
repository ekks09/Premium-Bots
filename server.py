# server.py
import os
import logging
from flask import Flask, request, jsonify
from bot import handle_update, send_message, PENDING_PAYMENTS
from product_service import ProductService
from paystack_handler import PaystackHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
product_service = ProductService()
paystack_handler = PaystackHandler()

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

# Paystack webhook route
@app.route("/paystack-callback", methods=["POST"])
def paystack_callback():
    try:
        data = request.get_json(force=True)
        logger.info("Paystack webhook received: %s", data)

        # Verify event type
        event = data.get("event")
        if event != "charge.success":
            logger.info("Ignoring non-success event: %s", event)
            return jsonify({"status": "ignored"}), 200

        # Extract reference
        reference = data.get("data", {}).get("reference")
        if not reference:
            logger.warning("No reference found in Paystack webhook")
            return jsonify({"status": "failed"}), 400

        payment_info = PENDING_PAYMENTS.get(reference)
        if not payment_info:
            logger.warning("No pending payment match for reference: %s", reference)
            return jsonify({"status": "unknown_reference"}), 404

        user_id = payment_info["user_id"]
        product_id = payment_info["product_id"]

        # Optionally verify with Paystack API for extra security
        verification = paystack_handler.verify_payment(reference)
        if verification.get("status") != "success":
            logger.warning("Paystack verification failed or not successful for reference: %s", reference)
            return jsonify({"status": "failed_verification"}), 400

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
        del PENDING_PAYMENTS[reference]

        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.exception("Error processing Paystack callback: %s", e)
        return jsonify({"status": "error"}), 500


def set_telegram_webhook():
    """Set Telegram webhook to WEBHOOK_URL + /webhook (called at startup)."""
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set; webhook will not be registered automatically.")
        return
    url = f"{WEBHOOK_URL.rstrip('/')}/webhook"
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
