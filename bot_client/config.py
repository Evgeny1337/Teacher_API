import os

from dotenv import load_dotenv

from bot_client.api import TeacherApiClient

load_dotenv(override=True)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_SHARED_SECRET = os.getenv("BOT_SHARED_SECRET", "test")
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

api = TeacherApiClient(API_BASE_URL, BOT_SHARED_SECRET)
