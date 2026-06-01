# Changelog

All notable changes to FrugalFly are documented here.
Format: `major.minor.patch`
- **Major** — breaking changes or full rewrites
- **Minor** — new features
- **Patch** — bug fixes, small improvements

---

## [0.5.1] - 2026-06-01
### Fixed
- Removed `delete_webhook()` from lifespan shutdown — was causing a race condition on every Render redeploy where the old process wiped the webhook after the new process had already registered it, leaving the bot unresponsive until manually re-registered

---

## [0.5.0] - 2026-06-01
### Changed
- **Full user flow redesign** to match updated spec:
  - Removed total budget question — total is now computed as the sum of all category inputs
  - Removed food as a separate planning question
  - Flow is now: currency → destination → duration → transport → hotel → activities → other → recommendations
- **Expanded feedback flow** (6 steps):
  - Q1: "Was this useful in seeing your total costs?" (Yes/No)
    - If No → "Please tell us why"
  - Q2: "Did you adjust any category after using FrugalFly?" (Yes/No)
    - If No → "Please tell us why"
    - If Yes → multi-select category buttons (Food / Transport / Hotel / Activities / Other + Done ✓)
  - Realism score 1–5 via inline buttons
  - "Which feature was most useful?" (open-ended text)
  - "What other features would you like?" (open-ended text / skip)
- LLM prompt updated: 4 categories only, focuses on assessing realism of the plan
- `format_plan_comparison` header now shows "Total Projected" instead of "Budget"
- Food hidden from output unless non-zero (e.g. manually adjusted via `/adjust food X`)

### Added
- 3 new DB columns: `categories_changed TEXT`, `realism_score INTEGER`, `most_useful_feature TEXT`
- Multi-select inline keyboard for category changed selection (toggle with checkmarks)
- Realism score inline keyboard (1–5)

---

## [0.4.2] - 2026-06-01
### Fixed
- Health endpoint now handles `HEAD /` requests (returns 200) — Render's internal health checker uses HEAD, which was returning 405 and causing Render to SIGTERM the process ~7 seconds after startup, creating a restart loop
- Suppressed false-alarm `PTBUserWarning` about `per_message=False` in `ConversationHandler`

---

## [0.4.1] - 2026-06-01
### Added
- `load_test.py` — concurrent load test script that simulates 50 users going through the full conversation flow simultaneously to stress test webhook handling, Supabase writes, and concurrent LLM calls

---

## [0.4.0] - 2026-06-01
### Changed
- Switched from polling to **webhook mode** using FastAPI — Render now receives inbound HTTP traffic, preventing free-tier spin-down
- `main.py` rebuilt around FastAPI with a `lifespan` context manager that registers/deregisters the Telegram webhook on startup/shutdown
- Bot auto-registers its webhook URL with Telegram on deploy via `bot.set_webhook()`
- Falls back to polling automatically when `WEBHOOK_URL` env var is not set (local development)

### Added
- `GET /` health check endpoint — returns `{"status": "ok"}`, used by Render and UptimeRobot to keep the service alive
- `POST /webhook` endpoint — receives Telegram updates pushed by Telegram
- `fastapi` and `uvicorn[standard]` added to `requirements.txt`

### Fixed
- `/adjust` command was still calling `optimize_budget` without `await` — fixed to use async properly

---

## [0.3.0] - 2026-06-01
### Changed
- Expanded post-recommendation feedback from a single yes/no question into a **two-question branching flow**:
  - Q1: "Did you think this budget planner was useful in helping you see the total costs of your trip?" (Yes/No)
    - If No → "Please let us know why..." (free text)
  - Q2: "Was FrugalFly useful in enabling you to keep within your travel budget?" (Yes/No)
    - If No → "Please let us know why..." (free text)
  - Final: "What other features would you like to see?" (free text / skip)
- Feedback responses saved to `trip_plans` table (`was_helpful`, `feedback_q1_reason`, `feedback_q2`, `feedback_q2_reason`, `feature_request`)

### Added
- 3 new conversation states: `ASK_FEEDBACK_Q1_WHY`, `ASK_FEEDBACK_Q2`, `ASK_FEEDBACK_Q2_WHY`
- 3 new DB columns: `feedback_q1_reason TEXT`, `feedback_q2 BOOLEAN`, `feedback_q2_reason TEXT`

---

## [0.2.0] - 2026-06-01
### Changed
- **Full conversation flow redesign**:
  - Step 1 is now currency selection (USD / JPY / SGD) via inline keyboard buttons
  - Each category question now shows *(Budget remaining: X)* after every entry
  - Rephrased category questions to "How much will you be spending on..."
  - Duration input now accepts "7 days" format, not just "7"
- Trips are no longer overwritten — each `/newtrip` creates a new record, all history is preserved
- `format_plan_comparison` and `format_my_plan` are now currency-aware (¥ shows no decimals, S$ prefix, etc.)
- LLM prompt updated to include currency context and proper symbol formatting

### Added
- `currency` column now populated in `trip_plans` on save
- `was_helpful` and `feature_request` columns added to `trip_plans` for feedback
- Post-recommendation feedback: "Was this helpful?" inline Yes/No buttons
- `update_trip_feedback()` in `db.py` to save feedback after conversation ends
- `trip_id` stored in `user_data` after save so feedback can be linked back

### Fixed
- `currency` column in `trip_plans` was defined in schema but never populated

---

## [0.1.2] - 2026-05-31
### Fixed
- Switched Anthropic client from `anthropic.Anthropic` (sync) to `anthropic.AsyncAnthropic` — the sync client was blocking the asyncio event loop on every LLM call, causing instability on Render
- `optimize_budget` made `async` and awaited at all call sites (`start.py`, `plan.py`)
- Added `force=True` to `logging.basicConfig` so logs are not silently suppressed when libraries configure the root logger before `main()` runs

---

## [0.1.1] - 2026-05-24
### Fixed
- `ANTHROPIC_API_KEY` was missing from `.env` — bot would complete the entire onboarding flow then fail silently at the LLM step with a generic error message
- Added `logger.exception()` to the `optimize_budget` try/except block so the real error (missing key, bad JSON, network failure) is logged instead of being swallowed

---

## [0.1.0] - 2026-05-24
### Added
- Initial Pre-Travel Tracker (PTT) — rebuilt MVP
- Conversational onboarding: destination → duration → total budget → 5 spending categories (food, transport, hotel, activities, other)
- LLM budget optimisation via Claude Haiku — redistributes user's planned budget based on real-world destination costs
- Budget comparison output: planned vs suggested per category with arrows and diff
- Saving tips and explanation from LLM
- Supabase integration: `users` and `trip_plans` tables
- `/myplan` — view latest trip plan
- `/adjust <category> <amount>` — tweak a category and re-optimise
- `/help` — show all commands
- `/newtrip` — restart onboarding

---

## [0.0.2] - pre-PTT
### Added
- `/total`, `/end`, `/editbudget`, `/help` commands
- Uncategorised expense flow
- Unknown category logging

## [0.0.1] - pre-PTT
### Added
- Initial commit and project scaffolding
