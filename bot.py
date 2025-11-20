# bot.py (Paystack version)
import os
import logging
import requests
import json
import re
import uuid
from paystack_handler import PaystackHandler
from product_service import ProductService
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PAYSTACK_CALLBACK_URL = os.getenv("PAYSTACK_CALLBACK_URL")  # e.g. https://your-app.onrender.com/paystack-callback
if not BOT_TOKEN:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN env var")
if not PAYSTACK_CALLBACK_URL:
    raise SystemExit("Missing PAYSTACK_CALLBACK_URL env var")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
HEADERS = {"Content-Type": "application/json"}

paystack_handler = PaystackHandler()
product_service = ProductService()

# in-memory states (simple)
USER_STATES: Dict[int, str] = {}
USER_DATA: Dict[int, Dict] = {}
PENDING_PAYMENTS: Dict[str, Dict] = {}   # reference -> { user_id, product_id, email }

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
        "• Product browsing\n• Paystack payments\n• Instant downloads\n\n"
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

        # ask for email (Paystack requires email)
        USER_STATES[user_id] = "awaiting_email"
        USER_DATA.setdefault(user_id, {})["selected_product_id"] = product_id
        text = (
            f"🛒 *{product['name']}*\n"
            f"💵 Price: KSh {product['price']}\n"
            f"📦 {product['description']}\n\n"
            "Enter your email address to proceed with payment:"
        )
        send_request("editMessageText", {
            "chat_id": callback_query["message"]["chat"]["id"],
            "message_id": callback_query["message"]["message_id"],
            "text": text,
            "parse_mode": "Markdown"
        })
        answer_callback_query(callback_id, "Enter your email to continue.")

def is_valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email))

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
            "Steps to buy:\n1. Choose a product\n2. Enter email\n3. Open Paystack payment link\n4. Receive download link"
        ))
        return

    # If user in awaiting_email state
    if USER_STATES.get(user_id) == "awaiting_email":
        email = text
        if not is_valid_email(email):
            send_message(chat_id, "❌ Invalid email. Try again.")
            return
        selected_product_id = USER_DATA.get(user_id, {}).get("selected_product_id")
        if not selected_product_id:
            send_message(chat_id, "❌ Product missing. Start again with /products.")
            USER_STATES[user_id] = None
            return
        product = product_service.get_product(selected_product_id)
        if not product:
            send_message(chat_id, "❌ Product not found. Start again with /products.")
            USER_STATES[user_id] = None
            return

        # create unique transaction reference
        reference = str(uuid.uuid4())
        PENDING_PAYMENTS[reference] = {"user_id": user_id, "product_id": selected_product_id, "email": email}
        USER_DATA[user_id]["pending_payment"] = {"reference": reference, "product_id": selected_product_id}

        # initialize Paystack payment
        payment_data = paystack_handler.initialize_payment(
            email=email,
            amount=product["price"],
            reference=reference,
            callback_url=PAYSTACK_CALLBACK_URL
        )

        if payment_data.get("authorization_url"):
            send_message(chat_id, (
                f"📲 Click the link below to pay for *{product['name']}*:\n\n"
                f"{payment_data['authorization_url']}\n\n"
                "Once payment is confirmed, you will receive your download link automatically."
            ))
        else:
            send_message(chat_id, "❌ Payment initialization failed. Try again later.")

        USER_STATES[user_id] = None
        return

    # otherwise ignore / allow generic reply
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
    # edited_message, channel_post etc can be ignored for now
    logger.debug("Update type not handled: keys=%s", list(update_json.keys()))
