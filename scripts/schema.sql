-- ==============================================================================
# SWARMWARM PHASE 1 - RELATIONAL DATABASE SCHEMA DEFINITIONS
# Execute this file directly in your Supabase SQL Editor console.
# ==============================================================================

-- 1. Ensure UUID Extension is Enabled for Native UUID Primary Keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Users Storage Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(50) DEFAULT 'user' NOT NULL, -- 'admin' or 'user'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Mailboxes Storage Table (ON DELETE CASCADE)
CREATE TABLE IF NOT EXISTS mailboxes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    smtp_host VARCHAR(255) NOT NULL,
    smtp_port INT NOT NULL,
    imap_host VARCHAR(255) NOT NULL,
    imap_port INT NOT NULL,
    encrypted_password TEXT NOT NULL,
    provider VARCHAR(50) NOT NULL,    -- 'google', 'microsoft', 'custom'
    daily_send_limit INT DEFAULT 40,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Warmup Schedules Storage Table (ON DELETE CASCADE)
CREATE TABLE IF NOT EXISTS warmup_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mailbox_id UUID REFERENCES mailboxes(id) ON DELETE CASCADE UNIQUE NOT NULL,
    current_day_number INT DEFAULT 1,
    target_send_count INT DEFAULT 2,
    emails_sent_today INT DEFAULT 0,
    is_cooling_down BOOLEAN DEFAULT FALSE,
    last_processed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Interaction Logs Storage Table (ON DELETE SET NULL)
CREATE TABLE IF NOT EXISTS interaction_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_mailbox_id UUID REFERENCES mailboxes(id) ON DELETE SET NULL,
    recipient_mailbox_id UUID REFERENCES mailboxes(id) ON DELETE SET NULL,
    message_id VARCHAR(255),
    subject TEXT,
    action_type VARCHAR(50) NOT NULL,      -- 'send', 'reply', 'spam_rescue'
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'success', 'failed'
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Indices for Query Performance & Constraint Verification
CREATE INDEX IF NOT EXISTS idx_mailboxes_user_id ON mailboxes(user_id);
CREATE INDEX IF NOT EXISTS idx_warmup_schedules_mailbox_id ON warmup_schedules(mailbox_id);
CREATE INDEX IF NOT EXISTS idx_interaction_logs_sender_mailbox_id ON interaction_logs(sender_mailbox_id);
CREATE INDEX IF NOT EXISTS idx_interaction_logs_recipient_mailbox_id ON interaction_logs(recipient_mailbox_id);
