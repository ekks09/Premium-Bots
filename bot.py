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

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global instances
mpesa_handler = MpesaHandler()
product_service = ProductService()

# User state management
USER_STATES = {}
PENDING_PAYMENTS = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message when the command /start is issued."""
    user = update.effective_user
    welcome_text = f"""
🤖 Welcome {user.first_name}!

I handle:
• Product browsing
• M-Pesa payments  
• Instant downloads

Use /products to see what's available.
"""
    await update.message.reply_text(welcome_text)

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available products with inline buttons."""
    products = product_service.get_products()
    
    if not products:
        await update.message.reply_text("❌ No products available at the moment.")
        return

    keyboard = []
    for product in products:
        keyboard.append([
            InlineKeyboardButton(
                f"{product['name']} - KSh {product['price']}",
                callback_data=f"product_{product['id']}"
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🛍️ Available Products:\nChoose one to purchase:",
        reply_markup=reply_markup
    )

async def handle_product_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle product selection from inline keyboard."""
    query = update.callback_query
    await query.answer()
    
    product_id = query.data.split("_")[1]
    product = product_service.get_product(product_id)
    
    if not product:
        await query.edit_message_text("❌ Product not found.")
        return

    # Store user state
    USER_STATES[query.from_user.id] = "awaiting_phone"
    context.user_data["selected_product"] = product

    product_info = f"""
🛒 {product['name']}
💵 Price: KSh {product['price']}
📦 {product['description']}

Please enter your M-Pesa phone number in the format:
2547XXXXXXXX
"""
    await query.edit_message_text(product_info)

async def handle_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process phone number and initiate M-Pesa payment."""
    user_id = update.effective_user.id
    
    # Check if user is in the correct state
    if USER_STATES.get(user_id) != "awaiting_phone":
        return

    phone_number = update.message.text.strip()
    
    # Validate phone number
    if not (phone_number.isdigit() and phone_number.startswith("254") and len(phone_number) == 12):
        await update.message.reply_text("❌ Invalid phone number. Please use format: 2547XXXXXXXX")
        return

    product = context.user_data.get("selected_product")
    if not product:
        await update.message.reply_text("❌ Product selection expired. Please start over with /products")
        USER_STATES[user_id] = None
        return

    await update.message.reply_text("📲 Initiating M-Pesa payment...")

    try:
        # Trigger STK push
        response = mpesa_handler.make_stk_push(
            phone_number=phone_number,
            amount=product["price"],
            account_reference=f"PROD{product['id']}"
        )

        if response.get("ResponseCode") == "0":
            checkout_request_id = response["CheckoutRequestID"]
            
            # Store payment information
            PENDING_PAYMENTS[checkout_request_id] = {
                "user_id": user_id,
                "product_id": product["id"],
                "phone_number": phone_number,
                "amount": product["price"]
            }
            
            await update.message.reply_text(
                "✅ M-Pesa prompt sent to your phone!\n\n"
                "Please enter your M-Pesa PIN to complete the payment.\n"
                "You'll receive your download link automatically once payment is confirmed."
            )
        else:
            error_message = response.get("ResponseDescription", "Unknown error")
            await update.message.reply_text(f"❌ Payment request failed: {error_message}")

    except Exception as e:
        logger.error(f"STK Push error: {e}")
        await update.message.reply_text("❌ Payment service temporarily unavailable. Please try again later.")
    
    finally:
        # Reset user state
        USER_STATES[user_id] = None

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message."""
    help_text = """
🆘 Bot Help Guide

Available Commands:
/start - Start the bot
/products - Browse available products
/help - Show this help message

Purchase Process:
1. Use /products to see available items
2. Select a product
3. Enter your M-Pesa number (2547XXXXXXXX)
4. Approve the STK push on your phone
5. Receive download link automatically

Need assistance? Contact support.
"""
    await update.message.reply_text(help_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages."""
    user_id = update.effective_user.id
    
    if USER_STATES.get(user_id) == "awaiting_phone":
        await handle_phone_number(update, context)
    else:
        await update.message.reply_text(
            "I'm here to help you purchase digital products!\n\n"
            "Use /products to see what's available or /help for assistance."
        )

def create_application() -> Application:
    """Create and configure the Telegram Application."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

    # Create Application
    application = Application.builder().token(bot_token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("products", show_products))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(handle_product_selection))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return application

# For local polling development
if __name__ == "__main__":
    app = create_application()
    print("Bot is running in polling mode...")
    app.run_polling()
