import logging
import os

from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.handlers.start import (
    ASK_ACTIVITIES,
    ASK_BUDGET,
    ASK_DESTINATION,
    ASK_DURATION,
    ASK_FOOD,
    ASK_HOTEL,
    ASK_OTHER,
    ASK_TRANSPORT,
    received_activities,
    received_budget,
    received_destination,
    received_duration,
    received_food,
    received_hotel,
    received_other,
    received_transport,
    start,
)
from bot.handlers.plan import adjust_budget, show_help, show_my_plan

load_dotenv()
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO, force=True)


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    onboarding = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("newtrip", start),
        ],
        states={
            ASK_DESTINATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_destination)],
            ASK_DURATION:    [MessageHandler(filters.TEXT & ~filters.COMMAND, received_duration)],
            ASK_BUDGET:      [MessageHandler(filters.TEXT & ~filters.COMMAND, received_budget)],
            ASK_FOOD:        [MessageHandler(filters.TEXT & ~filters.COMMAND, received_food)],
            ASK_TRANSPORT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, received_transport)],
            ASK_HOTEL:       [MessageHandler(filters.TEXT & ~filters.COMMAND, received_hotel)],
            ASK_ACTIVITIES:  [MessageHandler(filters.TEXT & ~filters.COMMAND, received_activities)],
            ASK_OTHER:       [MessageHandler(filters.TEXT & ~filters.COMMAND, received_other)],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("newtrip", start),
        ],
    )

    app.add_handler(onboarding)
    app.add_handler(CommandHandler("myplan", show_my_plan))
    app.add_handler(CommandHandler("adjust", adjust_budget))
    app.add_handler(CommandHandler("help", show_help))

    app.run_polling()


if __name__ == "__main__":
    main()
