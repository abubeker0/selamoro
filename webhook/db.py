# db.py
import asyncpg
from webhook.config import DATABASE_URL

async def create_database_connection():
    return await asyncpg.connect(DATABASE_URL)
