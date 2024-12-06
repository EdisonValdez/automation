"""Custom request call"""
import hashlib
import hmac
import json
import time
import requests
from typing import Tuple
from automation import settings
from automation.request.exception import InvalidRequest


class ResourceAccessSignature:
    """
    Class for generating and managing access signatures for resource requests.
    """
    __secret_key = None
    __namespace = "localsecret"

    def __init__(self):
        self.__secret_key = settings.SIGATURE_SECRET

    def generate_signature(self, topic: str):
        """
        Generate a signature for a given namespace and topic.
        """
        timestamp = int(time.time())
        signature_data = f"REQUEST::{self.__namespace}::{topic}::POST::{str(timestamp)}"
        signature = hmac.new(self.__secret_key.encode(
            encoding='utf8', errors='strict'),
            signature_data.encode(),
            hashlib.sha256).hexdigest()

        return timestamp, signature


class ResourceVerifySignature:
    """
    Class for verifying access signatures for resource requests.
    """
    __secret_key = None
    __namespace = "localsecret"

    def __init__(self):
        self.__secret_key = settings.SECRET_KEY

    def validate_signature(
            self, topic, timestamp, client_signature):
        """
        Validate the provided signature against the server-generated signature.
        """
        signature_data = f"REQUEST::{self.__namespace}::{topic}::POST::{str(timestamp)}"
        server_signature = hmac.new(
            self.__secret_key.encode(),
            signature_data.encode(),
            hashlib.sha256).hexdigest()
        return client_signature == server_signature


class RequestClient:
    """
    Client for making authenticated requests to a specified namespace and topic.
    """

    def __init__(self):
        pass

    def _decode_response(self, response_data: str = None):
        """
        Decode the response data from the server.
        """
        try:
            data = json.loads(response_data)
        except json.JSONDecodeError:
            data = response_data

        if isinstance(data, str):
            if data.isdigit():
                return int(data)
            try:
                return float(data)
            except ValueError:
                return data
        return data

    def request(self, topic: str, business_data:dict)-> Tuple[bool, str]:
        """
        Make a POST request to the specified with the given parameters.
        """

        # Generate and validate access signature for the request
        rs = ResourceAccessSignature()
        timestamp, signature = rs.generate_signature(topic)

        url = f"{settings.LOCAL_SECRET_BASE_URL}/api/custom-request/{topic}"
        header = {
            "Content-Type": "application/json",
            "X-Signature": signature,
            "X-Timestamp": str(timestamp)
        }
    
        response = requests.post(
            url, data=business_data,
            headers=header, verify=False)
        
        try:
            response.raise_for_status()
            response_data = response.json()
            
            if response_data.get("hasError") is True:
                raise ValueError(response_data.get("message"))     
        
        except requests.exceptions.HTTPError as e:
            raise 