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
    currency: str,
    planned: dict,
    optimized: dict,
    explanation: str,
    tips: list,
) -> dict:
    client = get_client()
    result = client.table("trip_plans").insert({
        "user_id": user_id,
        "destination": destination,
        "duration_days": duration_days,
        "total_budget": total_budget,
        "currency": currency,
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


def update_trip_feedback(trip_id: str, feedback: dict) -> None:
    client = get_client()
    cats = feedback.get("categories_changed")
    update_data = {
        "was_helpful":          feedback.get("q1_helpful"),
        "feedback_q1_reason":   feedback.get("q1_reason"),
        "feedback_q2":          feedback.get("q2_adjusted"),
        "feedback_q2_reason":   feedback.get("q2_reason"),
        "categories_changed":   ", ".join(cats) if cats else None,
        "realism_score":        feedback.get("realism_score"),
        "most_useful_feature":  feedback.get("most_useful_feature"),
        "feature_request":      feedback.get("feature_request"),
    }
    update_data = {k: v for k, v in update_data.items() if v is not None}
    if update_data:
        client.table("trip_plans").update(update_data).eq("id", trip_id).execute()


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
