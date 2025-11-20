# mpesa_handler.py
import base64
import datetime
import requests
from requests.auth import HTTPBasicAuth
import os
import logging

logger = logging.getLogger(__name__)

class MpesaHandler:
    def __init__(self):
        # Load environment variables
        self.consumer_key = os.getenv('MPESA_CONSUMER_KEY', '')
        self.consumer_secret = os.getenv('MPESA_CONSUMER_SECRET', '')
        self.passkey = os.getenv('MPESA_PASSKEY', '')
        self.business_shortcode = os.getenv('MPESA_BUSINESS_SHORTCODE', '174379')
        self.callback_url = os.getenv('MPESA_CALLBACK_URL')  # must be public
        # sandbox endpoints (change to production when ready)
        self.auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        self.stk_push_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        self.query_url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"

        self.access_token = None
        self.token_expiry = None

    def get_mpesa_access_token(self):
        if not self.consumer_key or not self.consumer_secret:
            raise RuntimeError("MPESA_CONSUMER_KEY / MPESA_CONSUMER_SECRET not set")
        resp = requests.get(self.auth_url, auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data.get("access_token")
        self.token_expiry = datetime.datetime.now() + datetime.timedelta(seconds=3500)
        logger.info("Obtained M-Pesa access token")
        return self.access_token

    def ensure_valid_token(self):
        if not self.access_token or not self.token_expiry or datetime.datetime.now() >= self.token_expiry:
            return self.get_mpesa_access_token()
        return self.access_token

    def generate_password(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        raw = f"{self.business_shortcode}{self.passkey}{timestamp}"
        encoded_password = base64.b64encode(raw.encode()).decode()
        return encoded_password, timestamp

    def make_stk_push(self, phone_number: str, amount: int, account_reference: str):
        self.ensure_valid_token()
        password, timestamp = self.generate_password()

        payload = {
            "BusinessShortCode": self.business_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": str(amount),
            "PartyA": phone_number,
            "PartyB": self.business_shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": self.callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": "Telegram Bot Purchase"
        }

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        resp = requests.post(self.stk_push_url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        logger.info("STK push response: %s", data)
        return data

    def query_transaction_status(self, checkout_request_id: str):
        self.ensure_valid_token()
        password, timestamp = self.generate_password()
        payload = {
            "BusinessShortCode": self.business_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        resp = requests.post(self.query_url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Query response: %s", data)
        return data
