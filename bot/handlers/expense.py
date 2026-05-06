from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.utils import db
from bot.utils.parser import parse_expense
from bot.utils.formatters import format_expense_reply

KNOWN_CATEGORIES = ["food", "transport", "hotel", "activities"]


async def handle_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    parsed = parse_expense(text)

    if not parsed:
        return

    user = update.effective_user
    db_user = db.get_user(user.id)
    if not db_user:
        await update.message.reply_text("You haven't set up a budget yet. Send /start to begin!")
        return

    budgets = db.get_budgets(db_user["id"])
    if not budgets:
        await update.message.reply_text("No budget found. Send /start to set one up first!")
        return

    # If category is unknown, ask user to pick instead of auto-saving
    if parsed["category"] == "uncategorised":
        db.log_unknown_category(db_user["id"], parsed["note"])
        context.user_data["pending_expense"] = {
            "amount": parsed["amount"],
            "note": parsed["note"],
        }
        keyboard = [
            [
                InlineKeyboardButton("🍔 Food", callback_data="cat_select:food"),
                InlineKeyboardButton("🚗 Transport", callback_data="cat_select:transport"),
            ],
            [
                InlineKeyboardButton("🏨 Hotel", callback_data="cat_select:hotel"),
                InlineKeyboardButton("🎡 Activities", callback_data="cat_select:activities"),
            ],
            [InlineKeyboardButton("💸 Other", callback_data="cat_select:other")],
        ]
        await update.message.reply_text(
            f"Got *${parsed['amount']:,.2f}* — what category is this?\n_{parsed['note']}_",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return

    log = db.log_expense(
        user_id=db_user["id"],
        amount=parsed["amount"],
        category=parsed["category"],
        note=parsed["note"],
    )

    spent = db.get_spent_by_category(db_user["id"])
    reply_text = format_expense_reply(parsed["category"], parsed["amount"], budgets, spent)

    keyboard = [[InlineKeyboardButton("✅ Thank You", callback_data=f"thankyou:{log['id']}")]]
    await update.message.reply_text(
        reply_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
