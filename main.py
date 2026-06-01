import logging
import os
import warnings
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.handlers.start import (
    ASK_ACTIVITIES,
    ASK_BUDGET,
    ASK_CURRENCY,
    ASK_DESTINATION,
    ASK_DURATION,
    ASK_FEEDBACK_Q1,
    ASK_FEEDBACK_Q1_WHY,
    ASK_FEEDBACK_Q2,
    ASK_FEEDBACK_Q2_WHY,
    ASK_FEATURE_REQUEST,
    ASK_FOOD,
    ASK_HOTEL,
    ASK_OTHER,
    ASK_TRANSPORT,
    received_activities,
    received_budget,
    received_currency,
    received_destination,
    received_duration,
    received_feature_request,
    received_feedback_q1,
    received_feedback_q1_why,
    received_feedback_q2,
    received_feedback_q2_why,
    received_food,
    received_hotel,
    received_other,
    received_transport,
    start,
)
from bot.handlers.plan import adjust_budget, show_help, show_my_plan

load_dotenv()
warnings.filterwarnings("ignore", message="If 'per_message=False'", category=UserWarning)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    force=True,
)


def _build_application() -> Application:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    onboarding = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("newtrip", start),
        ],
        states={
            ASK_CURRENCY:        [CallbackQueryHandler(received_currency)],
            ASK_DESTINATION:     [MessageHandler(filters.TEXT & ~filters.COMMAND, received_destination)],
            ASK_DURATION:        [MessageHandler(filters.TEXT & ~filters.COMMAND, received_duration)],
            ASK_BUDGET:          [MessageHandler(filters.TEXT & ~filters.COMMAND, received_budget)],
            ASK_FOOD:            [MessageHandler(filters.TEXT & ~filters.COMMAND, received_food)],
            ASK_TRANSPORT:       [MessageHandler(filters.TEXT & ~filters.COMMAND, received_transport)],
            ASK_HOTEL:           [MessageHandler(filters.TEXT & ~filters.COMMAND, received_hotel)],
            ASK_ACTIVITIES:      [MessageHandler(filters.TEXT & ~filters.COMMAND, received_activities)],
            ASK_OTHER:           [MessageHandler(filters.TEXT & ~filters.COMMAND, received_other)],
            ASK_FEEDBACK_Q1:     [CallbackQueryHandler(received_feedback_q1)],
            ASK_FEEDBACK_Q1_WHY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_feedback_q1_why)],
            ASK_FEEDBACK_Q2:     [CallbackQueryHandler(received_feedback_q2)],
            ASK_FEEDBACK_Q2_WHY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_feedback_q2_why)],
            ASK_FEATURE_REQUEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_feature_request)],
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
    return app


ptb_app = _build_application()


@asynccontextmanager
async def lifespan(_: FastAPI):
    webhook_url = os.environ["WEBHOOK_URL"].rstrip("/")
    async with ptb_app:
        await ptb_app.start()
        await ptb_app.bot.set_webhook(
            url=f"{webhook_url}/webhook",
            allowed_updates=Update.ALL_TYPES,
        )
        yield
        await ptb_app.bot.delete_webhook()
        await ptb_app.stop()


web_app = FastAPI(lifespan=lifespan)


@web_app.api_route("/", methods=["GET", "HEAD"])
async def health(request: Request):
    if request.method == "HEAD":
        return Response(status_code=200)
    return {"status": "ok"}


@web_app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.update_queue.put(update)
    return Response(status_code=200)


if __name__ == "__main__":
    if os.environ.get("WEBHOOK_URL"):
        import uvicorn
        uvicorn.run(web_app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    else:
        # Fallback to polling for local development
        ptb_app.run_polling()
