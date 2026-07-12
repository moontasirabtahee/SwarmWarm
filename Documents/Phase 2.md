# **Phase 2: Core Engine & Protocol Prototyping**

**Project:** SwarmWarm (Multi-Tenant P2P Email Warmup Engine)  
**Lead Engineer:** M. A. Moontasir Abtahee  
**Phase:** 2 (Core Engine & Cryptographic Protocol Prototyping Specification)  
**Status:** Approved for Core Prototyping

---

## **1. Executive Summary**

Phase 2 focuses on building the local execution engine, establishing secure, multi-tenant environment wrappers, and creating the cryptographic security framework to safeguard mailbox credentials. Outbound P2P traffic requires storing SMTP/IMAP application passwords; to ensure absolute security, credentials must be encrypted symmetrically before database serialization.

---

## **2. Cryptographic Security Wrapper (`security.py`)**

To secure mailbox authentication tokens (SMTP/IMAP App Passwords), the platform integrates a utility module using AES-256-GCM symmetric encryption.

```python
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Retrieve master key from environment variables
MASTER_KEY_HEX = os.getenv("SWARMWARM_DECRYPTION_KEY")

def encrypt_credentials(plaintext: str) -> str:
    """
    Encrypts email credentials using AES-256-GCM.
    Returns base64 encoded string containing nonce + ciphertext + tag.
    """
    key = bytes.fromhex(MASTER_KEY_HEX)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    # Combine nonce and ciphertext for database storage
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode('utf-8')

def decrypt_credentials(ciphertext_b64: str) -> str:
    """
    Decrypts base64 encoded ciphertext string using the master key.
    """
    key = bytes.fromhex(MASTER_KEY_HEX)
    aesgcm = AESGCM(key)
    combined = base64.b64decode(ciphertext_b64.encode('utf-8'))
    nonce = combined[:12]
    ciphertext = combined[12:]
    decrypted = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted.decode('utf-8')
```

---

## **3. Protocol Integration & Connection Handshakes**

The system executes connection checks and handshakes against Google Workspace (SMTP/IMAP) and Microsoft 365.

### **SMTP Connection Flow (Google Workspace)**
- **Host:** `smtp.gmail.com`
- **Port:** `465` (SSL) or `587` (TLS)
- **Handshake Logic:** Verify active app password authentication before finalizing DB state update.

### **IMAP Connection Flow (Google Workspace)**
- **Host:** `imap.gmail.com`
- **Port:** `993` (SSL)
- **Handshake Logic:** Access mailbox folder structure, verify folders (Inbox, Spam) and check permission flags.

---

## **4. Verification & Diagnostics Checklist**

Before transitioning to the message queue and background worker integration in Phase 3, verify that the cryptographic logic and socket connections pass:

| Target Component | Diagnostic Test Case | Expected Outcome |
| :--- | :--- | :--- |
| **Symmetric Wrapper** | Encrypt string → decrypt string | Output matches the original plaintext string exactly. |
| **SMTP Auth Handshake** | Initiate socket to `smtp.gmail.com:465` with credentials | Successful `235 2.7.0 Authentication successful` response code. |
| **IMAP Auth Handshake** | Initiate socket to `imap.gmail.com:993` with credentials | Mailbox connection established; returns list of directory folders. |
