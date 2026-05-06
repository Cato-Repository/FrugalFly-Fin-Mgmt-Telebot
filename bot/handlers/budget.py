from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, CommandHandler, filters

from bot.utils import db

EDIT_PICK_CATEGORY = 20
EDIT_NEW_AMOUNT = 21


async def show_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user = db.get_user(user.id)
    if not db_user:
        await update.message.reply_text("No budget found. Send /start to set one up!")
        return

    budgets = db.get_budgets(db_user["id"])
    if not budgets:
        await update.message.reply_text("No active trip found. Send /start to set one up!")
        return

    spent = db.get_spent_by_category(db_user["id"])
    lines = ["*Your budget overview:*"]
    total_budget = 0.0
    total_spent = 0.0

    for b in budgets:
        cat = b["category"]
        budget_amt = float(b["amount"])
        spent_amt = spent.get(cat, 0.0)
        remaining = budget_amt - spent_amt
        emoji = "✅" if remaining >= 0 else "⚠️"
        lines.append(f"{emoji} {cat.title()}: ${spent_amt:,.2f} spent / ${budget_amt:,.2f} budget (${remaining:,.2f} left)")
        total_budget += budget_amt
        total_spent += spent_amt

    total_remaining = total_budget - total_spent
    lines.append(f"\n💰 Total: ${total_spent:,.2f} / ${total_budget:,.2f} (${total_remaining:,.2f} left)")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def show_total(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user = db.get_user(user.id)
    if not db_user:
        await update.message.reply_text("No budget found. Send /start to set one up!")
        return

    total = db.get_total_spent(db_user["id"])
    budgets = db.get_budgets(db_user["id"])
    total_budget = sum(float(b["amount"]) for b in budgets) if budgets else 0.0

    await update.message.reply_text(
        f"💸 *Total spent so far:* ${total:,.2f}\n💰 *Total budget:* ${total_budget:,.2f}\n📉 *Remaining:* ${total_budget - total:,.2f}",
        parse_mode="Markdown",
    )


async def end_trip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db_user = db.get_user(user.id)
    if not db_user:
        await update.message.reply_text("No active trip found.")
        return

    budgets = db.get_budgets(db_user["id"])
    if not budgets:
        await update.message.reply_text("No active trip to end.")
        return

    spent = db.get_spent_by_category(db_user["id"])
    total_budget = sum(float(b["amount"]) for b in budgets)
    total_spent = sum(spent.values())

    db.end_trip(db_user["id"])

    lines = ["*Trip ended! Here's your final summary:*\n"]
    for b in budgets:
        cat = b["category"]
        spent_amt = spent.get(cat, 0.0)
        lines.append(f"• {cat.title()}: ${spent_amt:,.2f} / ${float(b['amount']):,.2f}")

    lines.append(f"\n💰 Total spent: ${total_spent:,.2f} / ${total_budget:,.2f}")
    lines.append("\nSend /start to set up a new trip!")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*How to use FrugalFly:*\n\n"
        "*Setup*\n"
        "/start — set up your trip budget\n\n"
        "*Logging expenses* — just type naturally:\n"
        "`spent 25 on lunch`\n"
        "`50 for taxi`\n"
        "`hotel 120`\n\n"
        "*Commands*\n"
        "/budget — full breakdown by category\n"
        "/total — total spent so far\n"
        "/editbudget — change a category budget\n"
        "/end — end your trip early\n"
        "/help — show this message\n\n"
        "*Categories recognised:*\n"
        "🍔 Food — lunch, dinner, cafe, coffee...\n"
        "🚗 Transport — taxi, grab, bus, train...\n"
        "🏨 Hotel — hotel, hostel, airbnb...\n"
        "🎡 Activities — tour, ticket, museum...\n\n"
        "_Anything else? I'll ask you to pick a category._",
        parse_mode="Markdown",
    )


# /editbudget conversation
async def edit_budget_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db_user = db.get_user(user.id)
    if not db_user:
        await update.message.reply_text("No budget found. Send /start to set one up!")
        return ConversationHandler.END

    budgets = db.get_budgets(db_user["id"])
    if not budgets:
        await update.message.reply_text("No active trip found. Send /start to set one up!")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(f"{b['category'].title()} (${float(b['amount']):,.2f})", callback_data=f"editcat:{b['category']}")]
        for b in budgets
    ]
    await update.message.reply_text(
        "Which category do you want to edit?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return EDIT_PICK_CATEGORY


async def edit_budget_pick_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    category = query.data.split(":")[1]
    context.user_data["editing_category"] = category

    await query.edit_message_text(
        f"Enter the new budget for *{category.title()}*:",
        parse_mode="Markdown",
    )
    return EDIT_NEW_AMOUNT


async def edit_budget_new_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        new_amount = float(text.replace(",", ""))
    except ValueError:
        await update.message.reply_text("Please enter a number, e.g. *2000*", parse_mode="Markdown")
        return EDIT_NEW_AMOUNT

    user = update.effective_user
    db_user = db.get_user(user.id)
    category = context.user_data.pop("editing_category", None)

    if not category:
        await update.message.reply_text("Something went wrong. Please try /editbudget again.")
        return ConversationHandler.END

    db.update_budget_amount(db_user["id"], category, new_amount)
    await update.message.reply_text(
        f"✅ *{category.title()}* budget updated to *${new_amount:,.2f}*",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


def build_edit_budget_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("editbudget", edit_budget_start)],
        states={
            EDIT_PICK_CATEGORY: [CallbackQueryHandler(edit_budget_pick_category, pattern="^editcat:")],
            EDIT_NEW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_budget_new_amount)],
        },
        fallbacks=[CommandHandler("editbudget", edit_budget_start)],
    )
