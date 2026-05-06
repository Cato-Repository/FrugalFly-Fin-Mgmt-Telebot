from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.utils import db

# Conversation states
ASK_BUDGET, ASK_SPLIT, ASK_CATEGORIES, ASK_DATES = range(4)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db.upsert_user(user.id, user.username)
    await update.message.reply_text(
        "Welcome to FrugalFly! ✈️\n\nLet's set up your trip budget.\nWhat's your total budget? (e.g. *1000*)",
        parse_mode="Markdown",
    )
    return ASK_BUDGET


async def received_total_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        amount = float(text.replace(",", ""))
    except ValueError:
        await update.message.reply_text("Please enter a number, e.g. *1000*", parse_mode="Markdown")
        return ASK_BUDGET

    context.user_data["total_budget"] = amount

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [
        [
            InlineKeyboardButton("Yes, split by category", callback_data="split_yes"),
            InlineKeyboardButton("No, keep it simple", callback_data="split_no"),
        ]
    ]
    await update.message.reply_text(
        f"Got it! Your total budget is *${amount:,.2f}*.\nWant to split by category?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return ASK_SPLIT


async def split_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "split_no":
        total = context.user_data["total_budget"]
        context.user_data["categories"] = {"total": total}
        await query.edit_message_text(
            "When are you travelling? (e.g. *15 Jun - 25 Jun* or skip with /skip)",
            parse_mode="Markdown",
        )
        return ASK_DATES

    await query.edit_message_text(
        "Enter your category budgets like this:\n`food 300, transport 200, hotel 400, activities 100`",
        parse_mode="Markdown",
    )
    return ASK_CATEGORIES


async def received_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from bot.utils.parser import parse_category_budgets
    from bot.utils.formatters import format_budget_summary

    parsed = parse_category_budgets(update.message.text)
    if not parsed:
        await update.message.reply_text(
            "Couldn't parse that. Try: `food 300, transport 200, hotel 400, activities 100`",
            parse_mode="Markdown",
        )
        return ASK_CATEGORIES

    context.user_data["categories"] = parsed
    summary = format_budget_summary([{"category": k, "amount": v} for k, v in parsed.items()])
    await update.message.reply_text(
        f"{summary}\n\nWhen are you travelling? (e.g. *15 Jun - 25 Jun* or /skip)",
        parse_mode="Markdown",
    )
    return ASK_DATES


async def received_dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _save_and_finish(update, context, date_text=update.message.text.strip())


async def skip_dates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _save_and_finish(update, context, date_text=None)


async def _save_and_finish(update: Update, context: ContextTypes.DEFAULT_TYPE, date_text: str | None) -> int:
    from bot.utils.formatters import format_budget_summary

    user = update.effective_user
    db_user = db.get_user(user.id)

    trip_start = trip_end = None
    if date_text:
        trip_start, trip_end = _parse_dates(date_text)

    db.set_budgets(db_user["id"], context.user_data["categories"], trip_start, trip_end)

    budgets = [{"category": k, "amount": v} for k, v in context.user_data["categories"].items()]
    summary = format_budget_summary(budgets)

    date_line = f"\n🗓 Trip: {date_text}" if date_text else ""
    await update.message.reply_text(
        f"Perfect! Here's your setup:{date_line}\n\n{summary}\n\nNow just tell me what you spent, e.g. *spent 25 on lunch* 🎉",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


def _parse_dates(text: str) -> tuple[str | None, str | None]:
    import re
    from datetime import datetime

    parts = re.split(r"\s*[-–to]+\s*", text, maxsplit=1)
    if len(parts) != 2:
        return None, None

    start = _to_iso_date(parts[0].strip())
    end = _to_iso_date(parts[1].strip())
    return start, end


def _to_iso_date(text: str) -> str | None:
    from datetime import datetime
    formats = [
        "%d %b %Y", "%d %B %Y",   # "25 Jun 2026", "25 June 2026"
        "%d %b", "%d %B",         # "25 Jun", "25 June"
        "%b %d %Y", "%B %d %Y",   # "Jun 25 2026"
        "%b %d", "%B %d",         # "Jun 25"
        "%Y-%m-%d",               # "2026-06-25"
        "%d/%m/%Y", "%d/%m/%y",   # "25/06/2026"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            # If no year in format, assume current year
            if dt.year == 1900:
                dt = dt.replace(year=datetime.now().year)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
