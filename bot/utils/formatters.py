CATEGORY_EMOJI = {
    "food": "🍔",
    "transport": "🚗",
    "hotel": "🏨",
    "activities": "🎡",
    "uncategorised": "💸",
    "total": "💰",
}


def format_budget_summary(budgets: list[dict]) -> str:
    lines = ["*Your trip budget:*"]
    for b in budgets:
        emoji = CATEGORY_EMOJI.get(b["category"], "💸")
        lines.append(f"{emoji} {b['category'].title()}: ${b['amount']:,.2f}")
    return "\n".join(lines)


def format_expense_reply(category: str, amount: float, budgets: list[dict], spent: dict[str, float]) -> str:
    emoji = CATEGORY_EMOJI.get(category, "💸")

    total_budget = sum(float(b["amount"]) for b in budgets)
    total_spent = sum(spent.values())
    total_remaining = total_budget - total_spent

    lines = [f"{emoji} *{category.title()}:* ${amount:,.2f} logged"]

    # Category-level remaining
    cat_budget = next((float(b["amount"]) for b in budgets if b["category"] == category), None)
    if cat_budget is not None:
        cat_spent = spent.get(category, 0.0)
        cat_remaining = cat_budget - cat_spent
        lines.append(f"Remaining: ${cat_remaining:,.2f} / ${cat_budget:,.2f} ({category})")

    lines.append(f"Total left: ${total_remaining:,.2f} / ${total_budget:,.2f}")
    return "\n".join(lines)
