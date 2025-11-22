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

# Init handlers
paystack = PaystackHandler()
product_service = ProductService()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CALLBACK_URL = os.getenv("PAYSTACK_CALLBACK_URL")

# Store payments until Paystack confirms
PENDING_PAYMENTS = {}

bot = Bot(token=TELEGRAM_BOT_TOKEN)

def start(update: Update, context: CallbackContext):
    products = product_service.get_products()
    keyboard = []

    for product in products:
        keyboard.append([
            InlineKeyboardButton(
                f"Buy {product['name']} ({product['price']} KES)",
                callback_data=product['id']
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Choose a product to buy:", reply_markup=reply_markup)


def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    product_id = query.data

    product = product_service.get_product(product_id)
    if not product:
        query.edit_message_text("Product not found!")
        return

    reference = str(uuid.uuid4())
    email = "customer@email.com"  # later ask real email

    payment = paystack.initialize_payment(email, product_id, reference, CALLBACK_URL)

    if payment and "authorization_url" in payment:
        PENDING_PAYMENTS[reference] = {
            "user_id": query.from_user.id,
            "product_id": product_id
        }
        query.edit_message_text(
            f"Click to pay securely:\n\n🔗 {payment['authorization_url']}"
        )
    else:
        logger.error("Failed Paystack init response: %s", payment)
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
