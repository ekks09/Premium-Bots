import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    message = f"""
🤖 Welcome {user.first_name}!

I handle:
• Product browsing  
• M-Pesa payments  
• Instant downloads  

Use /products to get started.
"""

    await update.message.reply_text(message)


# -------------------------------
# COMMAND: /products
# -------------------------------
async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = product_service.get_products()

    if not products:
        await update.message.reply_text("❌ No products available.")
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

    await update.message.reply_text(
        "🛍 Available Products:\nChoose one:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# -------------------------------
# CALLBACK: product chosen
# -------------------------------
async def handle_product_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = query.data.split("_")[1]
    product = product_service.get_product(product_id)

    if not product:
        await query.edit_message_text("❌ Product not found.")
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

    await query.edit_message_text(text)


# -------------------------------
# MESSAGE: phone number handler
# -------------------------------
async def handle_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if USER_STATES.get(user_id) != "awaiting_phone":
        return  # Ignore random messages

    phone = update.message.text.strip()

    # Basic validation
    if not phone.isdigit() or not phone.startswith("254") or len(phone) != 12:
        await update.message.reply_text("❌ Invalid number. Use format: 2547XXXXXXXX")
        return

    product_id = context.user_data.get("selected_product_id")
    product = product_service.get_product(product_id)

    if not product:
        await update.message.reply_text("❌ Product missing. Start again at /products.")
        return

    await update.message.reply_text("📲 Sending M-Pesa STK push...")

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

            await update.message.reply_text(
                "✅ Check your phone and enter your M-Pesa PIN to complete payment.\n"
                "I'll send your download link automatically once payment is confirmed."
            )
        else:
            await update.message.reply_text(
                "❌ Payment request failed. Try again later."
            )

    except Exception as e:
        logger.error(f"STK Error: {e}")
        await update.message.reply_text("❌ Payment system unavailable.")

    finally:
        USER_STATES[user_id] = None  # Reset state


# -------------------------------
# COMMAND: /help
# -------------------------------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await update.message.reply_text(text)


# -------------------------------
# Application entry
# -------------------------------
def create_application():
    """Create the Telegram application without requiring any arguments."""
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("products", show_products))
    app.add_handler(CommandHandler("help", help_command))

    # Callback
    app.add_handler(CallbackQueryHandler(handle_product_selection))

    # Phone numbers and messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_number))

    return app
