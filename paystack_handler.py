# paystack_handler.py
import os
import requests
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Map product IDs to download links
PRODUCT_LINKS = {
    "product_1": "https://pixeldrain.com/u/aakwH36V",
    "product_2": "https://pixeldrain.com/u/anotherLinkHere",
    # Add more products here
}

class PaystackHandler:
    def __init__(self):
        self.secret_key = os.getenv("PAYSTACK_SECRET_KEY")
        if not self.secret_key:
            raise RuntimeError("PAYSTACK_SECRET_KEY environment variable not set")
        self.base_url = "https://api.paystack.co"
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    def initialize_payment(self, email: str, amount: int, reference: str, callback_url: str, product_id: str) -> Dict:
        """
        Initialize a Paystack payment for a specific product
        """
        payload = {
            "email": email,
            "amount": amount * 100,
            "reference": reference,
            "callback_url": callback_url,
            "metadata": {
                "product_id": product_id
            }
        }
        try:
            resp = requests.post(f"{self.base_url}/transaction/initialize", json=payload, headers=self.headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status"):
                logger.info("Payment initialized: %s", data)
                return data["data"]
            else:
                logger.warning("Failed to initialize payment: %s", data)
                return {}
        except Exception as e:
            logger.exception("Error initializing Paystack payment: %s", e)
            return {}

    def verify_payment(self, reference: str) -> Dict:
        """
        Verify transaction status and return the appropriate download link
        """
        try:
            resp = requests.get(f"{self.base_url}/transaction/verify/{reference}", headers=self.headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") and data["data"]["status"] == "success":
                logger.info("Payment verified successfully: %s", data)
                product_id = data["data"]["metadata"].get("product_id")
                download_link = PRODUCT_LINKS.get(product_id)
                return {
                    "status": "success",
                    "message": "Payment confirmed! Here’s your download link.",
                    "download_link": download_link
                }
            else:
                logger.warning("Payment not successful or failed verification: %s", data)
                return {
                    "status": "failed",
                    "message": "Payment verification failed or not completed."
                }
        except Exception as e:
            logger.exception("Error verifying Paystack payment: %s", e)
            return {
                "status": "error",
                "message": str(e)
            }
