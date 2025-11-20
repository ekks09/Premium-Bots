# mpesa_handler.py
import os
import requests
import hashlib
import hmac
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class MpesaHandler:
    """
    Backwards-compatible filename/class name.
    This implements minimal Paystack helpers:
      - initialize_transaction(email, amount_major, reference=None)
      - verify_transaction(reference)
      - verify_webhook_signature(raw_body, signature_header) -> bool
    """

    def __init__(self):
        self.secret = os.getenv("PAYSTACK_SECRET_KEY", "")
        self.callback_url = os.getenv("PAYSTACK_CALLBACK_URL")  # public URL to receive webhooks
        if not self.secret:
            logger.warning("PAYSTACK_SECRET_KEY not set; Paystack API calls will fail.")

        self.base = "https://api.paystack.co"

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.secret}",
            "Content-Type": "application/json"
        }

    def initialize_transaction(self, email: str, amount_major: float, reference: Optional[str] = None):
        """
        Initialize a Paystack transaction. amount_major is in main currency units (e.g., KSh).
        Paystack expects amount in the smallest unit -> multiply by 100.
        Returns Paystack response as dict.
        """
        if not email:
            raise ValueError("Email is required by Paystack.")
        amount_smallest = int(round(float(amount_major) * 100))
        payload = {
            "email": email,
            "amount": amount_smallest,
        }
        if reference:
            payload["reference"] = reference
        if self.callback_url:
            payload["callback_url"] = self.callback_url

        url = f"{self.base}/transaction/initialize"
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def verify_transaction(self, reference: str):
        """
        Verify a transaction by reference using Paystack verify API.
        """
        if not reference:
            raise ValueError("reference required for verify")
        url = f"{self.base}/transaction/verify/{reference}"
        resp = requests.get(url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        return resp.json()

    def verify_webhook_signature(self, raw_body: bytes, signature_header: str) -> bool:
        """
        Paystack sends header 'x-paystack-signature' which is HMAC-SHA512 of the raw body using SECRET_KEY.
        """
        if not self.secret:
            logger.warning("No PAYSTACK_SECRET_KEY available to verify webhook signature.")
            return False
        computed = hmac.new(self.secret.encode(), raw_body, hashlib.sha512).hexdigest()
        # signature_header can be hex string; Paystack uses hex lowercase
        return hmac.compare_digest(computed, signature_header)
