BOT_TOKEN = "6057025819:AAFO9Rj6B84y-HF6er4LAwEEbdla45GE4Fg"  # Replace with your bot token
DB_NAME = "telegram_chat_bot"
DB_USER = "postgres"
DB_PASSWORD = "Emu091006"
DB_HOST = "localhost"
DB_PORT = "5432"
ADMIN_USER_ID = 5935463391
#Replace with your admin ID

#Construct the database URL.
DATABASE_URL = "postgresql://postgres:OSectOkNhhlmYVnOrUsJYqDJzXdGeIjm@caboose.proxy.rlwy.net:59203/railway"
#TELEGRAM_PAYMENT_TOKEN = "your_telegram_payment_token"
#CHAPA_SECRET_KEY = "CHASECK_TEST-1dOO7koopLCEZCvjR9vqy4fHtf2cLSwF"
# config.py
# config.py
import os

CHAPA_SECRET_KEY = os.getenv("CHAPA_SECRET_KEY",
                             "CHASECK_TEST-1dOO7koopLCEZCvjR9vqy4fHtf2cLSwF")
CHAPA_BASE_URL = "https://api.chapa.co/v1/transaction/initialize"
CHAPA_CALLBACK_URL = os.getenv(
    "CHAPA_CALLBACK_URL",
    "https://5252920e-89f9-4852-abe8-e9c1c27a9e9c-00-sft017ukk0bk.riker.replit.dev/chapa_callback"
)
CHAPA_VERIFY_URL = "https://api.chapa.co/v1/transaction/verify/"
WEBHOOK_PATH = "/chapa_callback"  # Make this match the path in CHAPA_CALLBACK_URL# The specific path where your Chapa webhook handler will listen
CHAPA_WEBHOOK_SECRET = "Emu091006$"
BASE_WEBHOOK_URL = "https://5252920e-89f9-4852-abe8-e9c1c27a9e9c-00-sft017ukk0bk.riker.replit.dev"
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", 8000))
# ... other config variables like DATABASE_URL, TEMP_PHOTO_DIR etc.
# ... other config variables like DATABASE_URL, TEMP_PHOTO_DIR etc.
#Optional: you can remove the individual database variables, if you want.
#DB_NAME = None, DB_USER = None, DB_PASSWORD = None, DB_HOST = None, DB_PORT = None
