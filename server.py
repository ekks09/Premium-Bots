# server.py
import os
import logging
from flask import Flask, request, jsonify
from bot import handle_update, send_message, PENDING_PAYMENTS, product_service
from product_service import ProductService
from mpesa_handler import MpesaHandler  # this is our Paystack handler
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
product_service = ProductService()
paystack = MpesaHandler()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # e.g. https://your-render-app.onrender.com

if not TELEGRAM_BOT_TOKEN:
    logger.error("Missing TELEGRAM_BOT_TOKEN environment variable")
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN")

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
        handle_update(update_json)
        return "OK", 200
    except Exception as e:
        logger.exception("Webhook handling failed: %s", e)
        return "Error", 500

# Paystack webhook receiver
@app.route("/paystack-webhook", methods=["POST"])
def paystack_webhook():
    try:
        # raw_body needed to verify signature
        raw_body = request.get_data()
        signature = request.headers.get("x-paystack-signature", "")
        if not paystack.verify_webhook_signature(raw_body, signature):
            logger.warning("Invalid Paystack webhook signature.")
            return jsonify({"status": "error", "message": "invalid signature"}), 400

        payload = request.get_json(force=True)
        logger.info("Paystack webhook payload: %s", payload)

        event = payload.get("event")
        data = payload.get("data", {})

        # handle charge.success (completed payment)
        if event == "charge.success":
            reference = data.get("reference")
            status = data.get("status")
            logger.info("charge.success received for %s status=%s", reference, status)

            if status == "success":
                pending = PENDING_PAYMENTS.get(reference)
                if pending:
                    user_id = pending["user_id"]
                    product_id = pending["product_id"]
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
                else:
                    logger.warning("No pending payment match for reference: %s", reference)
            else:
                logger.warning("charge.success but status != success for %s: %s", reference, status)

        # respond 200 quickly
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.exception("Error processing Paystack webhook: %s", e)
        return jsonify({"status": "error", "message": "failed"}), 500

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
