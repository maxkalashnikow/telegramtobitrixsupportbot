import os
import logging
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters

from .settings import TELEGRAM_BOT_TOKEN, WEBHOOK_URL
from .main_logic import start, new_ticket, ticket_answer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

telegram_app: Application = (
    ApplicationBuilder()
    .token(TELEGRAM_BOT_TOKEN)
    .build()
)

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("new", new_ticket))
telegram_app.add_handler(
    MessageHandler(filters.ALL & ~filters.COMMAND, ticket_answer)
)


@app.on_event("startup")
async def startup():
    if WEBHOOK_URL:
        await telegram_app.bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook set: {WEBHOOK_URL}")


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}
