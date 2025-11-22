# paystack_handler.py
import os
import requests
import logging

logger = logging.getLogger(__name__)

# ========= YOUR PRODUCTS ==========
# Make these prices match ProductService prices
PRODUCTS = {
    "1": {
        "name": "Spotify Premium",
        "price": 1,
        "pixeldrain_link": "https://pixeldrain.com/u/aakwH36V"
    },
    "2": {
        "name": "Basic Software Package",
        "price": 250,
        "pixeldrain_link": "https://pixeldrain.com/u/your-file-id-2"
    },
    "3": {
        "name": "Advanced Tools Bundle",
        "price": 750,
        "pixeldrain_link": "https://pixeldrain.com/u/your-file-id-3"
    }
}
# ===================================

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

    def initialize_payment(self, email: str, product_id: str, reference: str, callback_url: str):
        product = PRODUCTS.get(product_id)
        if not product:
            logger.error("Product not found: %s", product_id)
            return {}

        payload = {
            "email": email,
            "amount": product["price"] * 100,
            "reference": reference,
            "callback_url": callback_url,
            "metadata": {"product_id": product_id}
        }

        try:
            resp = requests.post(
                f"{self.base_url}/transaction/initialize",
                json=payload,
                headers=self.headers,
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status"):
                return data["data"]
            return {}
        except Exception as e:
            logger.exception("Paystack init error: %s", e)
            return {}

    def verify_payment(self, reference: str):
        try:
            resp = requests.get(
                f"{self.base_url}/transaction/verify/{reference}",
                headers=self.headers,
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("status") or data["data"]["status"] != "success":
                return {"status": "failed"}

            product_id = data["data"]["metadata"].get("product_id")
            product = PRODUCTS.get(product_id)

            return {
                "status": "success",
                "product_name": product["name"],
                "download_link": product["pixeldrain_link"]
            }

        except Exception as e:
            logger.exception("Paystack verify error: %s", e)
            return {"status": "error", "message": str(e)}
