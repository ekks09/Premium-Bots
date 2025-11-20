import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext
)
from mpesa_handler import MpesaHandler
from product_service import ProductService

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Instances
mpesa_handler = MpesaHandler()
product_service = ProductService()

USER_STATES = {}
PENDING_PAYMENTS = {}

# ----------------- Commands -----------------
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    update.message.reply_text(
        f"🤖 Welcome {user.first_name}!\n\n"
        "I handle:\n• Product browsing\n• M-Pesa payments\n• Instant downloads\n\n"
        "Use /products to get started."
    )

def show_products(update: Update, context: CallbackContext):
    products = product_service.get_products()
    if not products:
        update.message.reply_text("❌ No products available.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{p['name']} - KSh {p['price']}", callback_data=f"product_{p['id']}")]
        for p in products
    ]
    update.message.reply_text("🛍 Available Products:\nChoose one:", reply_markup=InlineKeyboardMarkup(keyboard))

def handle_product_selection(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    product_id = query.data.split("_")[1]
    product = product_service.get_product(product_id)

    if not product:
        query.edit_message_text("❌ Product not found.")
        return

    USER_STATES[query.from_user.id] = "awaiting_phone"
    context.user_data["selected_product_id"] = product_id

    query.edit_message_text(
        f"🛒 {product['name']}\n💵 Price: KSh {product['price']}\n📦 {product['description']}\n\n"
        "Enter your M-Pesa number (format: 2547XXXXXXXX)"
    )

def handle_phone_number(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if USER_STATES.get(user_id) != "awaiting_phone":
        return

    phone = update.message.text.strip()
    if not phone.isdigit() or not phone.startswith("254") or len(phone) != 12:
        update.message.reply_text("❌ Invalid number. Use format: 2547XXXXXXXX")
        return

    product_id = context.user_data.get("selected_product_id")
    product = product_service.get_product(product_id)
    if not product:
        update.message.reply_text("❌ Product missing. Start again at /products.")
        return

    update.message.reply_text("📲 Sending M-Pesa STK push...")

    try:
        response = mpesa_handler.make_stk_push(phone_number=phone, amount=product["price"], account_reference=f"PD{product_id}")
        if response.get("ResponseCode") == "0":
            checkout_id = response["CheckoutRequestID"]
            PENDING_PAYMENTS[checkout_id] = {"user_id": user_id, "product_id": product_id, "phone": phone}
            context.user_data["pending_payment"] = {"checkout_id": checkout_id, "product_id": product_id}
            update.message.reply_text(
                "✅ Check your phone and enter your M-Pesa PIN. Download link will follow payment confirmation."
            )
        else:
            update.message.reply_text("❌ Payment request failed. Try again later.")
    except Exception as e:
        logger.error(f"STK Error: {e}")
        update.message.reply_text("❌ Payment system unavailable.")
    finally:
        USER_STATES[user_id] = None

def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🆘 Help Menu\n\n"
        "/start - Restart bot\n"
        "/products - Show products\n"
        "/help - Show help\n\n"
        "Steps to buy:\n1. Choose product\n2. Send phone\n3. Approve STK push\n4. Receive download link"
    )

# ----------------- Application -----------------
def create_application():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")

    # Use Updater for PTB v13.x
    updater = Updater(token, use_context=True)
    dispatcher = updater.dispatcher

    # Commands
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("products", show_products))
    dispatcher.add_handler(CommandHandler("help", help_command))

    # Callback
    dispatcher.add_handler(CallbackQueryHandler(handle_product_selection))

    # Messages
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_phone_number))

    return updater
