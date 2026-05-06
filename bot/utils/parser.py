import re

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "food": ["food", "lunch", "dinner", "breakfast", "eat", "meal", "cafe", "coffee", "snack", "restaurant", "drink"],
    "transport": ["transport", "taxi", "grab", "uber", "bus", "train", "mrt", "flight", "ferry", "toll", "parking"],
    "hotel": ["hotel", "hostel", "airbnb", "accommodation", "lodge", "room", "stay"],
    "activities": ["activity", "activities", "tour", "ticket", "entrance", "museum", "show", "event", "excursion"],
}


def parse_expense(text: str) -> dict | None:
    """
    Parses messages like:
      "spent 25 on lunch"
      "25 for taxi"
      "food 30"
    Returns {"amount": float, "category": str, "note": str} or None.
    """
    text = text.strip().lower()

    # Extract the first number in the message
    match = re.search(r"\d+(\.\d+)?", text)
    if not match:
        return None

    amount = float(match.group())
    category = _detect_category(text)

    return {"amount": amount, "category": category, "note": text}


def _detect_category(text: str) -> str:
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return "uncategorised"


def parse_category_budgets(text: str) -> dict[str, float] | None:
    """
    Parses "food 300, transport 200, hotel 400, activities 100"
    Returns {"food": 300, "transport": 200, ...} or None.
    """
    pattern = re.findall(r"(\w+)\s+(\d+(?:\.\d+)?)", text.lower())
    if not pattern:
        return None
    return {cat: float(amt) for cat, amt in pattern}
