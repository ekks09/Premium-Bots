import os
import logging
import asyncio
from flask import Flask, request, jsonify
from telegram import Update
from bot import create_application, get_pending_payments

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize bot application
try:
    application = create_application()
    pending_payments = get_pending_payments()
    logger.info("Bot application initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize bot: {e}")
    application = None
    pending_payments = {}

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming Telegram updates."""
    if not application:
        logger.error("Bot application not initialized")
        return "Bot not initialized", 500
        
    try:
        update_data = request.get_json()
        logger.info(f"Received webhook update from user: {update_data}")
        
        # Process the update
        update = Update.de_json(update_data, application.bot)
        application.update_queue.put_nowait(update)
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

@app.route('/mpesa-callback', methods=['POST'])
def mpesa_callback():
    """Handle M-Pesa payment callbacks."""
    try:
        data = request.get_json()
        logger.info(f"M-Pesa callback received: {data}")

        stk_callback = data.get('Body', {}).get('stkCallback', {})
        result_code = stk_callback.get('ResultCode')
        checkout_request_id = stk_callback.get('CheckoutRequestID')

        if result_code == 0 and application:
            # Payment successful
            payment_info = pending_payments.get(checkout_request_id)
            if payment_info:
                user_id = payment_info['user_id']
                product = payment_info['product']
                
                message = (
                    f"✅ Payment Confirmed!\n\n"
                    f"📦 Product: {product['name']}\n"
                    f"💵 Amount: KSh {product['price']}\n"
                    f"🔗 Download Link: {product['download_link']}\n\n"
                    "Thank you for your purchase! 🎉"
                )
                
                # Send download link to user
                asyncio.run_coroutine_threadsafe(
                    application.bot.send_message(chat_id=user_id, text=message),
                    asyncio.get_event_loop()
                )
                
                logger.info(f"Download link sent to user {user_id} for product {product['name']}")
                del pending_payments[checkout_request_id]
            else:
                logger.warning(f"No pending payment found for checkout: {checkout_request_id}")
        else:
            # Payment failed
            error_message = stk_callback.get('ResultDesc', 'Payment failed')
            logger.warning(f"Payment failed for checkout: {checkout_request_id}, error: {error_message}")
            
            # Notify user if we have the payment info
            payment_info = pending_payments.get(checkout_request_id)
            if payment_info and application:
                user_id = payment_info['user_id']
                asyncio.run_coroutine_threadsafe(
                    application.bot.send_message(
                        chat_id=user_id,
                        text=f"❌ Payment failed: {error_message}\n\nPlease try again with /products"
                    ),
                    asyncio.get_event_loop()
                )
                del pending_payments[checkout_request_id]
        
        return jsonify({"ResultCode": 0, "ResultDesc": "Success"})

    except Exception as e:
        logger.error(f"Callback error: {e}")
        return jsonify({"ResultCode": 1, "ResultDesc": "Failed"}), 500

@app.route('/')
def home():
    webhook_status = "Unknown"
    if application:
        try:
            webhook_info = application.bot.get_webhook_info()
            webhook_status = webhook_info.url if webhook_info.url else "Not set"
        except Exception as e:
            webhook_status = f"Error: {e}"
    
    return f"""
    <html>
        <head>
            <title>Telegram M-Pesa Bot</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .container {{ text-align: center; }}
                .status {{ color: green; font-weight: bold; }}
                .info {{ background: #f0f0f0; padding: 10px; border-radius: 5px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 Telegram M-Pesa Bot</h1>
                <p class="status">✅ Service is running with full functionality</p>
                <div class="info">
                    <p><strong>Webhook Status:</strong> {webhook_status}</p>
                    <p><strong>Bot Features:</strong> Product sales, M-Pesa payments, PixelDrain downloads</p>
                </div>
                <p>This bot handles digital product sales with M-Pesa integration.</p>
                <p><a href="/health">Health Check</a> | <a href="/set-webhook">Set Webhook</a></p>
            </div>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy", 
        "service": "telegram-mpesa-bot",
        "bot_initialized": application is not None,
        "features": ["product_catalog", "mpesa_payments", "download_links"]
    })

@app.route('/set-webhook', methods=['GET'])
def set_webhook_manual():
    """Manual webhook setup endpoint."""
    if not application:
        return "Bot not initialized", 500
        
    try:
        webhook_url = os.getenv('WEBHOOK_URL')
        if not webhook_url:
            return "WEBHOOK_URL environment variable not set", 400
            
        full_webhook_url = f"{webhook_url.rstrip('/')}/webhook"
        result = application.bot.set_webhook(full_webhook_url)
        
        logger.info(f"Webhook set manually to: {full_webhook_url}")
        return f"✅ Webhook set successfully to: {full_webhook_url}", 200
        
    except Exception as e:
        logger.error(f"Manual webhook setup failed: {e}")
        return f"❌ Failed to set webhook: {e}", 500

def setup_webhook():
    """Set up Telegram webhook on application start."""
    if not application:
        logger.error("Cannot set webhook: application not initialized")
        return
        
    webhook_url = os.getenv('WEBHOOK_URL')
    if not webhook_url:
        logger.warning("WEBHOOK_URL not set, webhook won't be configured")
        return

    try:
        full_webhook_url = f"{webhook_url.rstrip('/')}/webhook"
        result = application.bot.set_webhook(full_webhook_url)
        logger.info(f"Webhook set to: {full_webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

# Set webhook when the app starts
setup_webhook()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
