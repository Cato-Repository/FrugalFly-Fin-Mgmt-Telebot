-- Run this once in your Supabase SQL editor

CREATE TABLE IF NOT EXISTS users (
  id                SERIAL PRIMARY KEY,
  telegram_user_id  BIGINT UNIQUE NOT NULL,
  username          TEXT,
  home_timezone     TEXT,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS budgets (
  id              SERIAL PRIMARY KEY,
  user_id         INT REFERENCES users(id) ON DELETE CASCADE,
  category        TEXT NOT NULL,
  amount          NUMERIC NOT NULL,
  currency        TEXT DEFAULT 'USD',
  trip_start_date DATE,
  trip_end_date   DATE,
  ended_at        TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS expense_logs (
  id           SERIAL PRIMARY KEY,
  user_id      INT REFERENCES users(id) ON DELETE CASCADE,
  budget_id    INT REFERENCES budgets(id) ON DELETE SET NULL,
  amount       NUMERIC NOT NULL,
  category     TEXT,
  note         TEXT,
  logged_at    TIMESTAMPTZ DEFAULT NOW(),
  thank_you_at TIMESTAMPTZ
);

-- Tracks words users type that don't match any known category (analytics)
CREATE TABLE IF NOT EXISTS unknown_category_logs (
  id        SERIAL PRIMARY KEY,
  user_id   INT REFERENCES users(id) ON DELETE CASCADE,
  raw_text  TEXT,
  logged_at TIMESTAMPTZ DEFAULT NOW()
);

-- Session duration view
CREATE OR REPLACE VIEW expense_sessions AS
SELECT
  id,
  user_id,
  amount,
  category,
  note,
  logged_at,
  thank_you_at,
  EXTRACT(EPOCH FROM (thank_you_at - logged_at)) * 1000 AS session_duration_ms
FROM expense_logs
WHERE thank_you_at IS NOT NULL;


-- =============================================
-- MIGRATION: run these if tables already exist
-- =============================================
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS ended_at TIMESTAMPTZ;
