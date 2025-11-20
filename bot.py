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
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global instances
mpesa_handler = MpesaHandler()
product_service = ProductService()

# Temporary user states
USER_STATES = {}

# Store pending payments
PENDING_PAYMENTS = {}


# -------------------------------
# COMMAND: /start
# -------------------------------
def start(update: Update, context: CallbackContext):
    user = update.effective_user

    message = f"""
🤖 Welcome {user.first_name}!

I handle:
• Product browsing  
• M-Pesa payments  
• Instant downloads  

Use /products to get started.
"""

    update.message.reply_text(message)


# -------------------------------
# COMMAND: /products
# -------------------------------
def show_products(update: Update, context: CallbackContext):
    products = product_service.get_products()

    if not products:
        update.message.reply_text("❌ No products available.")
        return

    keyboard = [
        [
            InlineKeyboardButton(
                f"{p['name']} - KSh {p['price']}",
                callback_data=f"product_{p['id']}"
            )
        ]
        for p in products
    ]

    update.message.reply_text(
        "🛍 Available Products:\nChoose one:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# -------------------------------
# CALLBACK: product chosen
# -------------------------------
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

    text = f"""
🛒 {product['name']}
💵 Price: KSh {product['price']}
📦 {product['description']}

Enter your M-Pesa number in the format:
2547XXXXXXXX
"""

    query.edit_message_text(text)


# -------------------------------
# MESSAGE: phone number handler
# -------------------------------
def handle_phone_number(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if USER_STATES.get(user_id) != "awaiting_phone":
        return  # Ignore random messages

    phone = update.message.text.strip()

    # Basic validation
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
        response = mpesa_handler.make_stk_push(
            phone_number=phone,
            amount=product["price"],
            account_reference=f"PD{product_id}"
        )

        # ResponseCode 0 = STK push sent successfully
        if response.get("ResponseCode") == "0":
            checkout_id = response["CheckoutRequestID"]

            # Store payment info
            PENDING_PAYMENTS[checkout_id] = {
                "user_id": update.effective_user.id,
                "product_id": product_id,
                "phone": phone,
            }

            context.user_data["pending_payment"] = {
                "checkout_id": checkout_id,
                "product_id": product_id,
            }

            update.message.reply_text(
                "✅ Check your phone and enter your M-Pesa PIN to complete payment.\n"
                "I'll send your download link automatically once payment is confirmed."
            )
        else:
            update.message.reply_text(
                "❌ Payment request failed. Try again later."
            )

    except Exception as e:
        logger.error(f"STK Error: {e}")
        update.message.reply_text("❌ Payment system unavailable.")

    finally:
        USER_STATES[user_id] = None  # Reset state


# -------------------------------
# COMMAND: /help
# -------------------------------
def help_command(update: Update, context: CallbackContext):
    text = """
🆘 Help Menu

Commands:
/start - Restart bot
/products - Show product list
/help - Show help

Steps to buy:
1. Choose a product
2. Send phone number
3. Approve STK push
4. Receive download link
"""
    update.message.reply_text(text)


# -------------------------------
# Application entry
# -------------------------------
def create_application():
    """Create the Telegram application without requiring any arguments."""
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
    
    # Use Updater for v13.x compatibility
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Commands
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("products", show_products))
    dispatcher.add_handler(CommandHandler("help", help_command))

    # Callback
    dispatcher.add_handler(CallbackQueryHandler(handle_product_selection))

    # Phone numbers and messages
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_phone_number))

    return updater
