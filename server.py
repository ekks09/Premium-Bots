import os
import logging
import asyncio
from flask import Flask, request, jsonify
from bot import create_application, PENDING_PAYMENTS
from product_service import ProductService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Initialize bot application and product service
application = create_application()
product_service = ProductService()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming Telegram updates via webhook."""
    try:
        # Process the update
        update = Update.de_json(request.get_json(), application.bot)
        application.update_queue.put_nowait(update)
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error processing webhook', 500

@app.route('/mpesa-callback', methods=['POST'])
def mpesa_callback():
    """Handle M-Pesa payment confirmation callbacks."""
    try:
        callback_data = request.get_json()
        logger.info(f"Received M-Pesa callback: {callback_data}")

        # Extract callback information
        stk_callback = callback_data.get('Body', {}).get('stkCallback', {})
        result_code = stk_callback.get('ResultCode')
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])

        if result_code == 0:
            # Payment was successful
            logger.info(f"Payment successful for checkout: {checkout_request_id}")
            
            # Find the pending payment
            payment_info = PENDING_PAYMENTS.get(checkout_request_id)
            if payment_info:
                user_id = payment_info['user_id']
                product_id = payment_info['product_id']
                
                # Get product details
                product = product_service.get_product(product_id)
                if product:
                    download_link = product['pixeldrain_link']
                    
                    # Prepare success message
                    success_message = f"""
✅ Payment Confirmed!

📦 Product: {product['name']}
💵 Amount: KSh {product['price']}
🔗 Download Link: {download_link}

Thank you for your purchase! 
If you have any issues, please contact support.
"""
                    # Send message to user
                    asyncio.run_coroutine_threadsafe(
                        application.bot.send_message(
                            chat_id=user_id,
                            text=success_message
                        ),
                        asyncio.get_event_loop()
                    )
                    
                    logger.info(f"Download link sent to user {user_id} for product {product_id}")
                
                # Clean up pending payment
                del PENDING_PAYMENTS[checkout_request_id]
            else:
                logger.warning(f"No pending payment found for checkout: {checkout_request_id}")
        else:
            # Payment failed
            error_message = stk_callback.get('ResultDesc', 'Payment failed')
            logger.warning(f"Payment failed for {checkout_request_id}: {error_message}")
            
            # Notify user if we have the payment info
            payment_info = PENDING_PAYMENTS.get(checkout_request_id)
            if payment_info:
                user_id = payment_info['user_id']
                asyncio.run_coroutine_threadsafe(
                    application.bot.send_message(
                        chat_id=user_id,
                        text=f"❌ Payment failed: {error_message}\n\nPlease try again with /products"
                    ),
                    asyncio.get_event_loop()
                )
                del PENDING_PAYMENTS[checkout_request_id]

        return jsonify({"ResultCode": 0, "ResultDesc": "Success"})

    except Exception as e:
        logger.error(f"M-Pesa callback processing error: {e}")
        return jsonify({"ResultCode": 1, "ResultDesc": "Failed"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({"status": "healthy", "service": "telegram-mpesa-bot"})

@app.route('/', methods=['GET'])
def home():
    """Home page."""
    return """
    <html>
        <head>
            <title>Telegram M-Pesa Bot</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .container { text-align: center; }
                .status { color: green; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 Telegram M-Pesa Bot</h1>
                <p class="status">✅ Service is running</p>
                <p>This bot handles digital product sales with M-Pesa integration.</p>
                <p><a href="/health">Health Check</a></p>
            </div>
        </body>
    </html>
    """

def setup_webhook():
    """Set up Telegram webhook on application start."""
    webhook_url = os.getenv('WEBHOOK_URL')
    if not webhook_url:
        logger.warning("WEBHOOK_URL not set, webhook won't be configured")
        return

    try:
        webhook_url = f"{webhook_url.rstrip('/')}/webhook"
        application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

# Set up webhook when the app starts
setup_webhook()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
