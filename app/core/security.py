import os
import base64
from dotenv import load_dotenv
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

# Load environmental variables
load_dotenv()

SECRET_KEY_B64 = os.getenv("SWARMWARM_SECRET_KEY")

if not SECRET_KEY_B64:
    raise ValueError("Missing SWARMWARM_SECRET_KEY environment variable. Check your .env file.")

try:
    # Decode the base64 master key to raw bytes
    MASTER_KEY_BYTES = base64.b64decode(SECRET_KEY_B64)
    if len(MASTER_KEY_BYTES) != 32:
         raise ValueError("SWARMWARM_SECRET_KEY must decode to exactly 32 bytes.")
except Exception as e:
    raise ValueError(f"Invalid SWARMWARM_SECRET_KEY base64 format: {e}")

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
