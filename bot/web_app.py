# bot/web_app.py
import logging

from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

from .settings import TELEGRAM_BOT_TOKEN, WEBHOOK_URL
from .main_logic import start, new_ticket, ticket_answer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Создаём Telegram Application один раз на уровне модуля
telegram_app: Application = (
    ApplicationBuilder()
    .token(TELEGRAM_BOT_TOKEN)
    .build()
)

# Регистрируем хендлеры
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("new", new_ticket))
telegram_app.add_handler(
    MessageHandler(filters.ALL & ~filters.COMMAND, ticket_answer)
)


@app.on_event("startup")
async def on_startup():
    """
    На старте сервиса просто ставим webhook у Telegram.
    Инициализацию Application делаем лениво в самом хендлере вебхука.
    """
    if WEBHOOK_URL:
        await telegram_app.bot.set_webhook(WEBHOOK_URL)
        logger.info("Telegram webhook set to %s", WEBHOOK_URL)
    else:
        logger.warning("WEBHOOK_URL is not set; webhook will NOT be configured")


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    Эндпоинт для Telegram webhook.
    Здесь же лениво инициализируем Application, если ещё не был инициализирован.
    """
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)

    # КЛЮЧЕВОЙ МОМЕНТ:
    # Если Application ещё не инициализирован (telegram_app._initialized == False),
    # проинициализируем его прямо здесь.
    if not getattr(telegram_app, "_initialized", False):
        logger.info("Telegram Application not initialized yet, calling initialize()...")
        await telegram_app.initialize()
        # ВАЖНО: start() НЕ обязателен, если не используешь JobQueue и фоновые задачи

    await telegram_app.process_update(update)
    return {"ok": True}
