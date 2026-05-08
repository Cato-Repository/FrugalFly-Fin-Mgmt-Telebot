import json
import os
import re

import anthropic

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def optimize_budget(destination: str, duration_days: int, total_budget: float, planned: dict) -> dict:
    """
    Calls Claude to redistribute the user's planned budget optimally for their destination.
    planned: {"food": 400, "transport": 300, "hotel": 500, "activities": 200, "other": 100}
    Returns: {"food": ..., "transport": ..., "hotel": ..., "activities": ..., "other": ...,
              "explanation": ..., "tips": [...]}
    """
    client = _get_client()
    planned_total = sum(planned.values())

    prompt = f"""You are a travel budget optimizer. A user is planning a trip and wants help allocating their budget realistically before they go.

Trip: {destination} | {duration_days} days | Total budget: ${total_budget:.2f}

Their planned spending:
- Food & Drinks: ${planned.get('food', 0):.2f}
- Transport (flights, taxis, local): ${planned.get('transport', 0):.2f}
- Hotel/Accommodation: ${planned.get('hotel', 0):.2f}
- Activities & Entertainment: ${planned.get('activities', 0):.2f}
- Other expenses: ${planned.get('other', 0):.2f}
- Total planned: ${planned_total:.2f}

Based on real-world average costs in {destination} for {duration_days} days, suggest an optimized budget allocation. Redistribute funds from over-budgeted categories to under-budgeted ones. The 5 optimized amounts MUST sum to exactly ${total_budget:.2f}.

Respond with ONLY valid JSON, no markdown:
{{
  "food": <number>,
  "transport": <number>,
  "hotel": <number>,
  "activities": <number>,
  "other": <number>,
  "explanation": "<2-3 sentences summarizing what you changed and why>",
  "tips": ["<actionable saving tip 1>", "<actionable saving tip 2>", "<actionable saving tip 3>"]
}}"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        raw = match.group(1).strip()

    result = json.loads(raw)

    # Fill missing keys defensively
    for key in ["food", "transport", "hotel", "activities", "other"]:
        if key not in result:
            result[key] = planned.get(key, 0)
    result.setdefault("explanation", "")
    result.setdefault("tips", [])

    # Clamp totals: if LLM drifts, force-adjust "other" to balance
    core_total = sum(result[k] for k in ["food", "transport", "hotel", "activities"])
    if abs((core_total + result["other"]) - total_budget) > 0.5:
        result["other"] = round(max(0.0, total_budget - core_total), 2)

    return result
