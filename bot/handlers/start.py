import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.utils import db

logger = logging.getLogger(__name__)

(
    ASK_CURRENCY,
    ASK_DESTINATION,
    ASK_DURATION,
    ASK_BUDGET,
    ASK_FOOD,
    ASK_TRANSPORT,
    ASK_HOTEL,
    ASK_ACTIVITIES,
    ASK_OTHER,
    ASK_FEEDBACK_Q1,
    ASK_FEEDBACK_Q1_WHY,
    ASK_FEEDBACK_Q2,
    ASK_FEEDBACK_Q2_WHY,
    ASK_FEATURE_REQUEST,
) = range(14)

CURRENCY_CONFIG = {
    "USD": {"symbol": "$",  "decimals": 2, "flag": "🇺🇸"},
    "JPY": {"symbol": "¥",  "decimals": 0, "flag": "🇯🇵"},
    "SGD": {"symbol": "S$", "decimals": 2, "flag": "🇸🇬"},
}

_PROMPTS = {
    "food":       "🍔 Food & Drinks (meals, cafes, groceries)",
    "transport":  "🚗 Transport (flights, taxis, trains, buses)",
    "hotel":      "🏨 Hotel & Accommodation",
    "activities": "🎡 Activities & Entertainment (tours, tickets, experiences)",
    "other":      "💸 Other expenses (shopping, tips, emergencies)",
}

_Q2_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("👍 Yes", callback_data="q2_yes"),
    InlineKeyboardButton("👎 No",  callback_data="q2_no"),
]])

_FEATURE_REQUEST_TEXT = (
    "Please also let us know what other features you would like to see that will "
    "enable you to more effectively budget your trips! 😊\n"
    "_(Type your suggestions, or 'skip' to finish)_"
)


def fmt_amount(amount: float, currency: str) -> str:
    cfg = CURRENCY_CONFIG.get(currency, CURRENCY_CONFIG["USD"])
    if cfg["decimals"] == 0:
        return f"{cfg['symbol']}{int(round(amount)):,}"
    return f"{cfg['symbol']}{amount:,.{cfg['decimals']}f}"


def _remaining(context: ContextTypes.DEFAULT_TYPE) -> float:
    total = context.user_data.get("total_budget", 0.0)
    spent = sum(context.user_data.get("planned", {}).values())
    return total - spent


# ---------------------------------------------------------------------------
# Onboarding flow
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db.upsert_user(user.id, user.username)
    context.user_data.clear()

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🇺🇸 USD", callback_data="USD"),
        InlineKeyboardButton("🇯🇵 JPY", callback_data="JPY"),
        InlineKeyboardButton("🇸🇬 SGD", callback_data="SGD"),
    ]])
    await update.message.reply_text(
        "Welcome to FrugalFly! ✈️\n\n"
        "I'll help you plan your trip budget *before* you go — so every dollar lands in the right place.\n\n"
        "*Select your currency:*",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return ASK_CURRENCY


async def received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    currency = query.data
    context.user_data["currency"] = currency
    cfg = CURRENCY_CONFIG[currency]
    await query.edit_message_text(
        f"Currency set to *{currency}* {cfg['flag']}\n\n"
        f"*Where are you headed to?* (e.g. Bali, Tokyo, Paris)",
        parse_mode="Markdown",
    )
    return ASK_DESTINATION


async def received_destination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    destination = update.message.text.strip()
    if len(destination) < 2:
        await update.message.reply_text("Please enter a valid destination.")
        return ASK_DESTINATION
    context.user_data["destination"] = destination
    await update.message.reply_text(
        f"*{destination}* — great choice! 🌏\n\n*How long is your trip?* (e.g. 7)",
        parse_mode="Markdown",
    )
    return ASK_DURATION


async def received_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    match = re.search(r"\d+", text)
    if not match:
        await update.message.reply_text("Please enter a valid number of days (e.g. 7).")
        return ASK_DURATION
    days = int(match.group())
    if days < 1 or days > 365:
        await update.message.reply_text("Please enter a number of days between 1 and 365.")
        return ASK_DURATION
    context.user_data["duration_days"] = days
    await update.message.reply_text(
        f"*{days} day{'s' if days != 1 else ''}* — got it! 🗓\n\n*What is your total budget?*",
        parse_mode="Markdown",
    )
    return ASK_BUDGET


async def received_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    currency = context.user_data.get("currency", "USD")
    symbol = CURRENCY_CONFIG[currency]["symbol"]
    try:
        amount = float(text.replace(",", "").replace(symbol, "").strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid budget amount (e.g. 1500).")
        return ASK_BUDGET
    context.user_data["total_budget"] = amount
    context.user_data["planned"] = {}
    await update.message.reply_text(
        f"Budget set: *{fmt_amount(amount, currency)}* 💰\n\n"
        f"Now let's plan category by category.\n\n"
        f"*How much will you be spending on {_PROMPTS['food']}?*\n"
        f"_(Budget remaining: {fmt_amount(amount, currency)})_",
        parse_mode="Markdown",
    )
    return ASK_FOOD


async def received_food(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _receive_category(update, context, "food", ASK_FOOD, ASK_TRANSPORT)


async def received_transport(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _receive_category(update, context, "transport", ASK_TRANSPORT, ASK_HOTEL)


async def received_hotel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _receive_category(update, context, "hotel", ASK_HOTEL, ASK_ACTIVITIES)


async def received_activities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    currency = context.user_data.get("currency", "USD")
    try:
        amount = float(text.replace(",", ""))
        if amount < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid amount (e.g. 200 or 0).")
        return ASK_ACTIVITIES
    context.user_data["planned"]["activities"] = amount
    remaining = _remaining(context)
    await update.message.reply_text(
        f"*How much will you be spending on {_PROMPTS['other']}?*\n"
        f"_(Budget remaining: {fmt_amount(remaining, currency)})_",
        parse_mode="Markdown",
    )
    return ASK_OTHER


async def received_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        amount = float(text.replace(",", ""))
        if amount < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid amount (e.g. 100 or 0).")
        return ASK_OTHER
    context.user_data["planned"]["other"] = amount
    return await _generate_and_save(update, context)


# ---------------------------------------------------------------------------
# Feedback flow
# ---------------------------------------------------------------------------

async def received_feedback_q1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    helpful = (query.data == "q1_yes")
    context.user_data.setdefault("feedback", {})["q1_helpful"] = helpful

    if helpful:
        await query.edit_message_text("Glad to hear that! 😊")
        await query.message.reply_text(
            "Was FrugalFly useful in enabling you to keep within your travel budget?",
            reply_markup=_Q2_KEYBOARD,
        )
        return ASK_FEEDBACK_Q2
    else:
        await query.edit_message_text(
            "We're sorry to hear that 😔\n\n"
            "Please let us know why so that we can continue improving this software:"
        )
        return ASK_FEEDBACK_Q1_WHY


async def received_feedback_q1_why(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.setdefault("feedback", {})["q1_reason"] = update.message.text.strip()
    await update.message.reply_text(
        "Thanks for letting us know! 🙏\n\n"
        "Was FrugalFly useful in enabling you to keep within your travel budget?",
        reply_markup=_Q2_KEYBOARD,
    )
    return ASK_FEEDBACK_Q2


async def received_feedback_q2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    helpful = (query.data == "q2_yes")
    context.user_data.setdefault("feedback", {})["q2_helpful"] = helpful

    if helpful:
        await query.edit_message_text("Awesome! 🎉")
        await query.message.reply_text(_FEATURE_REQUEST_TEXT, parse_mode="Markdown")
        return ASK_FEATURE_REQUEST
    else:
        await query.edit_message_text(
            "We're sorry to hear that 😔\n\n"
            "Please let us know why so that we can continue improving FrugalFly:"
        )
        return ASK_FEEDBACK_Q2_WHY


async def received_feedback_q2_why(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.setdefault("feedback", {})["q2_reason"] = update.message.text.strip()
    await update.message.reply_text(_FEATURE_REQUEST_TEXT, parse_mode="Markdown")
    return ASK_FEATURE_REQUEST


async def received_feature_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    feedback = context.user_data.get("feedback", {})
    if text.lower() != "skip":
        feedback["feature_request"] = text

    trip_id = context.user_data.get("trip_id")
    if trip_id and feedback:
        db.update_trip_feedback(trip_id, feedback)

    await update.message.reply_text(
        "Thank you so much for your feedback — it helps us improve! 🚀\n\n"
        "Use /myplan to view your plan anytime, or /adjust to tweak a category.\n"
        "Start fresh with /newtrip."
    )
    context.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _receive_category(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    cat: str,
    self_state: int,
    next_state: int,
) -> int:
    text = update.message.text.strip()
    currency = context.user_data.get("currency", "USD")
    try:
        amount = float(text.replace(",", ""))
        if amount < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid amount (e.g. 300 or 0).")
        return self_state
    context.user_data["planned"][cat] = amount
    remaining = _remaining(context)
    next_cat = {
        ASK_TRANSPORT:  "transport",
        ASK_HOTEL:      "hotel",
        ASK_ACTIVITIES: "activities",
    }[next_state]
    await update.message.reply_text(
        f"*How much will you be spending on {_PROMPTS[next_cat]}?*\n"
        f"_(Budget remaining: {fmt_amount(remaining, currency)})_",
        parse_mode="Markdown",
    )
    return next_state


async def _generate_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from bot.utils.formatters import format_plan_comparison
    from bot.utils.llm import optimize_budget

    destination  = context.user_data["destination"]
    duration     = context.user_data["duration_days"]
    total_budget = context.user_data["total_budget"]
    currency     = context.user_data.get("currency", "USD")
    planned      = context.user_data["planned"]
    planned_total = sum(planned.values())

    warning = ""
    if planned_total > total_budget:
        warning = (
            f"\n\n⚠️ Your planned total ({fmt_amount(planned_total, currency)}) exceeds "
            f"your budget ({fmt_amount(total_budget, currency)}). I'll optimise within budget."
        )

    thinking_msg = await update.message.reply_text(
        f"🔍 Analysing your plan for *{destination}*...{warning}",
        parse_mode="Markdown",
    )

    try:
        result = await optimize_budget(destination, duration, total_budget, planned, currency)
    except Exception:
        logger.exception("optimize_budget failed for destination=%s", destination)
        await thinking_msg.edit_text(
            "Sorry, I couldn't generate recommendations right now. Please try again with /newtrip."
        )
        context.user_data.clear()
        return ConversationHandler.END

    user = update.effective_user
    db_user = db.get_user(user.id)
    optimized = {k: result[k] for k in ["food", "transport", "hotel", "activities", "other"]}

    trip = db.save_trip_plan(
        user_id=db_user["id"],
        destination=destination,
        duration_days=duration,
        total_budget=total_budget,
        currency=currency,
        planned=planned,
        optimized=optimized,
        explanation=result.get("explanation", ""),
        tips=result.get("tips", []),
    )
    context.user_data["trip_id"] = trip["id"]

    reply = format_plan_comparison(destination, duration, total_budget, planned, result, currency)
    await thinking_msg.edit_text(reply, parse_mode="Markdown")

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("👍 Yes", callback_data="q1_yes"),
        InlineKeyboardButton("👎 No",  callback_data="q1_no"),
    ]])
    await update.message.reply_text(
        "Did you think this budget planner was useful in helping you see the total costs of your trip?",
        reply_markup=keyboard,
    )
    return ASK_FEEDBACK_Q1
