import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + pwdhash.hex()

def verify_password(password: str, hash: str) -> bool:
    salt = hash[:32]
    stored_hash = hash[32:]
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return pwdhash.hex() == stored_hash

def generate_token() -> str:
    return secrets.token_urlsafe(32)

def verify_telegram_data(data: dict, bot_token: str) -> bool:
    check_hash = data.pop('hash', '')
    data_check_string = '\n'.join([f"{k}={v}" for k, v in sorted(data.items())])
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return calculated_hash == check_hash
