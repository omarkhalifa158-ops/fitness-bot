"""
Configuration Module for Smart Fitness & Meal Notification System
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

TIMEZONE = os.getenv("TIMEZONE", "Africa/Cairo")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
WEB_BASE_URL = os.getenv("WEB_BASE_URL", f"http://localhost:{PORT}")

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
ENABLE_TELEGRAM = os.getenv("ENABLE_TELEGRAM", "True").lower() in ("true", "1", "yes")

# WhatsApp (CallMeBot) Configuration
ENABLE_WHATSAPP = os.getenv("ENABLE_WHATSAPP", "False").lower() in ("true", "1", "yes")
CALLMEBOT_PHONE = os.getenv("CALLMEBOT_PHONE", "").strip()
CALLMEBOT_API_KEY = os.getenv("CALLMEBOT_API_KEY", "").strip()

# State File Path
STATE_FILE_PATH = BASE_DIR / "state.json"
CUSTOM_MEALS_PATH = BASE_DIR / "custom_meals.json"
