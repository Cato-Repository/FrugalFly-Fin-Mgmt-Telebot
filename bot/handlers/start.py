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
    ASK_TRANSPORT,
    ASK_HOTEL,
    ASK_ACTIVITIES,
    ASK_OTHER,
    ASK_FEEDBACK_Q1,
    ASK_FEEDBACK_Q1_WHY,
    ASK_FEEDBACK_Q2,
    ASK_FEEDBACK_Q2_WHY,
    ASK_CATEGORIES_CHANGED,
    ASK_REALISM_SCORE,
    ASK_MOST_USEFUL,
    ASK_FEATURE_REQUEST,
) = range(15)

CURRENCY_CONFIG = {
    "USD": {"symbol": "$",  "decimals": 2, "flag": "🇺🇸"},
    "JPY": {"symbol": "¥",  "decimals": 0, "flag": "🇯🇵"},
    "SGD": {"symbol": "S$", "decimals": 2, "flag": "🇸🇬"},
}

_PROMPTS = {
    "transport":  "🚗 Transport (flights, taxis, trains, buses)",
    "hotel":      "🏨 Hotels & Accommodation",
    "activities": "🎡 Activities & Entertainment (tours, tickets, experiences)",
    "other":      "💸 Other Expenses (shopping, tips, emergencies)",
}

_CATEGORY_LABELS = ["Food", "Transport", "Hotel", "Activities", "Other"]

_Q2_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("👍 Yes", callback_data="q2_yes"),
    InlineKeyboardButton("👎 No",  callback_data="q2_no"),
]])

_REALISM_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton(str(i), callback_data=f"score_{i}") for i in range(1, 6)
]])

_SCORE_EMOJI = {1: "😞", 2: "😕", 3: "😐", 4: "😊", 5: "😄"}


def fmt_amount(amount: float, currency: str) -> str:
    cfg = CURRENCY_CONFIG.get(currency, CURRENCY_CONFIG["USD"])
    if cfg["decimals"] == 0:
        return f"{cfg['symbol']}{int(round(amount)):,}"
    return f"{cfg['symbol']}{amount:,.{cfg['decimals']}f}"


def _category_keyboard(selected: list) -> InlineKeyboardMarkup:
    def btn(cat: str) -> InlineKeyboardButton:
        label = f"✅ {cat}" if cat in selected else cat
        return InlineKeyboardButton(label, callback_data=f"cat_{cat}")
    return InlineKeyboardMarkup([
        [btn(c) for c in _CATEGORY_LABELS[:3]],
        [btn(c) for c in _CATEGORY_LABELS[3:]],
        [InlineKeyboardButton("Done ✓", callback_data="cat_done")],
    ])


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
        f"*{destination}* — great choice! 🌏\n\n*How many days is your trip?* (e.g. 7)",
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
    context.user_data["planned"] = {}
    await update.message.reply_text(
        f"*{days} day{'s' if days != 1 else ''}* — got it! 🗓\n\n"
        f"*How much will you be spending on {_PROMPTS['transport']}?*",
        parse_mode="Markdown",
    )
    return ASK_TRANSPORT


async def received_transport(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _receive_category(update, context, "transport", ASK_TRANSPORT, ASK_HOTEL)


async def received_hotel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _receive_category(update, context, "hotel", ASK_HOTEL, ASK_ACTIVITIES)


async def received_activities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _receive_category(update, context, "activities", ASK_ACTIVITIES, ASK_OTHER)


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
            "After using FrugalFly, did you adjust any category for your budget planning?",
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
        "After using FrugalFly, did you adjust any category for your budget planning?",
        reply_markup=_Q2_KEYBOARD,
    )
    return ASK_FEEDBACK_Q2


async def received_feedback_q2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    adjusted = (query.data == "q2_yes")
    context.user_data.setdefault("feedback", {})["q2_adjusted"] = adjusted

    if adjusted:
        await query.edit_message_text("Great! 🎉")
        await query.message.reply_text(
            "*Which categories did you change?*\n_(Select all that apply, then tap Done ✓)_",
            parse_mode="Markdown",
            reply_markup=_category_keyboard([]),
        )
        return ASK_CATEGORIES_CHANGED
    else:
        await query.edit_message_text(
            "We're sorry to hear that 😔\n\n"
            "Please let us know why so that we can continue improving FrugalFly:"
        )
        return ASK_FEEDBACK_Q2_WHY


async def received_feedback_q2_why(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.setdefault("feedback", {})["q2_reason"] = update.message.text.strip()
    await update.message.reply_text(
        "Thanks for letting us know! 🙏\n\n"
        "*How realistic does your budget feel now?*\n_(1 = not realistic at all, 5 = very realistic)_",
        parse_mode="Markdown",
        reply_markup=_REALISM_KEYBOARD,
    )
    return ASK_REALISM_SCORE


async def received_categories_changed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    feedback = context.user_data.setdefault("feedback", {})
    selected = list(feedback.get("categories_changed", []))

    if query.data == "cat_done":
        feedback["categories_changed"] = selected
        changed_str = ", ".join(selected) if selected else "none"
        await query.edit_message_text(
            f"Got it — you changed: *{changed_str}*", parse_mode="Markdown"
        )
        await query.message.reply_text(
            "*How realistic does your budget feel now?*\n_(1 = not realistic at all, 5 = very realistic)_",
            parse_mode="Markdown",
            reply_markup=_REALISM_KEYBOARD,
        )
        return ASK_REALISM_SCORE
    else:
        cat = query.data.replace("cat_", "")
        if cat in selected:
            selected.remove(cat)
        else:
            selected.append(cat)
        feedback["categories_changed"] = selected
        await query.edit_message_reply_markup(reply_markup=_category_keyboard(selected))
        return ASK_CATEGORIES_CHANGED


async def received_realism_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    score = int(query.data.replace("score_", ""))
    context.user_data.setdefault("feedback", {})["realism_score"] = score
    emoji = _SCORE_EMOJI[score]
    await query.edit_message_text(
        f"Budget realism score: *{score}/5* {emoji}", parse_mode="Markdown"
    )
    await query.message.reply_text(
        "*Which feature do you think was most useful?*\n_(Type your answer)_",
        parse_mode="Markdown",
    )
    return ASK_MOST_USEFUL


async def received_most_useful(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.setdefault("feedback", {})["most_useful_feature"] = update.message.text.strip()
    await update.message.reply_text(
        "Please also let us know what other features you would like to see that will "
        "enable you to more effectively budget your trips! 😊\n"
        "_(Type your suggestions, or 'skip' to finish)_",
        parse_mode="Markdown",
    )
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
    try:
        amount = float(text.replace(",", ""))
        if amount < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid amount (e.g. 300 or 0).")
        return self_state
    context.user_data.setdefault("planned", {})[cat] = amount
    next_cat = {
        ASK_HOTEL:      "hotel",
        ASK_ACTIVITIES: "activities",
        ASK_OTHER:      "other",
    }[next_state]
    await update.message.reply_text(
        f"*How much will you be spending on {_PROMPTS[next_cat]}?*",
        parse_mode="Markdown",
    )
    return next_state


async def _generate_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from bot.utils.formatters import format_plan_comparison
    from bot.utils.llm import optimize_budget

    destination  = context.user_data["destination"]
    duration     = context.user_data["duration_days"]
    currency     = context.user_data.get("currency", "USD")
    planned      = context.user_data["planned"]
    planned_total = sum(planned.values())

    thinking_msg = await update.message.reply_text(
        f"🔍 Analysing your plan for *{destination}*...",
        parse_mode="Markdown",
    )

    try:
        result = await optimize_budget(destination, duration, planned, currency)
    except Exception:
        logger.exception("optimize_budget failed for destination=%s", destination)
        await thinking_msg.edit_text(
            "Sorry, I couldn't generate recommendations right now. Please try again with /newtrip."
        )
        context.user_data.clear()
        return ConversationHandler.END

    user = update.effective_user
    db_user = db.get_user(user.id)
    optimized = {k: result[k] for k in ["transport", "hotel", "activities", "other"]}

    trip = db.save_trip_plan(
        user_id=db_user["id"],
        destination=destination,
        duration_days=duration,
        total_budget=planned_total,
        currency=currency,
        planned=planned,
        optimized=optimized,
        explanation=result.get("explanation", ""),
        tips=result.get("tips", []),
    )
    context.user_data["trip_id"] = trip["id"]

    reply = format_plan_comparison(destination, duration, planned_total, planned, result, currency)
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
