import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict

DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "swarmwarm.db"))

def get_db_connection():
    """
    Establishes a thread-safe connection to the SQLite database.
    Enforces row factory to return dictionaries instead of tuples.
    """
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # Enforce foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """
    Initializes database tables and inserts mock seeds if database is empty.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Create Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user' NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 2. Create Mailboxes Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mailboxes (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        email TEXT UNIQUE NOT NULL,
        smtp_host TEXT NOT NULL,
        smtp_port INTEGER NOT NULL,
        imap_host TEXT NOT NULL,
        imap_port INTEGER NOT NULL,
        encrypted_password TEXT NOT NULL,
        provider TEXT NOT NULL,
        use_ssl INTEGER DEFAULT 1,
        daily_send_limit INTEGER DEFAULT 40,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 3. Create Interaction Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interaction_logs (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        mailbox_id TEXT REFERENCES mailboxes(id) ON DELETE SET NULL,
        recipient_email TEXT NOT NULL,
        subject TEXT,
        action TEXT NOT NULL,
        folder TEXT DEFAULT 'INBOX',
        ai_replied INTEGER DEFAULT 0,
        error_message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 4. Create System Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_logs (
        id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        module TEXT NOT NULL,
        event TEXT NOT NULL,
        level TEXT DEFAULT 'INFO' NOT NULL
    );
    """)
    
    conn.commit()
    
    # Seed Initial Data if Users Table is empty
    cursor.execute("SELECT COUNT(*) FROM users;")
    if cursor.fetchone()[0] == 0:
        # Hashed password for 'admin' using sha256_crypt (matching user_admin in memory)
        default_pwd_hash = "$5$rounds=535000$Th1sEM1YEuPGZ2zN$jP/jNldccT0jg0gtKa.8PHczAp8GAhgSzWdSwckLGJ2"
        
        # Seed users
        cursor.execute("INSERT INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?);",
                       ("user_admin", "ieee.dobby1998@gmail.com", default_pwd_hash, "admin"))
        cursor.execute("INSERT INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?);",
                       ("user_1", "abtahee@qoarc.com", default_pwd_hash, "user"))
        cursor.execute("INSERT INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?);",
                       ("user_2", "m.abtahee@brownmafia.com", default_pwd_hash, "user"))
        
        # Seed mailboxes
        cursor.execute("""
        INSERT INTO mailboxes (id, user_id, email, smtp_host, smtp_port, imap_host, imap_port, encrypted_password, provider, use_ssl) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("mailbox_admin_google", "user_admin", "ieee.dobby1998@gmail.com", "smtp.gmail.com", 465, "imap.gmail.com", 993, "PTT8XA-KBmrFyBphxcUTX8R1yB4zlZs0H3qSeG8301NLBPdIDOTkgv06TkBXuXs=", "google", 1))
        
        cursor.execute("""
        INSERT INTO mailboxes (id, user_id, email, smtp_host, smtp_port, imap_host, imap_port, encrypted_password, provider, use_ssl) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("mailbox_google_1", "user_1", "abtahee@qoarc.com", "smtp.gmail.com", 465, "imap.gmail.com", 993, "4jRTREI1DyqWaIt1SaI7aF2A_MELB1zDvSFyFOJwQBVpCfeOT1rRSV-mPpiWgpcMUbkHcV8g-0fRZGMmBvLL", "google", 1))
        
        cursor.execute("""
        INSERT INTO mailboxes (id, user_id, email, smtp_host, smtp_port, imap_host, imap_port, encrypted_password, provider, use_ssl) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("mailbox_microsoft_1", "user_2", "m.abtahee@brownmafia.com", "smtp.office365.com", 587, "outlook.office365.com", 993, "GS4Cqdt1Jnc3TGrTpi_fKuPFQB73mlp0CjWehQW3-7jqmAli-CfyS1sFb1uyg_J_zAldJ9EjUxPcfKpxP1GY", "microsoft", 0))
        
        # Seed initial interaction logs
        cursor.execute("""
        INSERT INTO interaction_logs (id, user_id, mailbox_id, recipient_email, subject, action, folder, ai_replied, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("log_1", "user_1", "mailbox_google_1", "m.abtahee@brownmafia.com", "Warmup Sync Request", "sent", "INBOX", 1, "2026-07-12T10:00:00Z"))
        cursor.execute("""
        INSERT INTO interaction_logs (id, user_id, mailbox_id, recipient_email, subject, action, folder, ai_replied, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("log_2", "user_1", "mailbox_google_1", "node01@mabsj.com", "Warmup Sync Request", "sent", "INBOX", 1, "2026-07-12T12:00:00Z"))
        cursor.execute("""
        INSERT INTO interaction_logs (id, user_id, mailbox_id, recipient_email, subject, action, folder, ai_replied, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("log_3", "user_1", "mailbox_google_1", "outreach@startup.net", "SwarmWarm Rescue", "rescued", "Spam", 0, "2026-07-12T14:00:00Z"))
        cursor.execute("""
        INSERT INTO interaction_logs (id, user_id, mailbox_id, recipient_email, subject, action, folder, ai_replied, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("log_4", "user_1", "mailbox_google_1", "outreach@startup.net", "Warmup Sync Request", "sent", "INBOX", 0, "2026-07-12T16:00:00Z"))
        cursor.execute("""
        INSERT INTO interaction_logs (id, user_id, mailbox_id, recipient_email, subject, action, folder, ai_replied, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, ("log_5", "user_2", "mailbox_microsoft_1", "abtahee@qoarc.com", "Warmup Sync Request", "sent", "INBOX", 1, "2026-07-12T11:00:00Z"))
        
        # Seed initial system logs
        cursor.execute("""
        INSERT INTO system_logs (id, timestamp, module, event, level)
        VALUES (?, ?, ?, ?, ?);
        """, ("syslog_1", "2026-07-12 20:38:12", "CELERY_BEAT", "Nightly P2P bipartite graph mapping complete.", "INFO"))
        cursor.execute("""
        INSERT INTO system_logs (id, timestamp, module, event, level)
        VALUES (?, ?, ?, ?, ?);
        """, ("syslog_2", "2026-07-12 20:39:01", "REDIS_BROKER", "Enqueued 42 task items into FIFO channel buffer.", "INFO"))
        cursor.execute("""
        INSERT INTO system_logs (id, timestamp, module, event, level)
        VALUES (?, ?, ?, ?, ?);
        """, ("syslog_3", "2026-07-12 20:41:14", "LOCAL_AI_NODE", "Gemma 4B compiled context tokens. (42 t/s)", "INFO"))
        cursor.execute("""
        INSERT INTO system_logs (id, timestamp, module, event, level)
        VALUES (?, ?, ?, ?, ?);
        """, ("syslog_4", "2026-07-12 20:45:22", "SMTP_WORKER_02", "Connection block jitter offset applied: 47s.", "INFO"))
        cursor.execute("""
        INSERT INTO system_logs (id, timestamp, module, event, level)
        VALUES (?, ?, ?, ?, ?);
        """, ("syslog_5", "2026-07-12 20:50:05", "IMAP_WORKER_01", "[RESCUE] Account abtahee@qoarc.com flag fix complete.", "INFO"))
        
        conn.commit()
        
    conn.close()

# Auto-initialize database on module import
init_db()

# --- HELPER FUNCTIONS FOR USERS ---

def get_user_by_email(email: str) -> Optional[dict]:
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?);", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(email: str, password_hash: str, role: str = "user") -> dict:
    conn = get_db_connection()
    user_id = f"user_{get_user_count() + 1}"
    conn.execute(
        "INSERT INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?);",
        (user_id, email.lower(), password_hash, role)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE id = ?;", (user_id,)).fetchone()
    conn.close()
    return dict(row)

def get_user_count() -> int:
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
    conn.close()
    return count

def get_all_users() -> List[dict]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM users;").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- HELPER FUNCTIONS FOR MAILBOXES ---

def get_mailbox_by_id(mailbox_id: str) -> Optional[dict]:
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM mailboxes WHERE id = ?;", (mailbox_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["is_active"] = bool(d["is_active"])
        d["use_ssl"] = bool(d["use_ssl"])
        return d
    return None

def create_mailbox(user_id: str, email: str, smtp_host: str, smtp_port: int, imap_host: str, imap_port: int, provider: str, use_ssl: bool, encrypted_password: str) -> dict:
    conn = get_db_connection()
    mailbox_id = f"mailbox_{get_mailbox_count() + 1}"
    conn.execute(
        """
        INSERT INTO mailboxes (id, user_id, email, smtp_host, smtp_port, imap_host, imap_port, encrypted_password, provider, use_ssl, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
        """,
        (mailbox_id, user_id, email, smtp_host, smtp_port, imap_host, imap_port, encrypted_password, provider, 1 if use_ssl else 0)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM mailboxes WHERE id = ?;", (mailbox_id,)).fetchone()
    conn.close()
    d = dict(row)
    d["is_active"] = bool(d["is_active"])
    d["use_ssl"] = bool(d["use_ssl"])
    return d

def get_mailbox_count() -> int:
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(*) FROM mailboxes;").fetchone()[0]
    conn.close()
    return count

def list_mailboxes_by_user(user_id: str) -> List[dict]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM mailboxes WHERE user_id = ?;", (user_id,)).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["is_active"] = bool(d["is_active"])
        d["use_ssl"] = bool(d["use_ssl"])
        results.append(d)
    return results

def list_all_mailboxes() -> List[dict]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM mailboxes;").fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["is_active"] = bool(d["is_active"])
        d["use_ssl"] = bool(d["use_ssl"])
        results.append(d)
    return results

def update_mailbox_active_state(mailbox_id: str, is_active: bool):
    conn = get_db_connection()
    conn.execute("UPDATE mailboxes SET is_active = ? WHERE id = ?;", (1 if is_active else 0, mailbox_id))
    conn.commit()
    conn.close()

def delete_mailbox(mailbox_id: str):
    conn = get_db_connection()
    conn.execute("DELETE FROM mailboxes WHERE id = ?;", (mailbox_id,))
    conn.commit()
    conn.close()

# --- HELPER FUNCTIONS FOR INTERACTION LOGS ---

def create_interaction_log(user_id: str, mailbox_id: str, action: str, folder: str, ai_replied: bool, subject: Optional[str] = None, recipient_email: Optional[str] = "", error_message: Optional[str] = None) -> dict:
    conn = get_db_connection()
    # Generate log UUID
    import uuid
    log_id = f"log_{uuid.uuid4().hex[:8]}"
    created_at = datetime.utcnow().isoformat() + "Z"
    conn.execute(
        """
        INSERT INTO interaction_logs (id, user_id, mailbox_id, recipient_email, subject, action, folder, ai_replied, error_message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (log_id, user_id, mailbox_id, recipient_email, subject, action, folder, 1 if ai_replied else 0, error_message, created_at)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM interaction_logs WHERE id = ?;", (log_id,)).fetchone()
    conn.close()
    d = dict(row)
    d["ai_replied"] = bool(d["ai_replied"])
    return d

def list_interaction_logs_by_user(user_id: str) -> List[dict]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM interaction_logs WHERE user_id = ? ORDER BY created_at DESC;", (user_id,)).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["ai_replied"] = bool(d["ai_replied"])
        results.append(d)
    return results

def list_interaction_logs_by_mailbox(mailbox_id: str) -> List[dict]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM interaction_logs WHERE mailbox_id = ? ORDER BY created_at DESC;", (mailbox_id,)).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["ai_replied"] = bool(d["ai_replied"])
        results.append(d)
    return results

def list_all_interaction_logs() -> List[dict]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM interaction_logs ORDER BY created_at DESC LIMIT 100;").fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["ai_replied"] = bool(d["ai_replied"])
        results.append(d)
    return results

# --- HELPER FUNCTIONS FOR SYSTEM LOGS ---

def create_system_log(module: str, event: str, level: str = "INFO") -> dict:
    conn = get_db_connection()
    import uuid
    log_id = f"syslog_{uuid.uuid4().hex[:8]}"
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO system_logs (id, timestamp, module, event, level) VALUES (?, ?, ?, ?, ?);",
        (log_id, timestamp, module, event, level)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM system_logs WHERE id = ?;", (log_id,)).fetchone()
    conn.close()
    return dict(row)

def list_system_logs() -> List[dict]:
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT 50;").fetchall()
    conn.close()
    return [dict(r) for r in rows]
