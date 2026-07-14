import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from app.core.settings import settings

SECRET_KEY_RAW = settings.SWARMWARM_SECRET_KEY

if not SECRET_KEY_RAW:
    raise ValueError("Missing SWARMWARM_SECRET_KEY environment variable. Check your .env file.")


def _load_master_key(raw: str) -> bytes:
    """
    Resolves a 32-byte AES-256 master key from a variety of common encodings so the
    service is resilient to how the key was generated (standard base64, url-safe
    base64 with or without padding, or a 64-character hex string).
    """
    candidate = raw.strip()

    # 1. Hex (64 hex chars -> 32 bytes)
    if len(candidate) == 64:
        try:
            key = bytes.fromhex(candidate)
            if len(key) == 32:
                return key
        except ValueError:
            pass

    # 2. Standard / url-safe base64 (tolerate missing padding)
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            padded = candidate + "=" * (-len(candidate) % 4)
            key = decoder(padded)
            if len(key) == 32:
                return key
        except Exception:
            continue

    raise ValueError(
        "SWARMWARM_SECRET_KEY must resolve to exactly 32 bytes "
        "(base64, url-safe base64, or 64-char hex)."
    )


MASTER_KEY_BYTES = _load_master_key(SECRET_KEY_RAW)

def encrypt_token(plaintext: str) -> str:
    """
    Encrypts sensitive tokens/credentials using AES-256-GCM.
    Returns a URL-safe base64 encoded string containing nonce + ciphertext.
    """
    if not plaintext:
        raise ValueError("Plaintext cannot be empty.")
        
    aesgcm = AESGCM(MASTER_KEY_BYTES)
    nonce = os.urandom(12)  # 12-byte cryptographically secure random nonce
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    
    # Prepend the nonce to the ciphertext
    combined = nonce + ciphertext
    return base64.urlsafe_b64encode(combined).decode('utf-8')

def decrypt_token(ciphertext_b64: str) -> str:
    """
    Decrypts a URL-safe base64 encoded ciphertext string.
    Gracefully handles tag verification errors or tampering.
    """
    if not ciphertext_b64:
        raise ValueError("Ciphertext base64 string cannot be empty.")
        
    try:
        combined = base64.urlsafe_b64decode(ciphertext_b64.encode('utf-8'))
        if len(combined) < 12:
            raise ValueError("Ciphertext is too short (must contain at least 12-byte nonce).")
            
        nonce = combined[:12]
        ciphertext = combined[12:]
        
        aesgcm = AESGCM(MASTER_KEY_BYTES)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode('utf-8')
    except InvalidTag:
        raise ValueError("Decryption failed: Ciphertext tag verification failed (tampered data or wrong key).")
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")
