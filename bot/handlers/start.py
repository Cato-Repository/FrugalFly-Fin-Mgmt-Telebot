import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.utils import db

logger = logging.getLogger(__name__)

# Conversation states
ASK_DESTINATION, ASK_DURATION, ASK_BUDGET, ASK_FOOD, ASK_TRANSPORT, ASK_HOTEL, ASK_ACTIVITIES, ASK_OTHER = range(8)

_PROMPTS = {
    "food":       "🍔 Food & Drinks (meals, cafes, groceries)?",
    "transport":  "🚗 Transport (flights, taxis, trains, buses)?",
    "hotel":      "🏨 Hotel & Accommodation?",
    "activities": "🎡 Activities & Entertainment (tours, tickets, experiences)?",
    "other":      "💸 Other expenses (shopping, tips, emergencies)?",
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db.upsert_user(user.id, user.username)
    context.user_data.clear()
    await update.message.reply_text(
        "Welcome to FrugalFly! ✈️\n\n"
        "I'll help you plan your trip budget *before* you go — so every dollar lands in the right place.\n\n"
        "*Where are you headed?* (e.g. Bali, Tokyo, Paris)",
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
    try:
        days = int(text)
        if days < 1 or days > 365:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid number of days (e.g. 7).")
        return ASK_DURATION

    context.user_data["duration_days"] = days
    await update.message.reply_text(
        f"*{days} day{'s' if days != 1 else ''}* — got it! 🗓\n\n*What's your total budget?* (e.g. 1500)",
        parse_mode="Markdown",
    )
    return ASK_BUDGET


async def received_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        amount = float(text.replace(",", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid budget amount (e.g. 1500).")
        return ASK_BUDGET

    context.user_data["total_budget"] = amount
    context.user_data["planned"] = {}

    await update.message.reply_text(
        f"Budget set: *${amount:,.2f}* 💰\n\n"
        f"Now let's plan category by category.\n\n"
        f"How much are you planning for *{_PROMPTS['food']}*",
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
    # Show remaining budget hint before asking for "other"
    text = update.message.text.strip()
    try:
        amount = float(text.replace(",", ""))
        if amount < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid amount (e.g. 200 or 0).")
        return ASK_ACTIVITIES

    context.user_data["planned"]["activities"] = amount
    so_far = sum(context.user_data["planned"].values())
    remaining = context.user_data["total_budget"] - so_far

    await update.message.reply_text(
        f"How much for *{_PROMPTS['other']}*\n\n_(${remaining:,.2f} of your budget unallocated so far)_",
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

    context.user_data["planned"][cat] = amount

    next_cat = {
        ASK_TRANSPORT: "transport",
        ASK_HOTEL: "hotel",
        ASK_ACTIVITIES: "activities",
    }[next_state]

    await update.message.reply_text(
        f"How much for *{_PROMPTS[next_cat]}*",
        parse_mode="Markdown",
    )
    return next_state


async def _generate_and_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from bot.utils.formatters import format_plan_comparison
    from bot.utils.llm import optimize_budget

    destination = context.user_data["destination"]
    duration = context.user_data["duration_days"]
    total_budget = context.user_data["total_budget"]
    planned = context.user_data["planned"]
    planned_total = sum(planned.values())

    warning = ""
    if planned_total > total_budget:
        warning = f"\n\n⚠️ Your planned total (${planned_total:,.2f}) exceeds your budget (${total_budget:,.2f}). I'll optimise within budget."

    thinking_msg = await update.message.reply_text(
        f"🔍 Analysing your plan for *{destination}*...{warning}",
        parse_mode="Markdown",
    )

    try:
        result = await optimize_budget(destination, duration, total_budget, planned)
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

    db.save_trip_plan(
        user_id=db_user["id"],
        destination=destination,
        duration_days=duration,
        total_budget=total_budget,
        planned=planned,
        optimized=optimized,
        explanation=result.get("explanation", ""),
        tips=result.get("tips", []),
    )

    reply = format_plan_comparison(destination, duration, total_budget, planned, result)
    await thinking_msg.edit_text(reply, parse_mode="Markdown")
    await update.message.reply_text(
        "Use /myplan to view this anytime, or /adjust to tweak a category.\nStart fresh with /newtrip."
    )

    context.user_data.clear()
    return ConversationHandler.END
