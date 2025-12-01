import logging
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from .config_fields import FIELDS
from .settings import BITRIX_WEBHOOK_URL, BITRIX_ENTITY_TYPE_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Используйте /new для создания заявки.")


async def new_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ticket"] = {
        "current_index": 0,
        "answers": {
            f["key"]: [] if f["type"] == "files" else None
            for f in FIELDS
        }
    }
    await ask_next_field(update, context)


async def ask_next_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticket = context.user_data["ticket"]
    idx = ticket["current_index"]

    if idx >= len(FIELDS):
        await finalize_ticket(update, context)
        return

    field = FIELDS[idx]

    if field["type"] == "choice":
        kb = [[item] for item in field["choices"]]
        await update.message.reply_text(
            field["prompt"],
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)
        )
    else:
        await update.message.reply_text(field["prompt"])


async def ticket_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "ticket" not in context.user_data:
        await update.message.reply_text("Начните с /new")
        return

    ticket = context.user_data["ticket"]
    idx = ticket["current_index"]
    field = FIELDS[idx]

    # == обработка текстовых полей ==
    if field["type"] == "text":
        ticket["answers"][field["key"]] = update.message.text
        ticket["current_index"] += 1

    # == варианты ==
    elif field["type"] == "choice":
        val = update.message.text
        if val not in field["choices"]:
            await update.message.reply_text("Выберите вариант из списка.")
            return
        ticket["answers"][field["key"]] = val
        ticket["current_index"] += 1

    # == файлы ==
    elif field["type"] == "files":
        if update.message.text and update.message.text.lower() in ("готово", "всё", "все"):
            ticket["current_index"] += 1
        else:
            if update.message.document:
                ticket["answers"][field["key"]].append(update.message.document.file_id)
            elif update.message.photo:
                ticket["answers"][field["key"]].append(update.message.photo[-1].file_id)
            else:
                await update.message.reply_text("Пришлите файл или напишите «готово».")
                return

    await ask_next_field(update, context)


async def finalize_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticket = context.user_data["ticket"]
    answers = ticket["answers"]

    fields = {
        "TITLE": f"Заявка от @{update.effective_user.username}"
    }

    # маппинг всех UF_ полей
    for f in FIELDS:
        if f["type"] == "files":
            fields[f["bitrix_field"]] = "\n".join(answers[f["key"]])
        else:
            fields[f["bitrix_field"]] = answers[f["key"]]

    payload = {
        "entityTypeId": BITRIX_ENTITY_TYPE_ID,
        "fields": fields
    }

    try:
        resp = requests.post(BITRIX_WEBHOOK_URL + "crm.item.add.json", json=payload)
        data = resp.json()

        item_id = (data.get("result") or {}).get("item", {}).get("id")
        await update.message.reply_text(f"Заявка создана! ID: {item_id}")

    except Exception as e:
        await update.message.reply_text("Ошибка при создании заявки.")
        logger.error("Bitrix error: %s", e)

    del context.user_data["ticket"]