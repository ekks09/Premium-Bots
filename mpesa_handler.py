import base64
import datetime
import requests
from requests.auth import HTTPBasicAuth
import os
import logging

logger = logging.getLogger(__name__)


class MpesaHandler:
    def __init__(self):
        # Load all secrets from environment variables
        self.consumer_key = os.getenv('MPESA_CONSUMER_KEY', '')
        self.consumer_secret = os.getenv('MPESA_CONSUMER_SECRET', '')
        self.passkey = os.getenv('MPESA_PASSKEY', '')
        self.business_shortcode = os.getenv('MPESA_BUSINESS_SHORTCODE', '174379')

        # IMPORTANT: callback_url must be public (Heroku/ngrok)
        self.callback_url = os.getenv('MPESA_CALLBACK_URL')

        # Safaricom endpoints (use sandbox)
        self.auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        self.stk_push_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        self.query_url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"

        self.access_token = None
        self.token_expiry = None

    def get_mpesa_access_token(self):
        """Request M-Pesa OAuth token"""
        try:
            resp = requests.get(
                self.auth_url,
                auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret)
            )
            resp.raise_for_status()

            data = resp.json()
            self.access_token = data.get("access_token")
            # Token lasts 3600 sec → refresh early
            self.token_expiry = datetime.datetime.now() + datetime.timedelta(seconds=3500)

            logger.info("New M-Pesa access token issued")
            return self.access_token

        except Exception as e:
            logger.error(f"Token error: {e}")
            raise

    def ensure_valid_token(self):
        """Ensure working token or refresh"""
        if (
            not self.access_token
            or not self.token_expiry
            or datetime.datetime.now() >= self.token_expiry
        ):
            return self.get_mpesa_access_token()
        return self.access_token

    def generate_password(self):
        """Generate Lipa na M-Pesa encoded password"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        raw = f"{self.business_shortcode}{self.passkey}{timestamp}"
        encoded_password = base64.b64encode(raw.encode()).decode()
        return encoded_password, timestamp

    def make_stk_push(self, phone_number: str, amount: int, account_reference: str):
        """Trigger STK push request"""
        try:
            self.ensure_valid_token()
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

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            resp = requests.post(self.stk_push_url, json=payload, headers=headers)
            resp.raise_for_status()

            data = resp.json()
            logger.info(f"STK Push -> {data}")
            return data

        except Exception as e:
            logger.error(f"STK push failed: {e}")
            raise

    def query_transaction_status(self, checkout_request_id: str):
        """Query STK push status"""
        try:
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

            resp = requests.post(self.query_url, json=payload, headers=headers)
            resp.raise_for_status()

            data = resp.json()
            logger.info(f"Query -> {data}")
            return data

        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise
