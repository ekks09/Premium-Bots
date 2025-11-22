# paystack_handler.py
import os
import requests
import logging
from typing import Dict, Any
from product_service import ProductService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class PaystackHandler:
    def __init__(self):
        self.secret_key = os.getenv("PAYSTACK_SECRET_KEY")
        if not self.secret_key:
            # Don't raise here; let callers handle and show message
            logger.error("PAYSTACK_SECRET_KEY not set in environment")
        self.base_url = "https://api.paystack.co"
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}" if self.secret_key else "",
            "Content-Type": "application/json"
        }
        self.products = ProductService()

    def initialize_payment(self, email: str, product_id: str, reference: str, callback_url: str) -> Dict[str, Any]:
        """
        Returns either {'ok': True, 'data': {...}} or {'ok': False, 'error': 'reason', 'detail': {...}}
        """
        # Basic checks
        if not self.secret_key:
            return {"ok": False, "error": "missing_secret_key", "detail": "PAYSTACK_SECRET_KEY env var is not set."}
        if not callback_url:
            return {"ok": False, "error": "missing_callback", "detail": "PAYSTACK_CALLBACK_URL env var is not set."}
        if not email or "@" not in email:
            return {"ok": False, "error": "invalid_email", "detail": f"Invalid email: {email}"}

        product = self.products.get_product(product_id)
        if not product:
            return {"ok": False, "error": "product_not_found", "detail": f"Product id {product_id} not found."}

        amount = product.get("price")
        try:
            amount_smallest = int(round(float(amount) * 100))
        except Exception as e:
            return {"ok": False, "error": "invalid_price", "detail": f"Invalid product price: {amount}. error: {e}"}

        payload = {
            "email": email,
            "amount": amount_smallest,
            "reference": reference,
            "callback_url": callback_url,
            "metadata": {"product_id": product_id}
        }

        try:
            resp = requests.post(f"{self.base_url}/transaction/initialize",
                                 json=payload, headers=self.headers, timeout=15)
        except requests.RequestException as e:
            logger.exception("HTTP request to Paystack failed")
            return {"ok": False, "error": "http_error", "detail": str(e)}

        # capture status and body
        status = resp.status_code
        try:
            body = resp.json()
        except Exception:
            body = {"raw_text": resp.text}

        if status >= 400 or not body.get("status"):
            logger.error("Paystack init failed status=%s body=%s", status, body)
            return {"ok": False, "error": "paystack_init_failed", "detail": body}

        # success
        data = body.get("data", {})
        logger.info("Paystack initialized: reference=%s auth_url=%s", data.get("reference"), data.get("authorization_url"))
        return {"ok": True, "data": data}

    def verify_payment(self, reference: str) -> Dict[str, Any]:
        """
        Verifies transaction. Returns structured dict:
        {'ok': True, 'data': {...}} or {'ok': False, 'error': 'reason', 'detail': {...}}
        """
        if not self.secret_key:
            return {"ok": False, "error": "missing_secret_key", "detail": "PAYSTACK_SECRET_KEY env var is not set."}
        try:
            resp = requests.get(f"{self.base_url}/transaction/verify/{reference}",
                                headers=self.headers, timeout=15)
        except requests.RequestException as e:
            logger.exception("Paystack verify HTTP error")
            return {"ok": False, "error": "http_error", "detail": str(e)}

        try:
            body = resp.json()
        except Exception:
            body = {"raw_text": resp.text}

        if resp.status_code >= 400 or not body.get("status"):
            logger.error("Paystack verify failed status=%s body=%s", resp.status_code, body)
            return {"ok": False, "error": "verify_failed", "detail": body}

        data = body.get("data", {})
        if data.get("status") != "success":
            return {"ok": False, "error": "not_successful", "detail": data}

        # get product info
        product_id = data.get("metadata", {}).get("product_id")
        product = self.products.get_product(product_id)
        return {"ok": True, "data": {"product": product, "payload": data}}
