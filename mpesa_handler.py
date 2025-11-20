import base64
import datetime
import requests
from requests.auth import HTTPBasicAuth
import os
import logging

logger = logging.getLogger(__name__)

class MpesaHandler:
    def __init__(self):
        # Load configuration from environment variables
        self.consumer_key = os.getenv('MPESA_CONSUMER_KEY')
        self.consumer_secret = os.getenv('MPESA_CONSUMER_SECRET')
        self.passkey = os.getenv('MPESA_PASSKEY')
        self.business_shortcode = os.getenv('MPESA_BUSINESS_SHORTCODE', '174379')
        self.callback_url = os.getenv('MPESA_CALLBACK_URL')

        # Safaricom API endpoints (sandbox)
        self.auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        self.stk_push_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        self.stk_query_url = "https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query"

        self.access_token = None
        self.token_expiry = None

    def get_access_token(self) -> str:
        """Obtain M-Pesa API access token."""
        try:
            response = requests.get(
                self.auth_url,
                auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret),
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data.get('access_token')
            # Set token expiry (typically 1 hour)
            self.token_expiry = datetime.datetime.now() + datetime.timedelta(seconds=3500)
            
            logger.info("M-Pesa access token obtained successfully")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get M-Pesa access token: {e}")
            raise Exception("M-Pesa authentication failed")

    def ensure_valid_token(self) -> str:
        """Ensure we have a valid access token."""
        if not self.access_token or not self.token_expiry or datetime.datetime.now() >= self.token_expiry:
            return self.get_access_token()
        return self.access_token

    def generate_password(self) -> tuple:
        """Generate Lipa Na M-Pesa password."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        data_to_encode = f"{self.business_shortcode}{self.passkey}{timestamp}"
        encoded_password = base64.b64encode(data_to_encode.encode()).decode()
        return encoded_password, timestamp

    def make_stk_push(self, phone_number: str, amount: int, account_reference: str) -> dict:
        """Initiate STK push to customer's phone."""
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
                "TransactionDesc": "Digital Product Purchase"
            }

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            response = requests.post(self.stk_push_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"STK Push initiated: {result}")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"STK Push request failed: {e}")
            raise Exception("Failed to initiate M-Pesa payment")

    def query_transaction_status(self, checkout_request_id: str) -> dict:
        """Query status of an STK push transaction."""
        try:
            self.ensure_valid_token()
            password, timestamp = self.generate_password()

            payload = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            response = requests.post(self.stk_query_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Transaction query failed: {e}")
            raise Exception("Failed to query transaction status")
