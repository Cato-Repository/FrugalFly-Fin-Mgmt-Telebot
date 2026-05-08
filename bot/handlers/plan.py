from telegram import Update
from telegram.ext import ContextTypes

from bot.utils import db

_VALID_CATS = {"food", "transport", "hotel", "activities", "other"}


async def show_my_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from bot.utils.formatters import format_my_plan

    user = update.effective_user
    db_user = db.get_user(user.id)
    if not db_user:
        await update.message.reply_text("No plan found. Use /start to create one!")
        return

    plan = db.get_trip_plan(db_user["id"])
    if not plan:
        await update.message.reply_text("No plan found. Use /start to create one!")
        return

    await update.message.reply_text(format_my_plan(plan), parse_mode="Markdown")


async def adjust_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /adjust <category> <amount>
    Example: /adjust food 350
    """
    from bot.utils.formatters import format_plan_comparison
    from bot.utils.llm import optimize_budget

    args = context.args or []
    if len(args) != 2 or args[0].lower() not in _VALID_CATS:
        await update.message.reply_text(
            "Usage: `/adjust <category> <amount>`\n\n"
            "Categories: food · transport · hotel · activities · other\n\n"
            "Example: `/adjust food 350`",
            parse_mode="Markdown",
        )
        return

    cat = args[0].lower()
    try:
        new_amount = float(args[1].replace(",", ""))
        if new_amount < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please enter a valid amount (e.g. 350).")
        return

    user = update.effective_user
    db_user = db.get_user(user.id)
    if not db_user:
        await update.message.reply_text("No plan found. Use /start to create one!")
        return

    plan = db.get_trip_plan(db_user["id"])
    if not plan:
        await update.message.reply_text("No plan found. Use /start to create one!")
        return

    planned = {
        "food": float(plan.get("planned_food") or 0),
        "transport": float(plan.get("planned_transport") or 0),
        "hotel": float(plan.get("planned_hotel") or 0),
        "activities": float(plan.get("planned_activities") or 0),
        "other": float(plan.get("planned_other") or 0),
    }
    planned[cat] = new_amount

    total_budget = float(plan["total_budget"])
    if sum(planned.values()) > total_budget * 1.5:
        await update.message.reply_text(
            f"⚠️ That would put your planned total far above your budget of ${total_budget:,.2f}. "
            f"Please adjust other categories first or start fresh with /newtrip."
        )
        return

    thinking_msg = await update.message.reply_text("🔍 Re-optimising your plan...")

    try:
        result = optimize_budget(plan["destination"], plan["duration_days"], total_budget, planned)
    except Exception:
        await thinking_msg.edit_text("Sorry, couldn't re-optimise right now. Try again later.")
        return

    optimized = {k: result[k] for k in ["food", "transport", "hotel", "activities", "other"]}
    db.update_trip_plan_optimized(
        db_user["id"],
        planned,
        optimized,
        result.get("explanation", ""),
        result.get("tips", []),
    )

    reply = format_plan_comparison(
        plan["destination"], plan["duration_days"], total_budget, planned, result
    )
    await thinking_msg.edit_text(reply, parse_mode="Markdown")


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*FrugalFly — Pre-Travel Budget Planner* ✈️\n\n"
        "Plan your trip budget *before* you go. I'll analyse your spending plan and suggest the optimal allocation so you don't exceed your budget.\n\n"
        "*Commands:*\n"
        "/start — Plan a new trip\n"
        "/myplan — View your current trip plan & suggestions\n"
        "/adjust <category> <amount> — Tweak a category and re-optimise\n"
        "   e.g. `/adjust food 350`\n"
        "/newtrip — Start over with a new trip\n"
        "/help — Show this message\n\n"
        "*Categories:* food · transport · hotel · activities · other",
        parse_mode="Markdown",
    )
