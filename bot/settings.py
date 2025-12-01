import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BITRIX_WEBHOOK_URL = os.getenv("BITRIX_WEBHOOK_URL")
BITRIX_ENTITY_TYPE_ID = int(os.getenv("BITRIX_ENTITY_TYPE_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://xxx.onrender.com/telegram/webhook