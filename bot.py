# bot.py
import os
import uuid
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from paystack_handler import PaystackHandler
from product_service import ProductService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

paystack = PaystackHandler()
product_service = ProductService()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CALLBACK_URL = os.getenv("PAYSTACK_CALLBACK_URL")  # must be set

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN env var")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
PENDING_PAYMENTS = {}  # reference -> {user_id, product_id}

def start(update: Update, context: CallbackContext):
    products = product_service.get_products()
    keyboard = []
    for p in products:
        keyboard.append([InlineKeyboardButton(f"{p['name']} — KES {p['price']}", callback_data=p['id'])])
    update.message.reply_text("Available products:", reply_markup=InlineKeyboardMarkup(keyboard))

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    product_id = query.data
    product = product_service.get_product(product_id)
    if not product:
        query.edit_message_text("Product not found.")
        return

    reference = str(uuid.uuid4())
    # For now using placeholder email; you can ask user for email later.
    email = (query.from_user.username or f"user{query.from_user.id}") + "@example.com"

    # initialize payment with structured response
    result = paystack.initialize_payment(email=email, product_id=product_id, reference=reference, callback_url=CALLBACK_URL)

    if not result.get("ok"):
        # detailed error — send to user and log
        err = result.get("error")
        detail = result.get("detail")
        logger.error("Paystack init error for user %s product %s: %s %s", query.from_user.id, product_id, err, detail)
        # Surface a short friendly message plus the error code so you can debug.
        query.edit_message_text(
            f"❌ Failed to create payment.\nReason: {err}\nDetails: {str(detail)}"
        )
        return

    data = result.get("data", {})
    auth_url = data.get("authorization_url")
    ref = data.get("reference", reference)

    # store pending
    PENDING_PAYMENTS[ref] = {"user_id": query.from_user.id, "product_id": product_id}

    # Send the link clearly
    query.edit_message_text(
        f"🔗 Open this link to pay for *{product['name']}* (KES {product['price']}):\n\n{auth_url}",
        parse_mode="Markdown"
    )

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
