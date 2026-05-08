-- Run this once in your Supabase SQL editor

CREATE TABLE IF NOT EXISTS users (
  id                SERIAL PRIMARY KEY,
  telegram_user_id  BIGINT UNIQUE NOT NULL,
  username          TEXT,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Pre-Travel Tracker: stores the user's planned and LLM-optimized budgets
CREATE TABLE IF NOT EXISTS trip_plans (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  destination    TEXT NOT NULL,
  duration_days  INT NOT NULL,
  total_budget   NUMERIC(10,2) NOT NULL,
  currency       TEXT DEFAULT 'SGD',

  -- User's planned amounts
  planned_food        NUMERIC(10,2) DEFAULT 0,
  planned_transport   NUMERIC(10,2) DEFAULT 0,
  planned_hotel       NUMERIC(10,2) DEFAULT 0,
  planned_activities  NUMERIC(10,2) DEFAULT 0,
  planned_other       NUMERIC(10,2) DEFAULT 0,

  -- LLM optimized amounts
  optimized_food        NUMERIC(10,2),
  optimized_transport   NUMERIC(10,2),
  optimized_hotel       NUMERIC(10,2),
  optimized_activities  NUMERIC(10,2),
  optimized_other       NUMERIC(10,2),

  -- LLM output
  llm_explanation  TEXT,
  llm_tips         JSONB DEFAULT '[]',

  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS trip_plans_user_id_idx ON trip_plans(user_id);
