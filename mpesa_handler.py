# mpesa_handler.py
import base64
import datetime
import os
import logging
import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

class MpesaHandler:
    def __init__(self):
        self.consumer_key = os.getenv("MPESA_CONSUMER_KEY", "")
        self.consumer_secret = os.getenv("MPESA_CONSUMER_SECRET", "")
        self.passkey = os.getenv("MPESA_PASSKEY", "")
        self.business_shortcode = os.getenv("MPESA_BUSINESS_SHORTCODE", "174379")
        self.callback_url = os.getenv("MPESA_CALLBACK_URL")

        self.auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        self.stk_push_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

        self.access_token = None
        self.token_expiry = None

    def get_access_token(self):
        try:
            resp = requests.get(self.auth_url, auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret))
            resp.raise_for_status()
            data = resp.json()
            self.access_token = data.get("access_token")
            self.token_expiry = datetime.datetime.now() + datetime.timedelta(seconds=3500)
            return self.access_token
        except Exception as e:
            logger.error(f"M-Pesa token error: {e}")
            raise

    def ensure_token(self):
        if not self.access_token or not self.token_expiry or datetime.datetime.now() >= self.token_expiry:
            return self.get_access_token()
        return self.access_token

    def generate_password(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        raw = f"{self.business_shortcode}{self.passkey}{timestamp}"
        encoded = base64.b64encode(raw.encode()).decode()
        return encoded, timestamp

    def make_stk_push(self, phone_number: str, amount: int, account_reference: str):
        self.ensure_token()
        password, timestamp = self.generate_password()
        payload = {
            "BusinessShortCode": self.business_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone_number,
            "PartyB": self.business_shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": self.callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": "Telegram Bot Purchase"
        }
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        resp = requests.post(self.stk_push_url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()
