import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import Client, create_client

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
    client = get_client()
    result = (
        client.table("users")
        .upsert(
            {"telegram_user_id": telegram_user_id, "username": username},
            on_conflict="telegram_user_id",
        )
        .execute()
    )
    return result.data[0]


def get_user(telegram_user_id: int) -> dict | None:
    client = get_client()
    result = (
        client.table("users")
        .select("*")
        .eq("telegram_user_id", telegram_user_id)
        .execute()
    )
    return result.data[0] if result.data else None


def save_trip_plan(
    user_id: int,
    destination: str,
    duration_days: int,
    total_budget: float,
    planned: dict,
    optimized: dict,
    explanation: str,
    tips: list,
) -> dict:
    client = get_client()
    client.table("trip_plans").delete().eq("user_id", user_id).execute()
    result = client.table("trip_plans").insert({
        "user_id": user_id,
        "destination": destination,
        "duration_days": duration_days,
        "total_budget": total_budget,
        "planned_food": planned.get("food", 0),
        "planned_transport": planned.get("transport", 0),
        "planned_hotel": planned.get("hotel", 0),
        "planned_activities": planned.get("activities", 0),
        "planned_other": planned.get("other", 0),
        "optimized_food": optimized.get("food"),
        "optimized_transport": optimized.get("transport"),
        "optimized_hotel": optimized.get("hotel"),
        "optimized_activities": optimized.get("activities"),
        "optimized_other": optimized.get("other"),
        "llm_explanation": explanation,
        "llm_tips": json.dumps(tips),
    }).execute()
    return result.data[0]


def get_trip_plan(user_id: int) -> dict | None:
    client = get_client()
    result = (
        client.table("trip_plans")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    row = result.data[0]
    if isinstance(row.get("llm_tips"), str):
        row["llm_tips"] = json.loads(row["llm_tips"])
    return row


def update_trip_plan_optimized(
    user_id: int,
    planned: dict,
    optimized: dict,
    explanation: str,
    tips: list,
) -> None:
    client = get_client()
    client.table("trip_plans").update({
        "planned_food": planned.get("food", 0),
        "planned_transport": planned.get("transport", 0),
        "planned_hotel": planned.get("hotel", 0),
        "planned_activities": planned.get("activities", 0),
        "planned_other": planned.get("other", 0),
        "optimized_food": optimized.get("food"),
        "optimized_transport": optimized.get("transport"),
        "optimized_hotel": optimized.get("hotel"),
        "optimized_activities": optimized.get("activities"),
        "optimized_other": optimized.get("other"),
        "llm_explanation": explanation,
        "llm_tips": json.dumps(tips),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("user_id", user_id).execute()
