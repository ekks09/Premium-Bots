# paystack_handler.py
import os
import requests
import logging
from typing import Dict

logger = logging.getLogger(__name__)

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

    def initialize_payment(self, email: str, amount: int, reference: str, callback_url: str) -> Dict:
        """
        Create a transaction (initialize payment) on Paystack
        :param email: Customer email (Paystack requires an email)
        :param amount: Amount in Naira/KES (Paystack expects smallest currency unit, e.g., KSh 250 → 25000 if decimal=2)
        :param reference: Unique reference for transaction
        :param callback_url: URL for Paystack to call when payment is completed
        """
        payload = {
            "email": email,
            "amount": amount * 100,  # Paystack uses kobo (or cents), multiply by 100
            "reference": reference,
            "callback_url": callback_url
        }
        try:
            resp = requests.post(f"{self.base_url}/transaction/initialize", json=payload, headers=self.headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status"):
                logger.info("Payment initialized: %s", data)
                return data["data"]  # contains authorization_url, reference, etc.
            else:
                logger.warning("Failed to initialize payment: %s", data)
                return {}
        except Exception as e:
            logger.exception("Error initializing Paystack payment: %s", e)
            return {}

    def verify_payment(self, reference: str) -> Dict:
        """
        Verify transaction status
        :param reference: Transaction reference
        """
        try:
            resp = requests.get(f"{self.base_url}/transaction/verify/{reference}", headers=self.headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status"):
                logger.info("Payment verified: %s", data)
                return data["data"]
            else:
                logger.warning("Failed to verify payment: %s", data)
                return {}
        except Exception as e:
            logger.exception("Error verifying Paystack payment: %s", e)
            return {}
