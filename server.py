# server.py
import os
import logging
import json
from flask import Flask, request, jsonify
from bot import create_application, PENDING_PAYMENTS
from product_service import ProductService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Create the Telegram application using your existing function
application = create_application()
product_service = ProductService()

# Webhook route for Telegram
@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming Telegram updates via webhook"""
    try:
        json_update = request.get_json(force=True)
        update = type('Update', (object,), json_update)  # Simple object creation
        application.update_queue.put_nowait(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500

# M-Pesa callback route
@app.route("/mpesa-callback", methods=["POST"])
def mpesa_callback():
    """Handle M-Pesa payment confirmation"""
    try:
        data = request.get_json()
        logger.info(f"M-Pesa callback received: {data}")
        
        # Process the callback
        callback_data = data.get('Body', {}).get('stkCallback', {})
        result_code = callback_data.get('ResultCode')
        checkout_request_id = callback_data.get('CheckoutRequestID')
        callback_metadata = callback_data.get('CallbackMetadata', {})
        
        if result_code == 0:
            # Payment successful
            logger.info(f"Payment successful for checkout: {checkout_request_id}")
            
            # Find the payment in pending payments
            payment_info = PENDING_PAYMENTS.get(checkout_request_id)
            if payment_info:
                user_id = payment_info["user_id"]
                product_id = payment_info["product_id"]
                
                # Get product and send download link
                product = product_service.get_product(product_id)
                if product:
                    download_link = product['pixeldrain_link']
                    message = f"""
✅ Payment confirmed!

📦 Product: {product['name']}
🔗 Download Link: {download_link}

Thank you for your purchase!
"""
                    # Send message to user (you'll need to implement this properly)
                    # For now, we'll just log it
                    logger.info(f"Should send to user {user_id}: {message}")
                
                # Remove from pending payments
                del PENDING_PAYMENTS[checkout_request_id]
            else:
                logger.warning(f"Payment info not found for checkout: {checkout_request_id}")
        else:
            # Payment failed
            error_message = callback_data.get('ResultDesc', 'Unknown error')
            logger.warning(f"Payment failed for checkout: {checkout_request_id}, error: {error_message}")
        
        return jsonify({"ResultCode": 0, "ResultDesc": "Success"})
        
    except Exception as e:
        logger.error(f"Callback error: {e}")
        return jsonify({"ResultCode": 1, "ResultDesc": "Failed"}), 500

@app.route("/", methods=["GET"])
def index():
    return "Bot is running."

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

# Set webhook on startup
def set_webhook():
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set")
        return
    
    url = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    try:
        # Use the bot instance from your application
        result = application.bot.set_webhook(url)
        logger.info(f"Webhook set successfully: {url}")
        return result
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

# Set webhook when the app starts
set_webhook()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
