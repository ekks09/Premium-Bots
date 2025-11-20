# bot.py
import os
import uuid
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from paystack_handler import PaystackHandler, PRODUCTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

paystack = PaystackHandler()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CALLBACK_URL = os.getenv("PAYSTACK_CALLBACK_URL")

# Store payments until Paystack confirms
PENDING_PAYMENTS = {}

bot = Bot(token=TELEGRAM_BOT_TOKEN)

def start(update: Update, context: CallbackContext):
    keyboard = []
    for product_id, product in PRODUCTS.items():
        keyboard.append([InlineKeyboardButton(f"Buy {product['name']}", callback_data=product_id)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Choose a product to buy:", reply_markup=reply_markup)

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    product_id = query.data
    product = PRODUCTS.get(product_id)
    if not product:
        query.edit_message_text("Product not found!")
        return

    reference = str(uuid.uuid4())
    email = "customer@email.com"  # later you can ask for real email

    payment_data = paystack.initialize_payment(email, product_id, reference, CALLBACK_URL)
    if payment_data:
        PENDING_PAYMENTS[reference] = {
            "user_id": query.from_user.id,
            "product_id": product_id
        }
        query.edit_message_text(
            f"Click to pay:\n{payment_data['authorization_url']}"
        )
    else:
        query.edit_message_text("Payment failed to initialize. Try again later.")

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
