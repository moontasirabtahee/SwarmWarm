import os
import sys

# Allow running standalone (python scripts/test_crypto.py) without setting PYTHONPATH.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.security import encrypt_token, decrypt_token

def test_crypto_subsystem():
    print("================================================================================")
    print("                 SWARMWARM CRYPTOGRAPHIC SYSTEM DIAGNOSTIC")
    print("================================================================================")
    
    test_secret = "smtp_app_password_secret_key_12345!"
    print(f"Original Plaintext: {test_secret}")
    
    try:
        # Round 1 Encryption
        enc_1 = encrypt_token(test_secret)
        print(f"Encryption Round 1 (URL-Safe Base64): {enc_1}")
        
        # Round 2 Encryption
        enc_2 = encrypt_token(test_secret)
        print(f"Encryption Round 2 (URL-Safe Base64): {enc_2}")
        
        # Uniqueness assertion (Nonce check)
        assert enc_1 != enc_2, "CRITICAL ERROR: Encrypting same string produced identical outputs (nonce reuse check failed)."
        print(" [+] Success: Nonces are randomized; cipher signatures are unique.")
        
        # Decryption check
        dec_1 = decrypt_token(enc_1)
        dec_2 = decrypt_token(enc_2)
        
        assert dec_1 == test_secret, "Decryption Round 1 mismatch!"
        assert dec_2 == test_secret, "Decryption Round 2 mismatch!"
        print(" [+] Success: Decrypted payloads match the original plaintext exactly.")
        
        # Tampering / Invalid Tag check
        tampered = enc_1[:-4] + "AAAA"
        try:
            decrypt_token(tampered)
            assert False, "CRITICAL ERROR: Tampered ciphertext was decrypted without raising exception."
        except ValueError as val_err:
            print(f" [+] Success: Tampered ciphertext correctly rejected. Message: {val_err}")
            
        print("\n================================================================================")
        print("                 CRYPTOGRAPHIC INTEGRITY SYSTEM DIAGNOSTIC: PASS")
        print("================================================================================")
        
    except Exception as e:
        print(f"\n[-] SYSTEM DIAGNOSTIC FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_crypto_subsystem()
