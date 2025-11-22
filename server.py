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

@app.route("/", methods=["GET"])
def index():
    return "OK", 200

@app.route("/paystack-callback", methods=["POST"])
def paystack_callback():
    try:
        payload = request.get_json(force=True)
        logger.info("Paystack webhook payload: %s", payload)

        # Optional: verify x-paystack-signature header here in production
        event = payload.get("event")
        if event != "charge.success":
            logger.info("Ignoring event: %s", event)
            return jsonify({"status": "ignored"}), 200

        reference = payload.get("data", {}).get("reference")
        if not reference:
            logger.warning("No reference in webhook payload")
            return jsonify({"status": "bad_request"}), 400

        # Optional: server-side verify for extra safety
        verify = paystack.verify_payment(reference)
        if not verify.get("ok"):
            logger.error("Webhook verify failed for %s: %s", reference, verify)
            return jsonify({"status": "verify_failed", "detail": verify}), 400

        pending = PENDING_PAYMENTS.get(reference)
        if not pending:
            logger.warning("No pending payment for reference %s", reference)
            # still return 200 to Paystack to avoid retries, but log it
            return jsonify({"status": "ok", "message": "no_session_found"}), 200

        user_id = pending["user_id"]
        product = verify["data"]["product"]
        link = product.get("pixeldrain_link", "No link")
        bot.send_message(chat_id=user_id,
                         text=f"✅ Payment confirmed for *{product['name']}*.\n\nDownload: {link}",
                         parse_mode="Markdown")
        # remove pending
        del PENDING_PAYMENTS[reference]
        return jsonify({"status": "delivered"}), 200

    except Exception as e:
        logger.exception("Exception processing Paystack webhook: %s", e)
        return jsonify({"status": "error", "detail": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
