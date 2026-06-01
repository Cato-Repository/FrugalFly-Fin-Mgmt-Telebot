CATEGORY_EMOJI = {
    "food":       "🍔",
    "transport":  "🚗",
    "hotel":      "🏨",
    "activities": "🎡",
    "other":      "💸",
}

CATEGORIES = ["transport", "hotel", "activities", "other"]

_CURRENCY_CONFIG = {
    "USD": {"symbol": "$",  "decimals": 2},
    "JPY": {"symbol": "¥",  "decimals": 0},
    "SGD": {"symbol": "S$", "decimals": 2},
}


def _fmt(amount: float, currency: str) -> str:
    cfg = _CURRENCY_CONFIG.get(currency, _CURRENCY_CONFIG["USD"])
    if cfg["decimals"] == 0:
        return f"{cfg['symbol']}{int(round(amount)):,}"
    return f"{cfg['symbol']}{amount:,.{cfg['decimals']}f}"


def format_plan_comparison(
    destination: str,
    duration: int,
    total_budget: float,
    planned: dict,
    optimized: dict,
    currency: str = "USD",
) -> str:
    day_label = "day" if duration == 1 else "days"
    lines = [
        f"*✈️ {destination} — {duration} {day_label}*",
        f"*Total Projected: {_fmt(total_budget, currency)}*",
        "",
        "*Your Plan  →  Suggested:*",
    ]

    for cat in CATEGORIES:
        plan_amt = float(planned.get(cat) or 0)
        opt_amt  = float(optimized.get(cat) or plan_amt)
        if plan_amt == 0 and opt_amt == 0:
            continue
        diff = opt_amt - plan_amt

        if diff > 0.5:
            arrow = f"↑ (+{_fmt(diff, currency)})"
        elif diff < -0.5:
            arrow = f"↓ (-{_fmt(abs(diff), currency)})"
        else:
            arrow = "→"

        lines.append(
            f"{CATEGORY_EMOJI[cat]} *{cat.title()}:* {_fmt(plan_amt, currency)}  →  {_fmt(opt_amt, currency)} {arrow}"
        )

    explanation = optimized.get("explanation", "")
    if explanation:
        lines.append(f"\n💡 {explanation}")

    tips = optimized.get("tips") or []
    if tips:
        lines.append("\n📌 *Tips:*")
        for tip in tips:
            lines.append(f"• {tip}")

    return "\n".join(lines)


def format_my_plan(plan: dict) -> str:
    currency = plan.get("currency", "USD")
    planned = {
        "transport":  float(plan.get("planned_transport") or 0),
        "hotel":      float(plan.get("planned_hotel") or 0),
        "activities": float(plan.get("planned_activities") or 0),
        "other":      float(plan.get("planned_other") or 0),
    }
    optimized = {
        "transport":   float(plan.get("optimized_transport") or 0),
        "hotel":       float(plan.get("optimized_hotel") or 0),
        "activities":  float(plan.get("optimized_activities") or 0),
        "other":       float(plan.get("optimized_other") or 0),
        "explanation": plan.get("llm_explanation", ""),
        "tips":        plan.get("llm_tips") or [],
    }
    total = float(plan.get("total_budget") or sum(planned.values()))
    return format_plan_comparison(
        plan["destination"],
        plan["duration_days"],
        total,
        planned,
        optimized,
        currency,
    )
