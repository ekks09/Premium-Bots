# bot.py
import os
import logging
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mpesa_handler = MpesaHandler()
product_service = ProductService()
USER_STATES = {}
PENDING_PAYMENTS = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = f"🤖 Welcome {user.first_name}!\n\nUse /products to browse products."
    await update.message.reply_text(message)

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = product_service.get_products()
    if not products:
        await update.message.reply_text("❌ No products available.")
        return

    keyboard = [[InlineKeyboardButton(f"{p['name']} - KSh {p['price']}", callback_data=f"product_{p['id']}")] for p in products]
    await update.message.reply_text("🛍 Choose a product:", reply_markup=InlineKeyboardMarkup(keyboard))

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

    text = f"🛒 {product['name']}\n💵 Price: KSh {product['price']}\n📦 {product['description']}\n\nEnter your M-Pesa number (2547XXXXXXXX):"
    await query.edit_message_text(text)

async def handle_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if USER_STATES.get(user_id) != "awaiting_phone":
        return

    phone = update.message.text.strip()
    if not phone.isdigit() or not phone.startswith("254") or len(phone) != 12:
        await update.message.reply_text("❌ Invalid number. Format: 2547XXXXXXXX")
        return

    product_id = context.user_data.get("selected_product_id")
    product = product_service.get_product(product_id)
    if not product:
        await update.message.reply_text("❌ Product missing. Start again at /products.")
        return

    await update.message.reply_text("📲 Sending M-Pesa STK push...")
    try:
        response = mpesa_handler.make_stk_push(phone, product["price"], f"PD{product_id}")
        if response.get("ResponseCode") == "0":
            checkout_id = response["CheckoutRequestID"]
            PENDING_PAYMENTS[checkout_id] = {"user_id": user_id, "product_id": product_id, "phone": phone}
            context.user_data["pending_payment"] = {"checkout_id": checkout_id, "product_id": product_id}
            await update.message.reply_text("✅ STK sent! Enter your PIN to complete payment.")
        else:
            await update.message.reply_text("❌ Payment request failed.")
    except Exception as e:
        logger.error(f"STK Error: {e}")
        await update.message.reply_text("❌ Payment system unavailable.")
    finally:
        USER_STATES[user_id] = None

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🆘 Commands:\n/start\n/products\n/help\n\nSteps: choose product -> send phone -> approve STK -> get download link"
    await update.message.reply_text(text)

def create_application():
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("products", show_products))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_product_selection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_number))
    return app
