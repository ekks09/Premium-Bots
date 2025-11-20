# bot.py
import os
import logging
import requests
import json
import re
import time
from product_service import ProductService
from mpesa_handler import MpesaHandler  # now acts as Paystack handler (keeps filename same)
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN env var")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
HEADERS = {"Content-Type": "application/json"}

# keep names for compatibility with server.py imports
paystack_handler = MpesaHandler()
product_service = ProductService()

# in-memory states (simple)
USER_STATES: Dict[int, str] = {}
USER_DATA: Dict[int, Dict] = {}
PENDING_PAYMENTS: Dict[str, Dict] = {}   # reference -> { user_id, product_id, amount }

def send_request(method: str, payload: dict):
    url = f"{TELEGRAM_API}/{method}"
    r = requests.post(url, json=payload, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

def send_message(chat_id: int, text: str, reply_markup: dict = None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return send_request("sendMessage", payload)

def answer_callback_query(callback_query_id: str, text: str = None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return send_request("answerCallbackQuery", payload)

def build_products_keyboard():
    products = product_service.get_products()
    keyboard = []
    for p in products:
        keyboard.append([{"text": f"{p['name']} - KSh {p['price']}", "callback_data": f"product_{p['id']}"}])
    return {"inline_keyboard": keyboard}

def handle_start(chat_id: int, first_name: str = ""):
    text = (
        f"🤖 Welcome {first_name or ''}!\n\n"
        "I handle:\n"
        "• Product browsing\n• Paystack payments\n"
        "• Instant downloads\n\n"
        "Use /products to get started."
    )
    send_message(chat_id, text)

def handle_products_cmd(chat_id: int):
    products = product_service.get_products()
    if not products:
        send_message(chat_id, "❌ No products available.")
        return
    send_message(chat_id, "🛍 Available Products:\nChoose one:", reply_markup=build_products_keyboard())

def handle_callback(callback_query: dict):
    data = callback_query.get("data", "")
    from_user = callback_query.get("from", {})
    callback_id = callback_query.get("id")
    user_id = from_user.get("id")
    if not user_id:
        return

    # When user taps a product button
    if data.startswith("product_"):
        product_id = data.split("_", 1)[1]
        product = product_service.get_product(product_id)
        if not product:
            send_request("editMessageText", {
                "chat_id": callback_query["message"]["chat"]["id"],
                "message_id": callback_query["message"]["message_id"],
                "text": "❌ Product not found."
            })
            answer_callback_query(callback_id, "Product not found.")
            return

        # Create a unique reference
        reference = f"tg{user_id}-{product_id}-{int(time.time())}"

        # Use a placeholder email because Paystack needs an email. In production collect real user email.
        email = (from_user.get("username") or f"user{user_id}") + "@example.com"

        try:
            init = paystack_handler.initialize_transaction(email=email, amount_major=product["price"], reference=reference)
        except Exception as e:
            logger.exception("Paystack init failed: %s", e)
            answer_callback_query(callback_id, "Failed to create payment. Try again later.")
            return

        if not init.get("status"):
            # API returned non-success
            logger.warning("Paystack initialize returned non-success: %s", init)
            answer_callback_query(callback_id, "Payment initialization failed.")
            return

        data = init.get("data", {})
        auth_url = data.get("authorization_url")
        ref = data.get("reference", reference)

        # store in pending payments by reference
        PENDING_PAYMENTS[ref] = {"user_id": user_id, "product_id": product_id, "amount": product["price"]}

        # Edit message to show payment link + verify button
        keyboard = [
            [{"text": "Open payment page", "url": auth_url}],
            [{"text": "I paid — verify", "callback_data": f"verify|{ref}"}]
        ]
        send_request("editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": (
                f"🛒 *{product['name']}*\n"
                f"💵 Price: KSh {product['price']}\n\n"
                "Tap the button to open Paystack and complete payment."
            ),
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": keyboard}
        })
        answer_callback_query(callback_id, "Payment link created. Open it to pay.")
        return

    # manual verification button
    if data.startswith("verify|"):
        _, ref = data.split("|", 1)
        callback_chat = callback_query["message"]["chat"]["id"]
        send_request("editMessageText", {
            "chat_id": callback_chat,
            "message_id": callback_query["message"]["message_id"],
            "text": "Verifying payment... (this may take a few seconds)"
        })
        try:
            result = paystack_handler.verify_transaction(reference=ref)
        except Exception as e:
            logger.exception("Verify API failed: %s", e)
            send_message(callback_chat, "Verification failed: API error.")
            return

        if not result.get("status"):
            send_message(callback_chat, f"Verification API returned failure: {result}")
            return

        status = result.get("data", {}).get("status")
        if status == "success":
            # deliver product
            pending = PENDING_PAYMENTS.get(ref)
            if pending:
                user = pending["user_id"]
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
                    send_message(user, message)
                del PENDING_PAYMENTS[ref]
            send_message(callback_chat, "Payment verified and product delivered.")
        else:
            send_message(callback_chat, f"Payment not successful. Status: {status}")

def handle_text_message(message: dict):
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "").strip()
    from_user = message.get("from", {})
    user_id = from_user.get("id")
    first_name = from_user.get("first_name", "")

    # commands
    if text.startswith("/start"):
        handle_start(chat_id, first_name)
        return
    if text.startswith("/products"):
        handle_products_cmd(chat_id)
        return
    if text.startswith("/help"):
        send_message(chat_id, (
            "🆘 *Help Menu*\n\n"
            "/start - Restart bot\n"
            "/products - Show product list\n"
            "/help - Show help\n\n"
            "Steps to buy:\n1. Choose a product\n2. Click the payment link and pay on Paystack\n3. You'll get the download link automatically when payment succeeds."
        ))
        return

    # otherwise
    send_message(chat_id, "I didn't understand that. Use /products to browse items or /help for commands.")

def handle_update(update_json: dict):
    """Central entry-point for incoming Telegram updates (webhook)."""
    logger.debug("handle_update called with: %s", update_json)
    # callback_query
    if "callback_query" in update_json:
        handle_callback(update_json["callback_query"])
        return
    # message
    if "message" in update_json:
        handle_text_message(update_json["message"])
        return
    logger.debug("Update type not handled: keys=%s", list(update_json.keys()))

# helper to let server set webhook
def set_webhook(url: str):
    resp = requests.post(f"{TELEGRAM_API}/setWebhook", json={"url": url}, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    logger.info("setWebhook response: %s", resp.text)
    return resp.json()
