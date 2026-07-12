# Shared In-Memory Database Registry for Local Testing/Simulation
# This models Supabase tables locally to enable state persistence across endpoints and workers.

# 1. Users Table
USERS = {
    "ieee.dobby1998@gmail.com": {
        "id": "user_admin",
        "email": "ieee.dobby1998@gmail.com",
        "password_hash": "$5$rounds=535000$Th1sEM1YEuPGZ2zN$jP/jNldccT0jg0gtKa.8PHczAp8GAhgSzWdSwckLGJ2",
        "role": "admin"
    }
}

# 2. Mailboxes Table
MAILBOXES = {
    "mailbox_admin_google": {
        "id": "mailbox_admin_google",
        "user_id": "user_admin",
        "email": "ieee.dobby1998@gmail.com",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 465,
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "provider": "google",
        "use_ssl": True,
        "is_active": True,
        "encrypted_password": "PTT8XA-KBmrFyBphxcUTX8R1yB4zlZs0H3qSeG8301NLBPdIDOTkgv06TkBXuXs="
    },
    "mailbox_google_1": {
        "id": "mailbox_google_1",
        "user_id": "user_1",
        "email": "abtahee@qoarc.com",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 465,
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "provider": "google",
        "use_ssl": True,
        "is_active": True,
        "encrypted_password": "4jRTREI1DyqWaIt1SaI7aF2A_MELB1zDvSFyFOJwQBVpCfeOT1rRSV-mPpiWgpcMUbkHcV8g-0fRZGMmBvLL"
    },
    "mailbox_microsoft_1": {
        "id": "mailbox_microsoft_1",
        "user_id": "user_2",
        "email": "m.abtahee@brownmafia.com",
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "provider": "microsoft",
        "use_ssl": False,
        "is_active": True,
        "encrypted_password": "GS4Cqdt1Jnc3TGrTpi_fKuPFQB73mlp0CjWehQW3-7jqmAli-CfyS1sFb1uyg_J_zAldJ9EjUxPcfKpxP1GY"
    }
}

# 3. Interaction Logs Table
INTERACTION_LOGS = [
    {"user_id": "user_1", "mailbox_id": "mailbox_google_1", "action": "sent", "folder": "INBOX", "ai_replied": True, "created_at": "2026-07-12T10:00:00Z"},
    {"user_id": "user_1", "mailbox_id": "mailbox_google_1", "action": "sent", "folder": "INBOX", "ai_replied": True, "created_at": "2026-07-12T12:00:00Z"},
    {"user_id": "user_1", "mailbox_id": "mailbox_google_1", "action": "rescued", "folder": "Spam", "ai_replied": False, "created_at": "2026-07-12T14:00:00Z"},
    {"user_id": "user_1", "mailbox_id": "mailbox_google_1", "action": "sent", "folder": "INBOX", "ai_replied": False, "created_at": "2026-07-12T16:00:00Z"},
    {"user_id": "user_2", "mailbox_id": "mailbox_microsoft_1", "action": "sent", "folder": "INBOX", "ai_replied": True, "created_at": "2026-07-12T11:00:00Z"},
]
