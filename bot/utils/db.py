import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


def upsert_user(telegram_user_id: int, username: str | None) -> dict:
    db = get_client()
    result = (
        db.table("users")
        .upsert(
            {"telegram_user_id": telegram_user_id, "username": username},
            on_conflict="telegram_user_id",
        )
        .execute()
    )
    return result.data[0]


def get_user(telegram_user_id: int) -> dict | None:
    db = get_client()
    result = (
        db.table("users")
        .select("*")
        .eq("telegram_user_id", telegram_user_id)
        .execute()
    )
    return result.data[0] if result.data else None


def set_budgets(user_id: int, categories: dict[str, float], trip_start: str | None, trip_end: str | None) -> None:
    db = get_client()
    # Delete existing budgets for the user before reinserting
    db.table("budgets").delete().eq("user_id", user_id).execute()
    rows = [
        {
            "user_id": user_id,
            "category": cat,
            "amount": amt,
            "trip_start_date": trip_start,
            "trip_end_date": trip_end,
        }
        for cat, amt in categories.items()
    ]
    db.table("budgets").insert(rows).execute()


def get_budgets(user_id: int) -> list[dict]:
    db = get_client()
    result = db.table("budgets").select("*").eq("user_id", user_id).execute()
    return result.data


def log_expense(user_id: int, amount: float, category: str, note: str) -> dict:
    db = get_client()
    budgets = get_budgets(user_id)
    budget_id = None
    for b in budgets:
        if b["category"] == category:
            budget_id = b["id"]
            break
    result = (
        db.table("expense_logs")
        .insert(
            {
                "user_id": user_id,
                "budget_id": budget_id,
                "amount": amount,
                "category": category,
                "note": note,
            }
        )
        .execute()
    )
    return result.data[0]


def record_thank_you(log_id: int) -> None:
    from datetime import datetime, timezone
    db = get_client()
    db.table("expense_logs").update({"thank_you_at": datetime.now(timezone.utc).isoformat()}).eq("id", log_id).execute()


def get_spent_by_category(user_id: int) -> dict[str, float]:
    db = get_client()
    result = db.table("expense_logs").select("category, amount").eq("user_id", user_id).execute()
    totals: dict[str, float] = {}
    for row in result.data:
        cat = row["category"] or "uncategorised"
        totals[cat] = totals.get(cat, 0.0) + float(row["amount"])
    return totals
