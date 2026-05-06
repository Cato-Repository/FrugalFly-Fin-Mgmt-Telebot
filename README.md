# FrugalFly Finance Management Telebot

A Telegram bot MVP for travel finance management. Log expenses, track budgets by category, and capture user behaviour metrics — built to validate the core UX loop before building a full web app.

## Features

- Set a total trip budget
- Split budget by category (food, transport, hotel, activities)
- Log expenses via natural language (e.g. `spent 25 on lunch`)
- View remaining balance per category and overall
- Thank You button to close the loop and record completion time
- Set travel dates per trip

## Tech Stack

- **Bot:** `python-telegram-bot 21.3`
- **Database:** Supabase (Postgres)
- **Deployment:** Railway

## Project Structure

```
├── main.py                  # Entry point
├── bot/
│   ├── handlers/
│   │   ├── start.py         # /start onboarding flow
│   │   ├── budget.py        # /budget command
│   │   ├── expense.py       # Expense logging
│   │   └── callbacks.py     # Thank You button
│   └── utils/
│       ├── db.py            # Supabase queries
│       ├── parser.py        # Expense text parser
│       └── formatters.py    # Bot reply formatting
├── db/
│   └── schema.sql           # Run once in Supabase SQL editor
├── requirements.txt
└── railway.toml
```

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/FrugalFly-Repository/FrugalFly-Fin-Mgmt-Telebot.git
cd FrugalFly-Fin-Mgmt-Telebot
```

### 2. Create a virtual environment

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set up environment variables

Copy `.env.example` to `.env` and fill in your credentials:

```
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key
```

### 4. Set up the database

Run `db/schema.sql` in your Supabase SQL editor.

### 5. Run the bot

```bash
python main.py
```

## Usage

| Command | Description |
|---|---|
| `/start` | Set up your trip budget |
| `/budget` | View current budget overview |
| `spent 25 on lunch` | Log an expense |

## Deployment (Railway)

1. Push to GitHub
2. New Project → Deploy from GitHub repo
3. Add environment variables in Railway dashboard
4. Railway auto-deploys on every push to `main`
