from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.utils import db
from bot.utils.formatters import format_expense_reply


async def handle_thank_you(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    log_id = int(query.data.split(":")[1])
    db.record_thank_you(log_id)

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("Noted! Keep it up 💪")


async def handle_category_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    category = query.data.split(":")[1]
    pending = context.user_data.pop("pending_expense", None)

    if not pending:
        await query.edit_message_text("Session expired. Please log the expense again.")
        return

    user = query.from_user
    db_user = db.get_user(user.id)
    budgets = db.get_budgets(db_user["id"])

    log = db.log_expense(db_user["id"], pending["amount"], category, pending["note"])
    spent = db.get_spent_by_category(db_user["id"])
    reply_text = format_expense_reply(category, pending["amount"], budgets, spent)

    keyboard = [[InlineKeyboardButton("✅ Thank You", callback_data=f"thankyou:{log['id']}")]]
    await query.edit_message_text(
        reply_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
