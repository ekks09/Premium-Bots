# bot.py
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
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Instances
mpesa_handler = MpesaHandler()
product_service = ProductService()

USER_STATES = {}
PENDING_PAYMENTS = {}

# ----------------- Commands -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"🤖 Welcome {user.first_name}!\n\n"
        "I handle:\n• Product browsing\n• M-Pesa payments\n• Instant downloads\n\n"
        "Use /products to get started."
    )

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = product_service.get_products()
    if not products:
        await update.message.reply_text("❌ No products available.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{p['name']} - KSh {p['price']}", callback_data=f"product_{p['id']}")]
        for p in products
    ]
    await update.message.reply_text("🛍 Available Products:\nChoose one:", reply_markup=InlineKeyboardMarkup(keyboard))

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

    await query.edit_message_text(
        f"🛒 {product['name']}\n💵 Price: KSh {product['price']}\n📦 {product['description']}\n\n"
        "Enter your M-Pesa number (format: 2547XXXXXXXX)"
    )

async def handle_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if USER_STATES.get(user_id) != "awaiting_phone":
        return

    phone = update.message.text.strip()
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
        response = mpesa_handler.make_stk_push(phone_number=phone, amount=product["price"], account_reference=f"PD{product_id}")
        if response.get("ResponseCode") == "0":
            checkout_id = response["CheckoutRequestID"]
            PENDING_PAYMENTS[checkout_id] = {"user_id": user_id, "product_id": product_id, "phone": phone}
            context.user_data["pending_payment"] = {"checkout_id": checkout_id, "product_id": product_id}
            await update.message.reply_text(
                "✅ Check your phone and enter your M-Pesa PIN. Download link will follow payment confirmation."
            )
        else:
            await update.message.reply_text("❌ Payment request failed. Try again later.")
    except Exception as e:
        logger.error(f"STK Error: {e}")
        await update.message.reply_text("❌ Payment system unavailable.")
    finally:
        USER_STATES[user_id] = None

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
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

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("products", show_products))
    app.add_handler(CommandHandler("help", help_command))

    # Callback
    app.add_handler(CallbackQueryHandler(handle_product_selection))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_number))

    return app
