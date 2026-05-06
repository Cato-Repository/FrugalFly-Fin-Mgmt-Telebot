from telegram import Update
from telegram.ext import ContextTypes

from bot.utils import db


async def handle_thank_you(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data  # e.g. "thankyou:42"
    if not data.startswith("thankyou:"):
        return

    log_id = int(data.split(":")[1])
    db.record_thank_you(log_id)

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("Noted! Keep it up 💪")
