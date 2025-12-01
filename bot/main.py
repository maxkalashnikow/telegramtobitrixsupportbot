import logging
import requests

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from .settings import TELEGRAM_BOT_TOKEN, BITRIX_WEBHOOK_URL, BITRIX_ENTITY_TYPE_ID
from .config_fields import FIELDS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для создания заявки в Bitrix24.\n"
        "Напишите /new, чтобы создать новую заявку."
    )


async def new_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ticket"] = {
        "current_index": 0,
        "answers": {field["key"]: [] if field["type"] == "files" else None for field in FIELDS},
    }
    await ask_next_field(update, context)


async def ask_next_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticket = context.user_data.get("ticket")
    if not ticket:
        await update.message.reply_text("Начните с /new для создания новой заявки.")
        return

    idx = ticket["current_index"]
    if idx >= len(FIELDS):
        await finalize_ticket(update, context)
        return

    field = FIELDS[idx]

    if field["type"] == "choice":
        kb = [[choice] for choice in field["choices"]]
        await update.message.reply_text(
            field["prompt"],
            reply_markup=ReplyKeyboardMarkup(
                kb,
                one_time_keyboard=True,
                resize_keyboard=True,
            ),
        )
    else:
        await update.message.reply_text(field["prompt"])


async def ticket_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticket = context.user_data.get("ticket")
    if not ticket:
        await update.message.reply_text("Наберите /new, чтобы создать новую заявку.")
        return

    idx = ticket["current_index"]
    if idx >= len(FIELDS):
        await update.message.reply_text("Данные уже собраны, подождите.")
        return

    field = FIELDS[idx]

    if field["type"] == "text":
        ticket["answers"][field["key"]] = update.message.text
        ticket["current_index"] += 1

    elif field["type"] == "choice":
        text = update.message.text
        if text not in field["choices"]:
            await update.message.reply_text("Пожалуйста, выберите один из вариантов на клавиатуре.")
            return
        ticket["answers"][field["key"]] = text
        ticket["current_index"] += 1

    elif field["type"] == "files":
        if update.message.text and update.message.text.lower() in ("готово", "всё", "все", "готова"):
            ticket["current_index"] += 1
        else:
            if update.message.document:
                file_id = update.message.document.file_id
                ticket["answers"][field["key"]].append(file_id)
            elif update.message.photo:
                photo = update.message.photo[-1]
                ticket["answers"][field["key"]].append(photo.file_id)
            else:
                await update.message.reply_text(
                    "Пришлите файл (документ/фото) или напишите «готово», когда закончите."
                )
                return

    context.user_data["ticket"] = ticket
    await ask_next_field(update, context)


async def finalize_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticket = context.user_data.get("ticket")
    if not ticket:
        await update.message.reply_text("Заявка не найдена. Наберите /new.")
        return

    answers = ticket["answers"]

    fields_for_bitrix = {
        "TITLE": f"Заявка из Telegram от @{update.effective_user.username or update.effective_user.id}",
    }

    for field in FIELDS:
        key = field["key"]
        bx_field = field["bitrix_field"]
        value = answers[key]

        if field["type"] == "files":
            fields_for_bitrix[bx_field] = "\n".join(value) if value else ""
        else:
            fields_for_bitrix[bx_field] = value

    url = BITRIX_WEBHOOK_URL + "crm.item.add.json"
    payload = {
        "entityTypeId": BITRIX_ENTITY_TYPE_ID,
        "fields": fields_for_bitrix,
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Bitrix response: %s", data)

        item_id = data.get("result", {}).get("item", {}).get("id") or data.get("result")
        await update.message.reply_text(
            f"Заявка создана в Bitrix24.\nID элемента смарт-процесса: {item_id}"
        )
    except Exception as e:
        logger.exception("Ошибка при создании заявки в Bitrix24")
        await update.message.reply_text("Ошибка при создании заявки в Bitrix24. Сообщите администратору.")

    context.user_data["ticket"] = None


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_ticket))
    app.add_handler(
        MessageHandler(
            filters.TEXT | filters.PHOTO | filters.Document.ALL,
            ticket_answer,
        )
    )

    app.run_polling()


if __name__ == "__main__":
    main()
