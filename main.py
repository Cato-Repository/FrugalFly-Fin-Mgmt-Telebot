import logging
import os

from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.handlers.start import (
    ASK_BUDGET,
    ASK_CATEGORIES,
    ASK_DATES,
    ASK_SPLIT,
    received_categories,
    received_dates,
    received_total_budget,
    skip_dates,
    split_choice,
    start,
)
from bot.handlers.budget import build_edit_budget_handler, end_trip, show_budget, show_help, show_total
from bot.handlers.callbacks import handle_category_select, handle_thank_you
from bot.handlers.expense import handle_expense

load_dotenv()
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    onboarding = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_total_budget)],
            ASK_SPLIT: [CallbackQueryHandler(split_choice, pattern="^split_")],
            ASK_CATEGORIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_categories)],
            ASK_DATES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_dates),
                CommandHandler("skip", skip_dates),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(onboarding)
    app.add_handler(build_edit_budget_handler())
    app.add_handler(CommandHandler("budget", show_budget))
    app.add_handler(CommandHandler("total", show_total))
    app.add_handler(CommandHandler("end", end_trip))
    app.add_handler(CommandHandler("help", show_help))
    app.add_handler(CallbackQueryHandler(handle_thank_you, pattern="^thankyou:"))
    app.add_handler(CallbackQueryHandler(handle_category_select, pattern="^cat_select:"))

    # Catch-all text handler for expense logging (must be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_expense))

    app.run_polling()


if __name__ == "__main__":
    main()
