import base64
import hashlib
import json

from cryptography.fernet import Fernet
from flask import current_app


def _cipher():
    digest = hashlib.sha256(current_app.config["SECRET_KEY"].encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_json(value):
    return _cipher().encrypt(json.dumps(value).encode()).decode()


def decrypt_json(value):
    return json.loads(_cipher().decrypt(value.encode()).decode())

