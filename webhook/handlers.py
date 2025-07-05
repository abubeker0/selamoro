import os
import uuid
import time
import random
import logging
import asyncio
import aiofiles
import aiohttp
import asyncpg
import psycopg2
import psycopg2.extras

from datetime import datetime, timedelta, timezone, date
from collections import defaultdict
from aiohttp import web, ClientSession, ClientError
from aiogram import Bot, Router, F, types
from aiogram.types import (Message, CallbackQuery, ReplyKeyboardRemove,
                           ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton,
                           FSInputFile, LabeledPrice, PreCheckoutQuery,
                           SuccessfulPayment, BotCommand)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from datetime import datetime
import webhook.config as config
from .config import (CHAPA_SECRET_KEY, CHAPA_BASE_URL, CHAPA_CALLBACK_URL,
                     WEBHOOK_PATH, CHAPA_VERIFY_URL, BASE_WEBHOOK_URL,
                     WEB_SERVER_HOST, WEB_SERVER_PORT)

# Logger setup
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global router instance
router = Router()

# Other global variables
now = datetime.now(timezone.utc)
vip_search_locks = {}
async def create_database_connection():
    """Creates and returns an asynchronous database connection using asyncpg."""
    try:
        conn = await asyncpg.connect(config.DATABASE_URL)
        return conn
    except Exception as e:
        # It's good to log this error
        logger.error(f"Failed to connect to PostgreSQL database: {e}",
                     exc_info=True)
        raise  # Re-raise the exception so the calling code knows it failed


async def create_pool():
    return await asyncpg.create_pool(
        dsn=config.
        DATABASE_URL,  # Example: "postgresql://user:password@host/db"
        min_size=1,
        max_size=5)


async def set_commands(bot: Bot):
    commands = [
        types.BotCommand(command="start", description="Bot jalqabaa"),
        types.BotCommand(command="search",
                         description="🔍 Hiriyaa barbaadi"),
        types.BotCommand(command="stop",
                         description="🛑 Chat ammaa dhaabaa"),
        types.BotCommand(command="next", description="➡️ Hiriyaa haaraa barbaadi"),
        types.BotCommand(command="settings",
                         description="⚙️ Saala, umrii ykn bakka haaromsuu"),
        types.BotCommand(command="vip", description="💎 Miseensa VIP ta'aa"),
        types.BotCommand(command="credit", description="💰 Liqii argachuu"),
        types.BotCommand(command="userid",
                         description="🆔 ID fayyadamaa keessan agarsiisi"),
    ]
    await bot.set_my_commands(commands)


def location_keyboard():
    """Creates a reply keyboard for location sharing."""
    return types.ReplyKeyboardMarkup(keyboard=[[
        types.KeyboardButton(text="📍 Bakka Qoodaa", request_location=True)
    ]],
                                     resize_keyboard=True,
                                     one_time_keyboard=True)



async def get_city_from_coords(lat, lon):
    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
    headers = {"User-Agent": "TelegramBot"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("address", {}).get("city") or \
                   data.get("address", {}).get("town") or \
                   data.get("address", {}).get("village")


@router.message(F.location)
async def location_handler(message: types.Message, bot: Bot):
    """Handles location sharing and saves city name."""
    location = message.location
    lat, lon = location.latitude, location.longitude
    city = await get_city_from_coords(lat, lon)

    if not city:
        await message.answer(
            "⚠️ Magaalaa keessan adda baasuu hin dandeenye. Mee booda irra deebi'ii yaalaa.",
            reply_markup=ReplyKeyboardRemove())
        return

    conn = None  # Initialize conn to None
    try:
        conn = await create_database_connection(
        )  # This now returns an asyncpg connection

        # Use await conn.execute() for UPDATE statements
        # Replace %s with $1, $2 for asyncpg parameters
        await conn.execute("UPDATE users SET location = $1 WHERE user_id = $2",
                           city, message.from_user.id)

        logger.info(f"User {message.from_user.id} location updated to {city}.")

    except Exception as e:
        logger.error(
            f"Database error updating user location for {message.from_user.id}: {e}",
            exc_info=True)
        await message.answer(
            "❌ Yeroo bakka kee qusattu dogongorri kuusdeetaa keessoo uumame. Mee irra deebi'ii yaalaa."
        )
        return  # Exit the function if DB update fails
    finally:
        if conn:
            await conn.close()  # Close the connection when done

    await message.answer(f"✅ Bakki akka: {city}",
                         reply_markup=ReplyKeyboardRemove())
    await set_commands(
        bot)  # Assuming set_commands is an async function that needs await
    # Global dictionary to store current chat partners


current_chats = {}


def gender_keyboard(context="start"):
    """Creates an inline keyboard for gender selection."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="♂️ Dhiira",
                                 callback_data=f"gender:{context}:male")
        ],
        [
            InlineKeyboardButton(text="♀️ Dubartii",
                                 callback_data=f"gender:{context}:female")
        ],
        [
            InlineKeyboardButton(text="kamuu",
                                 callback_data=f"gender:{context}:any")
        ],
    ])
    return keyboard


def location_keyboard():
    """Creates a reply keyboard for location sharing."""
    keyboard = ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text="📍 Bakka Qoodaa", request_location=True)
    ]],
                                   resize_keyboard=True,
                                   one_time_keyboard=True)
    return keyboard


# Placeholder for set_commands and logger if not already imported/defined
async def set_commands(bot: Bot):
    # This is a placeholder. Replace with your actual implementation.
    logging.info("Setting commands for bot.")


logger = logging.getLogger(__name__)  # Use the logger for consistent logging


@router.message(CommandStart())
async def cmd_start(message: types.Message, bot: Bot):
    """Handles the /start command."""
    logger.info(f"Received /start from user {message.from_user.id}")
    conn = None  # Initialize conn to None for safe cleanup
    try:
        conn = await create_database_connection(
        )  # This returns an asyncpg connection

        # Fetch user data directly using await conn.fetchrow()
        # Use $1 for positional parameters
        user = await conn.fetchrow(
            "SELECT user_id, gender, age, location FROM users WHERE user_id = $1",
            message.from_user.id)
        logger.info(f"User data: {user}")

        if not user:
            logger.info("User does not exist, inserting.")
            # Insert new user using await conn.execute()
            await conn.execute("INSERT INTO users (user_id) VALUES ($1)",
                               message.from_user.id)
            await message.answer(
                "👋 Baga gara Botii Maqaa Hin Qabneetti dhuftan! Mee isin haa qopheessinu.\n\n"
                "Maaloo saala kee filadhu:",
                reply_markup=gender_keyboard())
            logger.info("Sent gender keyboard.")
        elif user['gender'] is None or user['age'] is None:
            logger.info("User gender or age is None.")
            await message.answer(
                "⚠️ Profaayilli kee guutuu miti. Mee qindeessaa xumuri.\n\n"
                "Saalaa kee filadhu:",
                reply_markup=gender_keyboard())
            logger.info("Sent gender keyboard.")
        elif user['location'] is None:
            logger.info("User location is None.")
            await message.answer(
                "📍 Taphoota fooyya'aa ta'aniif bakka jirtan qooduu barbaadduu?\n\n"
                "Kun filannoodha, garuu namoota sitti dhihoo jiran argachuuf nu gargaara. yoo hin taane ajaja /search fayyadamii walsimsiisaa barbaadi.",
                reply_markup=location_keyboard())
            logger.info("Sent location keyboard.")
        else:
            logger.info("User profile is complete.")
            await message.answer("🎉 Baga nagaan dhuftan! Hundi keessan qophaa'aa jirtu.")
            logger.info("Sent welcome back message.")

        await set_commands(bot)
        logger.info("Set commands.")

    except Exception as e:
        logger.error(
            f"Error in cmd_start for user {message.from_user.id}: {e}",
            exc_info=True)
        # You might want to send an error message to the user here
        await message.answer(
            "❌ Dogoggorri hin eegamne uumame. Mee booda irra deebi'ii yaalaa.")
    finally:
        if conn:
            await conn.close()  # Ensure connection is closed
            logger.info("Database connection closed.")


@router.callback_query(F.data.startswith("gender:"))
async def gender_callback(query: types.CallbackQuery, bot: Bot):
    """Handles gender selection callback."""
    # Always answer the callback query to dismiss the loading state on the client
    await query.answer()

    context, gender = query.data.split(":")[1], query.data.split(":")[2]
    user_id = query.from_user.id
    conn = None  # Initialize conn to None for safe cleanup
    try:
        conn = await create_database_connection(
        )  # This returns an asyncpg connection

        # Use await conn.execute() for UPDATE statements
        # Replace %s with $1, $2 for asyncpg parameters
        await conn.execute("UPDATE users SET gender = $1 WHERE user_id = $2",
                           gender, user_id)

        logger.info(f"User {user_id} gender updated to {gender}.")

        if context == "change":
            await query.message.answer("✅ Saala haaromfame!")

        if context == "start":
            await query.message.answer("🔢 Mee umrii keessan galchaa:")

        await set_commands(bot)  # Set commands after gender change.

    except Exception as e:
        logger.error(f"Database error updating gender for user {user_id}: {e}",
                     exc_info=True)
        await query.message.answer(
            "❌ Saala kee osoo qusattu dogongorri hin eegamne uumame. Mee booda irra deebi'ii yaalaa."
        )
    finally:
        if conn:
            await conn.close()  # Ensure connection is closed


@router.message(F.text.isdigit())
async def age_handler(message: types.Message, bot: Bot):
    """Handles age input."""
    age = int(message.text)
    user_id = message.from_user.id
    conn = None  # Initialize conn to None for safe cleanup
    try:
        conn = await create_database_connection(
        )  # This returns an asyncpg connection

        # Use await conn.execute() for UPDATE statements
        # Replace %s with $1, $2 for asyncpg parameters
        await conn.execute("UPDATE users SET age = $1 WHERE user_id = $2", age,
                           user_id)

        logger.info(f"User {user_id} age updated to {age}.")

        await message.answer("✅ Profaayilli kee guutuudha!")
        await message.answer(
            "📍 Taphoota fooyya'aa ta'aniif bakka jirtan qooduu barbaadduu?\n\n"
            "Kun filannoodha, garuu namoota sitti dhihoo jiran argachuuf nu gargaara. yoo hin taane ajaja /search fayyadamii walsimsiisaa barbaadi.",
            reply_markup=location_keyboard())

        await set_commands(bot)  # Set commands after age change.

    except Exception as e:
        logger.error(f"Database error updating age for user {user_id}: {e}",
                     exc_info=True)
        await message.answer(
            "❌ Umurii kee osoo qusattu dogongorri hin eegamne uumame. Mee booda irra deebi'ii yaalaa."
        )
    finally:
        if conn:
            await conn.close()  # Ensure connection is closed


# This function does not interact with the database, so no changes needed
@router.callback_query(F.data == "set_gender")
async def set_gender_handler(query: types.CallbackQuery):
    await query.message.answer("🔄 Saala kee haaraa filadhu:",
                               reply_markup=gender_keyboard(context="change"))
    await query.answer()


# This function does not interact with the database, so no changes needed
current_chats = {
}  # Dictionary to store active chat pairs (user_id: partner_id)


# This function does not interact with the database, so no changes needed
def gender_selection_keyboard():
    """Creates an inline keyboard for gender selection."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="♂️ Dhiira",
                                 callback_data="gender_pref:male")
        ],
        [
            InlineKeyboardButton(text="♀️ Dubartii",
                                 callback_data="gender_pref:female")
        ],
        [InlineKeyboardButton(text="kamuu", callback_data="gender_pref:any")],
    ])
    return keyboard


search_queue = [
]  # List to store searching users (user_id, timestamp, gender_pref)
current_chats = {
}  # Dictionary to store active chat pairs (user_id: partner_id)

find_match_lock = asyncio.Lock()  # Already defined


async def find_match(user_id, gender_pref, is_vip):
    global current_chats, search_queue

    logger.debug(
        f"find_match called for user {user_id}. Pref: {gender_pref}, VIP: {is_vip}"
    )

    conn = None
    try:
        async with find_match_lock:
            # Check if user is still in the queue (might have been matched already)
            if not any(uid == user_id for uid, _, _ in search_queue):
                logger.debug(
                    f"User {user_id} no longer in search_queue at start of find_match."
                )
                return None, None

            user_ids_in_queue = [uid for uid, _, _ in search_queue]
            logger.debug(f"Users currently in queue: {user_ids_in_queue}")

            conn = await create_database_connection()
            rows = await conn.fetch(
                "SELECT user_id, is_vip, gender FROM users WHERE user_id = ANY($1)",
                user_ids_in_queue)
            user_info_map = {row['user_id']: row for row in rows}
            logger.debug(f"User info map from DB: {user_info_map}")

            user_own_gender = user_info_map.get(user_id, {}).get('gender')
            if not user_own_gender:
                logger.warning(
                    f"User {user_id} has no gender set, cannot match.")
                # Remove user from queue since can't match properly
                search_queue[:] = [(uid, ts, gen)
                                   for uid, ts, gen in search_queue
                                   if uid != user_id]
                return None, None

            current_user_effective_pref = gender_pref if is_vip else "any"
            logger.debug(
                f"User {user_id} (VIP:{is_vip}) effective preference: {current_user_effective_pref}"
            )

            potential_partners = []

            for other_user_id, _, other_user_gender_pref_in_queue in search_queue:
                if other_user_id == user_id:
                    continue

                other_user_row = user_info_map.get(other_user_id)
                if not other_user_row:
                    logger.debug(
                        f"Skipping {other_user_id}: Not found in DB info map.")
                    continue

                other_user_is_vip = other_user_row['is_vip']
                other_user_gender = other_user_row['gender']

                other_user_effective_pref = other_user_gender_pref_in_queue if other_user_is_vip else "any"

                current_user_likes_other = (
                    current_user_effective_pref == "any"
                    or other_user_gender == current_user_effective_pref)
                other_user_likes_current = (other_user_effective_pref == "any"
                                            or user_own_gender
                                            == other_user_effective_pref)

                logger.debug(
                    f"  Checking pair: {user_id} (gender:{user_own_gender}, vip:{is_vip}) vs {other_user_id} (gender:{other_user_gender}, vip:{other_user_is_vip})"
                )
                logger.debug(
                    f"    {user_id} likes {other_user_id}: {current_user_likes_other}"
                )
                logger.debug(
                    f"    {other_user_id} likes {user_id}: {other_user_likes_current}"
                )

                # Matchmaking logic
                if is_vip and other_user_is_vip:
                    logger.debug(f"    Case: Both VIPs.")
                    if current_user_likes_other and other_user_likes_current:
                        potential_partners.append(
                            (other_user_id, other_user_is_vip))
                        logger.debug(
                            f"      -> Added {other_user_id} to potential partners (mutual VIP like)."
                        )
                elif is_vip and not other_user_is_vip:
                    logger.debug(
                        f"    Case: {user_id} is VIP, {other_user_id} is Non-VIP."
                    )
                    if current_user_likes_other:
                        potential_partners.append(
                            (other_user_id, other_user_is_vip))
                        logger.debug(
                            f"      -> Added {other_user_id} to potential partners (VIP likes Non-VIP)."
                        )
                elif not is_vip and other_user_is_vip:
                    logger.debug(
                        f"    Case: {user_id} is Non-VIP, {other_user_id} is VIP."
                    )
                    if other_user_likes_current:
                        potential_partners.append(
                            (other_user_id, other_user_is_vip))
                        logger.debug(
                            f"      -> Added {other_user_id} to potential partners (VIP likes Non-VIP)."
                        )
                else:  # Both are non-VIPs
                    logger.debug(f"    Case: Both Non-VIPs.")
                    potential_partners.append(
                        (other_user_id, other_user_is_vip)
                    )  # Non-VIPs always match if criteria met before this
                    logger.debug(
                        f"      -> Added {other_user_id} to potential partners (both Non-VIP)."
                    )

            logger.debug(
                f"Potential partners for {user_id} after loop: {potential_partners}"
            )

            if potential_partners:
                partner_id, partner_is_vip = random.choice(potential_partners)

                # Confirm both users are still in queue before finalizing match
                current_queue_user_ids = [uid for uid, _, _ in search_queue]
                if user_id not in current_queue_user_ids or partner_id not in current_queue_user_ids:
                    logger.warning(
                        f"One of the matched users is no longer in the queue: {user_id}, {partner_id}"
                    )
                    return None, None

                # Remove both users from search queue
                search_queue[:] = [(uid, ts, gen)
                                   for uid, ts, gen in search_queue
                                   if uid != user_id and uid != partner_id]

                # Add matched users to current chats
                current_chats[user_id] = partner_id
                current_chats[partner_id] = user_id

                logger.info(
                    f"MATCHED: {user_id} <-> {partner_id} (VIP:{is_vip} vs PartnerVIP:{partner_is_vip})"
                )
                return partner_id, partner_is_vip

            logger.debug(f"No potential partners found for {user_id}.")
            return None, None

    except Exception as e:
        logger.error(f"ERROR in find_match() for user {user_id}: {e}",
                     exc_info=True)
        return None, None
    finally:
        if conn:
            await conn.close()


# 🔧 Ensure tuple on error


async def handle_vip_search(message: types.Message, bot: Bot):
    """Handles /search for VIP users."""
    await message.answer("Saala waliin haasa'uu barbaaddu filadhu:",
                         reply_markup=gender_selection_keyboard())


@router.callback_query(F.data.startswith("gender_pref:"))
async def gender_preference_callback(query: types.CallbackQuery, bot: Bot):
    user_id = query.from_user.id
    gender_pref = query.data.split(":")[1]
    current_time = time.time()

    await query.answer()

    # --- SIMPLIFIED COOLDOWN CHECK ---
    # Check if user is already in the search queue
    if any(uid == user_id for uid, _, _ in search_queue):
        await query.message.answer(
            "⏳ Duraanis tarree barbaacha keessa jirta. Mee barbaacha ammaa keessan akka xumuramu eegaa.ykn /stop gochuu dandeessa"
        )
        await bot.delete_message(chat_id=query.message.chat.id,
                                 message_id=query.message.message_id)
        return
    # --- END SIMPLIFIED COOLDOWN CHECK ---

    # Delete the gender preference message buttons after selection
    await bot.delete_message(chat_id=query.message.chat.id,
                             message_id=query.message.message_id)

    # Prevent searching if already in a chat
    if user_id in current_chats:
        partner_id = current_chats.pop(user_id, None)
        if partner_id and partner_id in current_chats:
            del current_chats[partner_id]
            try:
                await bot.send_message(
                    partner_id,
                    "Hiriyaan kee walitti dhufeenyi addaan citeera. Hiriyaa barbaaduuf /search fayyadami."
                )
            except Exception as e:
                logger.error(
                    f"Could not send disconnect message to {partner_id}: {e}")
        await query.message.answer("Chat keessa turte. Walitti hidhamiinsi addaan cite.")
        return

    # --- DB Fetch (for user's VIP status and gender) ---
    conn = None
    try:
        conn = await create_database_connection()
        user_row = await conn.fetchrow(
            "SELECT is_vip, gender FROM users WHERE user_id = $1", user_id)

        if not user_row:
            await query.message.answer(
                "⚠️ Odeeffannoo fayyadamaa keessanii argachuu hin dandeenye. Mee irra deebi'ii yaalaa.")
            logger.warning(
                f"User {user_id} not found in DB during gender_preference_callback."
            )
            return

        is_vip = user_row['is_vip']
        user_own_gender = user_row['gender']

        if not user_own_gender:
            await query.message.answer(
                "⚠️ Mee dursa saala kee /setgender fayyadamuun saagi.")
            logger.info(
                f"User {user_id} tried to search without setting gender.")
            return

        # Ensure only VIPs can use gender preferences
        if not is_vip:
            await query.message.answer(
                "💎 Walsimsiisni saalaa irratti hundaa'uun amala VIP qofa.\nMiseensa /vip ta'i"
            )
            logger.info(
                f"Non-VIP user {user_id} tried to use gender preference for search."
            )
            return

        # Add user to queue (this implicitly puts them "on cooldown" for searching again)
        search_queue[:] = [(uid, ts, gen) for uid, ts, gen in search_queue
                           if uid != user_id]  # Ensure not duplicated
        search_queue.append((user_id, time.time(), gender_pref))
        logger.info(
            f"User {user_id} added to search queue with preference {gender_pref}."
        )

        searching_message = await query.message.answer(
            "🔍 Hiriyaa barbaaduu...")
        searching_message_id = searching_message.message_id

        partner_id = None
        partner_is_vip = False
        for _ in range(20):  # Try for 20 seconds
            partner_id, partner_is_vip = await find_match(
                user_id, gender_pref, is_vip)
            if partner_id:
                break
            await asyncio.sleep(1)

        # --- Always remove user from search queue after search attempt ---
        # This automatically "ends" their cooldown as per your new logic
        search_queue[:] = [(uid, ts, gen) for uid, ts, gen in search_queue
                           if uid != user_id]
        logger.info(f"User {user_id} removed from search queue after attempt.")

        try:
            await bot.delete_message(chat_id=query.message.chat.id,
                                     message_id=searching_message_id)
        except Exception as e:
            logger.error(
                f"Could not delete searching message {searching_message_id} for user {user_id}: {e}"
            )

        if partner_id:
            # Match found: User is already out of queue due to cleanup above
            current_chats[user_id] = partner_id
            current_chats[partner_id] = user_id

            # Send messages to both users
            if partner_is_vip:
                await query.message.answer(
                    "💎 Hiriyaa VIP kan biraa argatte! Chatting jalqabi!\n\n"
                    "/next — hiriyaa haaraa barbaadi\n"
                    "/stop — marii kana dhaabi.",
                    parse_mode=ParseMode.HTML)
            else:
                await query.message.answer(
                    "✅ Hiriyaan argame! Chatting jalqabi!\n\n"
                    "/next — hiriyaa haaraa barbaadi\n"
                    "/stop — marii kana dhaabi.")

            try:
                await bot.send_message(
                    partner_id, "💎 Hiriyaan VIP argame! Chatting jalqabi!\n\n"
                    "/next — hiriyaa haaraa barbaadi\n"
                    "/stop — marii kana dhaabi.",
                    parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.error(
                    f"Could not send match message to partner {partner_id}: {e}"
                )
            logger.info(
                f"Match found between {user_id} and {partner_id}. User is VIP, partner is VIP:           {partner_is_vip}."
            )
        else:
            # No match found: User is already out of queue due to cleanup above

            logger.info(f"No match found for user {user_id} after timeout.")

    except Exception as e:
        logger.error(
            f"Error in gender_preference_callback for user {user_id}: {e}",
            exc_info=True)
        await query.message.answer(
            "❌ Yeroo barbaacha dogongorri hin eegamne uumame. Mee booda irra deebi'ii yaalaa."
        )
    finally:
        if conn:
            await conn.close()


async def get_partner_searching_message_id(partner_id: int) -> int | None:
    """Retrieves the searching message ID for a given partner ID from the database."""
    conn = None  # Initialize conn to None for safe cleanup
    try:
        conn = await create_database_connection()
        # Use await conn.fetchrow() for a single row
        # Replace %s with $1
        result = await conn.fetchrow(
            "SELECT message_id FROM search_messages WHERE user_id = $1",
            partner_id)
        if result:
            return result['message_id']  # Access the 'message_id' key
        else:
            return None
    except Exception as e:
        logger.error(
            f"ERROR: Error in get_partner_searching_message_id for {partner_id}: {e}",
            exc_info=True)
        return None
    finally:
        if conn:
            await conn.close()


# If no VIP match found, ask if they want to search free users
#if is_vip:
# keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
# [types.InlineKeyboardButton(text="Yes", callback_data=f"search_free:{gender}")],
# [types.InlineKeyboardButton(text="No", callback_data="cancel_search")],
# ])
# await query.message.answer(f"No VIP users are currently available for chat with your selected gender ({gender}). Would you like to search free users?", reply_markup=keyboard)
# else:
#await query.message.answer("No users are currently available for chat with your selected gender.")
# await query.answer()

#@router.callback_query(F.data.startswith("search_free:"))
#async def search_free_callback(query: types.CallbackQuery, bot: Bot):
# """Handles the callback for searching free users after no VIP match."""
# user_id = query.from_user.id
#gender = query.data.split(":")[1]

# if await find_match(user_id, gender, bot, is_vip=False): #sets is_vip to false, so it searches free users.
# await query.answer()
# return

# await query.message.answer("No free users are currently available for chat with your selected gender.")
# await query.answer()

#@router.callback_query(F.data == "cancel_search")
#async def cancel_search_callback(query: types.CallbackQuery):
#"""Handles the callback to cancel the search."""
#await query.message.answer("Search canceled.")


@router.message(lambda message: message.text == "🚹 Saalaan barbaacha")
async def search_by_gender_handler(message: types.Message, bot: Bot):
    await handle_vip_search(message, bot)


def search_menu_reply_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏙️ Magaalaan Barbaadi")],
                  [KeyboardButton(text="🚹 Saalaan barbaacha")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


@router.callback_query(F.data == "set_location")
async def set_location_callback(query: types.CallbackQuery):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="📍 Bakka Qoodaa", request_location=True)
        ]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await query.message.answer("Bakka live keessan nuuf qoodaa:",
                               reply_markup=keyboard)


@router.message(Command("search"))
async def search_command(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    conn = None  # Initialize conn to None for safe cleanup

    try:
        conn = await create_database_connection()

        # Use await conn.fetchrow() for a single row
        # Replace %s with $1
        result = await conn.fetchrow(
            "SELECT is_vip FROM users WHERE user_id = $1", user_id)

        if result and result["is_vip"]:
            # NEW: Quick unlimited VIP search without gender preference
            await quick_vip_search(message)
        else:
            # Normal non-VIP limited search
            await handle_non_vip_search(
                message, bot
            )  # IMPORTANT: handle_non_vip_search is not defined in the provided code
    except Exception as e:
        logger.error(f"Error in search_command for user {user_id}: {e}",
                     exc_info=True)
        await message.answer(
            "❌ Dogoggorri hin eegamne uumame. Mee booda irra deebi'ii yaalaa.")
    finally:
        if conn:
            await conn.close()


# In webhook/handlers.py (or wherever your global state is)
# ...
search_queue = []
current_chats = {}
user_search_cooldowns = {}  # New dictionary to track cooldowns
SEARCH_COOLDOWN_SECONDS = 30  # For example, 30 seconds


async def quick_vip_search(message: types.Message):
    user_id = message.from_user.id
    current_time = time.time()

    # --- SIMPLIFIED COOLDOWN CHECK ---
    # Check if user is already in the search queue
    if any(uid == user_id for uid, _, _ in search_queue):
        await message.answer(
            "⏳ Duraanis tarree barbaacha keessa jirta. Mee barbaacha ammaa keessan akka xumuramu eegaa.ykn /stop gochuu dandeessa"
        )
        return
    # --- END SIMPLIFIED COOLDOWN CHECK ---

    # Prevent searching if already in a chat
    if user_id in current_chats:
        await message.answer("🤔 Yeroo ammaa kana dura marii keessa jirta.\n"
                             "/next — hiriyaa haaraa barbaadi\n"
                             "/stop — qaaqa kana dhaabi.")
        return

    # Add user to queue (this implicitly puts them "on cooldown" for searching again)
    search_queue[:] = [
        (uid, ts, gen) for uid, ts, gen in search_queue if uid != user_id
    ]  # Ensure they are not duplicated if somehow already there
    search_queue.append((user_id, time.time(), "any"))
    logger.info(f"User {user_id} started quick VIP search and added to queue.")

    search_msg = await message.answer("🔍 Hiriyaa barbaaduu...")

    timeout = 20
    interval = 2
    elapsed = 0
    partner_id = None
    partner_is_vip = False

    while elapsed < timeout:
        partner_id, partner_is_vip = await find_match(user_id, "any", True)
        if partner_id:
            break
        await asyncio.sleep(interval)
        elapsed += interval

    # --- Always remove user from search queue after search attempt ---
    # This automatically "ends" their cooldown as per your new logic
    search_queue[:] = [(uid, ts, gen) for uid, ts, gen in search_queue
                       if uid != user_id]
    logger.info(f"User {user_id} removed from search queue after attempt.")

    try:
        await message.bot.delete_message(chat_id=message.chat.id,
                                         message_id=search_msg.message_id)
    except Exception as e:
        logger.error(
            f"Failed to delete search message for user {user_id}: {e}")

    if partner_id:
        # Match found: User is already out of queue due to cleanup above
        current_chats[user_id] = partner_id
        current_chats[partner_id] = user_id

        # Send messages to both users
        if partner_is_vip:
            await message.answer(
                "💎 Hiriyaa VIP kan biraa argatte! Chatting jalqabi!\n\n/next — hiriyaa haaraa\n/stop — marii xumuri",
                parse_mode=ParseMode.HTML)
        else:
            await message.answer(
                "✅ Hiriyaan argame! Chatting jalqabi!\n\n/next — hiriyaa haaraa\n/stop — marii xumuri"
            )

        try:
            await message.bot.send_message(
                partner_id,
                "💎 Hiriyaan VIP argame! Chatting jalqabi!\n\n/next — hiriyaa haaraa\n/stop — marii xumuri",
                parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(
                f"Failed to send match message to partner {partner_id}: {e}")
        logger.info(
            f"Quick VIP search: Match found between {user_id} and {partner_id}"
        )
    else:
        # No match found: User is already out of queue due to cleanup above

        logger.info(
            f"Quick VIP search: No match found for user {user_id} after timeout."
        )


@router.message(Command("stop"))
async def stop_command(message: types.Message, bot: Bot):
    """Handles the /stop command."""
    global current_chats, search_queue
    user_id = message.from_user.id
    logger.info(f"Stop command from {user_id}. Current chats: {current_chats}")

    if user_id not in current_chats:
        await message.answer("Chat sochii qabu keessa hin jirtu./search hiriyaa argachuuf.")
        logger.info(f"{user_id} is not in current_chats.")
        # Remove user from search queue if they were searching
        search_queue[:] = [(uid, ts, gen) for uid, ts, gen in search_queue
                           if uid != user_id]
        return

    partner_id = current_chats[user_id]
    logger.info(f"Partner ID: {partner_id}")

    # Check if the partner also has the user in their current_chats to ensure a valid pair
    if partner_id in current_chats and current_chats[partner_id] == user_id:
        # Remove both from chat map
        del current_chats[user_id]
        del current_chats[partner_id]
        logger.info(
            f"Chat stopped: {user_id} - {partner_id}. Current chats: {current_chats}"
        )

        # Notify partner
        try:
            await bot.send_message(
                partner_id,
                "✅ Hiriyaan kee chat dhaabeera. /search hiriyaa haaraa argachuuf",
                reply_markup=search_menu_reply_keyboard())
        except Exception as e:
            logger.error(
                f"Failed to notify partner {partner_id} about chat stop: {e}")

        # Notify user
        await message.answer("✅ Chat dhaabbate. /search hiriyaa haaraa argachuuf",
                             reply_markup=search_menu_reply_keyboard())

        # Send feedback buttons
        try:
            await bot.send_message(
                partner_id,
                "Muuxannoon hiriyyaa kee isa dhumaa wajjin qabdu akkam ture?",
                reply_markup=feedback_keyboard)
            await message.answer(
                "Muuxannoon hiriyyaa kee isa dhumaa wajjin qabdu akkam ture?",
                reply_markup=feedback_keyboard)
        except Exception as e:
            logger.error(
                f"Failed to send feedback keyboard to {user_id} or {partner_id}: {e}"
            )

        # Remove both from search queue if they were there (redundant if they were matched)
        search_queue[:] = [(uid, ts, gen) for uid, ts, gen in search_queue
                           if uid not in (user_id, partner_id)]

    else:
        # This branch indicates an inconsistent state in current_chats
        await message.answer("Dhimmi chat dhaabuu ture.")
        logger.error(
            f"Inconsistent state when stopping chat for {user_id} - {partner_id}. Current chats: {current_chats}"
        )


@router.message(Command("settings"))
async def settings_command(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Jijjiirraa Saalaa",
                                 callback_data="set_gender")
        ],
        [
            InlineKeyboardButton(text="📍 Bakka Saagi",
                                 callback_data="set_location")
        ], [InlineKeyboardButton(text="🎂 Umurii Saagi", callback_data="set_age")]
    ])
    await message.answer("⚙️ Waan haaromsuu barbaaddan filadhaa:",
                         reply_markup=keyboard)


#def gender_search_keyboard():
#"""Creates an inline keyboard for gender search."""
# keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
# [types.InlineKeyboardButton(text="♂️ Male", callback_data="search_gender:male")],
#[types.InlineKeyboardButton(text="♀️ Female", callback_data="search_gender:female")],
#[types.InlineKeyboardButton(text="Any", callback_data="search_gender:any")],
# ])
#return keyboard

#def city_gender_search_keyboard():
# """Creates an inline keyboard for city and gender search."""
### [types.InlineKeyboardButton(text="♀️ Female", callback_data="search_gender:female")],
# [types.InlineKeyboardButton(text="Any", callback_data="search_gender:any")],
#])
#return keyboard


async def get_user_credits(user_id):
    """Retrieves user credits and search data from the database."""
    conn = None  # Initialize conn to None for safe cleanup
    try:
        conn = await create_database_connection()
        # Use await conn.fetchrow() for a single row
        # Replace %s with $1
        result = await conn.fetchrow(
            "SELECT credit, last_search_date, search_count FROM users WHERE user_id = $1",
            user_id)
        if result:
            # asyncpg.Record objects can be accessed like dictionaries
            return {
                "credits": result['credit'],
                "last_search_date": result['last_search_date'],
                "search_count": result['search_count']
            }
        # Return default values if user not found
        return {"credits": 0, "last_search_date": None, "search_count": 0}
    except Exception as e:
        logger.error(f"Error getting user credits for {user_id}: {e}",
                     exc_info=True)
        # Return default or error indicator on failure
        return {"credits": 0, "last_search_date": None, "search_count": 0}
    finally:
        if conn:
            await conn.close()


async def update_user_credits(user_id, credits, last_search_date,
                              search_count):
    """Updates user credits and search data in the database."""
    conn = None  # Initialize conn to None for safe cleanup
    try:
        conn = await create_database_connection()
        # Use await conn.execute() for UPDATE statements
        # Replace %s with $1, $2, $3, $4 for asyncpg parameters
        await conn.execute(
            "UPDATE users SET credit = $1, last_search_date = $2, search_count = $3 WHERE user_id = $4",
            credits, last_search_date, search_count, user_id)
        logger.info(
            f"User {user_id} credits updated to {credits}, last_search_date to {last_search_date},                  search_count to {search_count}."
        )
    except Exception as e:
        logger.error(f"Error updating user credits for {user_id}: {e}",
                     exc_info=True)
        # Handle the error appropriately, maybe re-raise or return a status
    finally:
        if conn:
            await conn.close()


# Assuming router is initialized, e.g., router = Router()
@router.message(Command("credit"))
async def credit_command(message: types.Message):
    """Handles the /credit command."""
    user_id = message.from_user.id

    try:
        user_data = await get_user_credits(user_id)  # Get current user data
        new_credits = user_data['credits'] + 10  # Add 10 credits

        await update_user_credits(user_id, new_credits,
                                  user_data['last_search_date'],
                                  user_data['search_count'])

        # Send an image showing the credit reward visually
        photo = FSInputFile("media/download.png")
        # Use your actual image file
        await message.answer_photo(photo=photo, parse_mode="HTML")

        # Then send the actual credit update message
        await message.answer(
            f"💰 Qabxii 10 argatte! Waliigalatti qabxii keessan: {new_credits}")

        logger.info(f"User {user_id} added 10 credits. Total: {new_credits}")

    except Exception as e:
        logger.error(
            f"Error processing /credit command for user {user_id}: {e}",
            exc_info=True)
        await message.answer(
            "❌ Yeroo qabxii dabalu dogongorri uumame. Mee booda irra deebi'ii yaalaa."
        )





# Initialize global variables at module level (as provided by you)
search_queue = []
non_vip_search_locks = defaultdict(bool)


# Assume get_user_credits, update_user_credits, and find_match are defined and corrected elsewhere
# Example placeholders if they are in other files:
# from .db_operations import get_user_credits, update_user_credits
# from .matchmaking import find_match

 # Initialize logger


async def handle_non_vip_search(message: types.Message, bot: Bot):
    global search_queue, non_vip_search_locks, current_chats
    user_id = message.from_user.id
    today = date.today()

    if non_vip_search_locks[user_id]:  # defaultdict will handle new keys
        await message.answer(
            "Maaloo gaaffiin barbaacha keessan isa duraa akka xumuramu eegaa.")
        logger.info(
            f"User {user_id} tried to search while another search was active.")
        return

    non_vip_search_locks[
        user_id] = True  # Set lock at the beginning of the try block

    try:
        user_data = await get_user_credits(user_id)
        logger.debug(f"User {user_id} data fetched: {user_data}")

        # Reset search count if it's a new day
        if user_data.get('last_search_date') != today:
            user_data['search_count'] = 0
            await update_user_credits(user_id, user_data.get('credits', 0),
                                      today, 0)
            user_data['last_search_date'] = today
            logger.info(f"User {user_id} daily search count reset.")

        current_search_count = user_data.get('search_count', 0)
        current_credits = user_data.get('credits', 0)
        needs_credit = current_search_count >= 10

        if needs_credit and current_credits <= 0:
            await message.answer(
                "Daangaa barbaacha guyyaa guyyaa keessanii irra geessee jirta ykn liqii hin qabdu. Barbaacha dabalataa argachuuf /credit fayyadami."
            )
            logger.info(
                f"User {user_id} blocked from searching due to limit/credits.")
            return

        # Disconnect from current chat if active
        if user_id in current_chats:
            partner_id = current_chats.pop(user_id, None)
            if partner_id:
                current_chats.pop(partner_id, None)
                try:
                    await bot.send_message(
                        partner_id,
                        "Hiriyaan kee nama haaraaf /search waliin walitti hidhamiinsa addaan kuteera."
                    )
                    logger.info(
                        f"User {user_id} disconnected from {partner_id}.")
                except Exception as e:
                    logger.error(
                        f"Failed to send disconnect message to {partner_id}: {e}"
                    )
            await message.answer(
                "Chat keessan kanaan duraa irraa addaan cittee jirta. Hiriyaa haaraa barbaaduu."
            )

        # Update search count and credits before adding to queue
        new_search_count = current_search_count + 1
        new_credits = current_credits - 1 if needs_credit else current_credits
        await update_user_credits(user_id, new_credits, today,
                                  new_search_count)
        logger.info(
            f"User {user_id} search count incremented to {new_search_count}, credits to {new_credits}."
        )

        # Add user to search queue
        search_queue.append((user_id, time.time(), "any"))
        searching_message = await message.answer("🔍Hiriyaa barbaaduu...")
        logger.info(f"User {user_id} added to search queue.")

        # Try to find a match immediately
        match_made, is_partner_vip = await find_match(user_id, "any", False)

        # If no match found immediately, wait for a timeout
        if not match_made:
            # Wait for a period for a match to be found by others
            await asyncio.sleep(20)
            # Re-check for match after waiting
            match_made, is_partner_vip = await find_match(
                user_id, "any", False)

        # Remove the 'searching' message
        try:
            await bot.delete_message(chat_id=message.chat.id,
                                     message_id=searching_message.message_id)
        except Exception as e:
            logger.error(
                f"Failed to delete search message for user {user_id}: {e}")

        if match_made:
            partner_id = current_chats.get(
                user_id)  # Get partner_id after match is confirmed
            if partner_id:
                if is_partner_vip:
                    await message.answer(
                        "💎 Hiriyaan VIP argame! Chatting jalqabi!\n\n"
                        "/next — hiriyaa haaraa barbaadi\n"
                        "/stop — marii kana dhaabi.")
                else:
                    await message.answer("✅ Hiriyaan argame! Chatting jalqabi!\n\n"
                                         "/next — hiriyaa haaraa barbaadi\n"
                                         "/stop — marii kana dhaabi.")

                try:
                    await bot.send_message(
                        partner_id, "✅ Hiriyaan argame! Chatting jalqabi!\n\n"
                        "/next — hiriyaa haaraa barbaadi\n"
                        "/stop — marii kana dhaabi.")
                    logger.info(
                        f"Match found between {user_id} and {partner_id}.")
                except Exception as e:
                    logger.error(
                        f"Failed to send match message to partner {partner_id}: {e}"
                    )
            else:
                logger.error(
                    f"Match made but partner_id not found in current_chats for {user_id}."
                )
                await message.answer(
                    "❌ Dogoggorri erga walsimsiisaa argateen booda uumame. Mee irra deebi'ii yaalaa."
                )

        else:  # No match found after initial check and timeout
            if user_id in search_queue:  # Still in queue and not in chat
                search_queue[:] = [(uid, ts, gen)
                                   for uid, ts, gen in search_queue
                                   if uid != user_id]
                await message.answer(
                    "Yeroo ammaa kana fayyadamtoonni chat gochuuf hin jiran. Tarree barbaacha irraa haqame."
                )
                logger.info(
                    f"User {user_id} removed from queue (no match found).")
            else:
                logger.info(
                    f"User {user_id} was already removed from queue or matched during timeout."
                )

    except Exception as e:
        logger.error(
            f"Unhandled error in handle_non_vip_search for user {user_id}: {e}",
            exc_info=True)
        await message.answer(
            "❌ Dogoggorri hin eegamne uumame. Mee booda irra deebi'ii yaalaa.")
    finally:
        non_vip_search_locks[user_id] = False  # Release lock in finally block
        logger.debug(f"Lock released for user {user_id}.")


@router.callback_query(F.data.startswith("gender:"))
async def gender_callback(
        query: types.CallbackQuery,
        bot: Bot):  # Add bot parameter if needed for set_commands
    """Handles gender selection callback."""
    # Corrected syntax error 'a' and added context parsing as per original intention
    # Assuming the format is "gender:context:gender_value"
    parts = query.data.split(":")
    context = parts[1] if len(
        parts) > 2 else "start"  # Default context to "start"
    gender = parts[-1]  # Always take the last part as gender

    user_id = query.from_user.id
    conn = None  # Initialize conn to None for safe cleanup

    # Always answer the callback query to dismiss the loading state
    await query.answer()

    try:
        conn = await create_database_connection()
        # Use await conn.execute() for UPDATE statements
        # Replace %s with $1, $2 for asyncpg parameters
        await conn.execute("UPDATE users SET gender = $1 WHERE user_id = $2",
                           gender, user_id)
        logger.info(f"User {user_id} gender updated to {gender}.")

        if context == "change":
            await query.message.answer("✅ Saala haaromfame!")

        # This delete ensures the inline keyboard is removed after selection
        await bot.delete_message(chat_id=query.message.chat.id,
                                 message_id=query.message.message_id)

        if context == "start":
            await query.message.answer("🔢 Mee umrii keessan galchaa:")

        # Assuming set_commands needs to be called after gender change
        # await set_commands(bot) # Uncomment if set_commands is needed here

    except Exception as e:
        logger.error(f"Database error updating gender for user {user_id}: {e}",
                     exc_info=True)
        await query.message.answer(
            "❌ Saala kee osoo qusattu dogongorri hin eegamne uumame. Mee booda irra deebi'ii yaalaa."
        )
    finally:
        if conn:
            await conn.close()  # Ensure connection is closed


@router.message(Command("next"))
async def next_command(message: types.Message, bot: Bot):
    """Handle /next by disconnecting and routing based on VIP status."""
    global search_queue, current_chats, non_vip_search_locks

    user_id = message.from_user.id
    conn = None  # Initialize conn to None for safe cleanup
    logger.info(f"Next command from {user_id}.")

    try:
        # 1. Check ban status
        conn = await create_database_connection()

        # Use await conn.fetchrow() for a single row
        # Replace %s with $1 and NOW() with CURRENT_TIMESTAMP for PostgreSQL
        banned_info = await conn.fetchrow(
            """
            SELECT banned_until FROM banned_users WHERE user_id = $1 AND banned_until > CURRENT_TIMESTAMP
            """,
            user_id  # <--- Pass user_id directly, no comma!
        )

        if banned_info:
            banned_until = banned_info['banned_until']
            await message.answer(
                f"🚫 Hanga...{banned_until.strftime('%Y-%m-%d %H:%M:%S')}."
            )
            logger.info(f"User {user_id} is banned until {banned_until}.")
            return

        # 2. Disconnect from current chat (both users)
        if user_id in current_chats:
            partner_id = current_chats.pop(user_id)
            # Ensure partner exists in current_chats before attempting to pop
            if partner_id in current_chats:
                current_chats.pop(partner_id)
            logger.info(f"User {user_id} disconnected from {partner_id}.")

            try:
                await bot.send_message(
                    partner_id,
                    "Hiriyaan kee chat sana xumure. /search hiriyaa haaraa argachuuf"
                )
                await bot.send_message(
                    partner_id,
                    "Muuxannoon hiriyyaa kee isa dhumaa wajjin qabdu akkam ture?",
                    reply_markup=feedback_keyboard
                )  # Assumes feedback_keyboard is defined
            except Exception as e:
                logger.error(
                    f"Failed to notify partner {partner_id} about /next: {e}")

            await message.answer(
                "Muuxannoon hiriyyaa kee isa dhumaa wajjin qabdu akkam ture?",
                reply_markup=feedback_keyboard)
        else:
            await message.answer("Yeroo ammaa kana chat keessa hin jirtu.")
            logger.info(f"User {user_id} used /next but was not in a chat.")

        # 3. Check VIP status
        # Re-using the same connection is fine if not closed earlier, but typically get a new one per logical operation
        # or ensure a session management if connections are kept open for longer.
        # For simplicity, creating a new connection for VIP check here.
        # If this function is called immediately after a ban check, the connection from ban check could be reused
        # if the ban check connection is not closed prematurely. For separate operations, new connection is safer.
        if conn is None:  # In case the first connection was not created due to error
            conn = await create_database_connection()

        user_vip_info = await conn.fetchrow(
            "SELECT is_vip FROM users WHERE user_id = $1", user_id)
        is_vip = user_vip_info and user_vip_info["is_vip"]
        logger.info(f"User {user_id} VIP status: {is_vip}.")

        # 4. Route accordingly
        if is_vip:
            await quick_vip_search(message
                                   )  # Assumes quick_vip_search is defined
        else:
            await handle_non_vip_search(
                message, bot)  # Assumes handle_non_vip_search is defined

    except Exception as e:
        logger.error(f"Error in /next command for user {user_id}: {e}",
                     exc_info=True)
        await message.answer(
            "❌ Dogoggorri hin eegamne uumame. Mee booda irra deebi'ii yaalaa.")
    finally:
        if conn:
            await conn.close()  # Ensure connection is closed


#@router.message(Command("vip"))
#async def show_vip_options(message: types.Message):
#await message.answer("Choose your VIP plan:", reply_markup=payment_method_keyboard)
@router.message(Command("vip"))
async def vip_command(message: Message):
    user_id = message.from_user.id
    conn = None  # Initialize conn to None for safe cleanup

    try:
        conn = await create_database_connection()
        # Use await conn.fetchrow() for a single row
        # Replace %s with $1
        result = await conn.fetchrow(
            "SELECT is_vip FROM users WHERE user_id = $1", user_id)

        if result and result["is_vip"]:  # Access result like a dictionary
            await message.answer(
                "🎉 Duraanis 💎 **VIP access** qabda!\nAmaloota premium hunda itti gammadaa."
            )
            logger.info(
                f"User {user_id} tried to become VIP but already has access.")
            return
        gif = FSInputFile(
            r"media/Unlock VIP Access.gif")  # Use raw string for Windows path

        await message.answer_animation(animation=gif, parse_mode="HTML")
        # Show payment options
        text = ("<b>💎 Fayyadamaa VIP Ta'i</b>\n"
                "Chaatii deeggaraa fi amaloota gatii olaanaa battalumatti banaa.\n\n"
                "<b>Mala kaffaltii filadhu:</b>")

        builder = InlineKeyboardBuilder()
        builder.button(text="🧾 Telegram Payments",
                       callback_data="pay_telegram")
        builder.button(text="💳 Chapa Payments", callback_data="pay_chapa")

        await message.answer(text, reply_markup=builder.as_markup())
        logger.info(f"User {user_id} was shown VIP payment options.")

    except Exception as e:
        logger.error(f"Error in vip_command for user {user_id}: {e}",
                     exc_info=True)
        await message.answer(
            "❌ Dogoggorri hin eegamne uumame. Mee booda irra deebi'ii yaalaa.")
    finally:
        if conn:
            await conn.close()  # Ensure connection is closed


 # Ensure connection is closed


@router.message(Command("userid"))
async def userid_command(message: types.Message):
    """Handles the /userid command."""
    await message.answer(f"ID Fayyadamaa keessan: `{message.from_user.id}`"
                         )  # Use backticks for inline code
    logger.info(f"User {message.from_user.id} requested their user ID.")


async def get_user_by_id(user_id):
    conn = None  # Initialize conn to None for safe cleanup
    try:
        conn = await create_database_connection()
        # Use await conn.fetchrow() for a single row
        # Replace %s with $1
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1",
                                  user_id)

        # asyncpg.Record objects can be accessed like dictionaries.
        # No need for psycopg2.extras.DictCursor or dict(row) conversion.
        return row if row else None

    except Exception as e:
        logger.error(f"❌ Error in get_user_by_id for user {user_id}: {e}",
                     exc_info=True)
        return None
    finally:
        if conn:
            await conn.close()


class SettingsStates(StatesGroup):
    waiting_for_age = State()  # This line needs to be indented


@router.callback_query(F.data == "set_age")
async def ask_age(query: types.CallbackQuery, state: FSMContext):
    await query.answer()  # Always answer the callback query
    await query.message.answer("🔢 Mee umrii keessan galchaa:")
    await state.set_state(SettingsStates.waiting_for_age)
    logger.info(f"User {query.from_user.id} initiated age setting.")


@router.message(SettingsStates.waiting_for_age)
async def age_input_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()
    if text.isdigit():
        age = int(text)
        if 10 <= age <= 100:
            # Update database here
            # Assuming you have an update function like update_user_profile(user_id, age=age)
            # For demonstration, let's assume a direct update using create_database_connection
            conn = None
            try:
                conn = await create_database_connection()
                await conn.execute(
                    "UPDATE users SET age = $1 WHERE user_id = $2", age,
                    user_id)
                await message.answer(f"✅ Umriin kee akka: **{age}**")
                logger.info(f"User {user_id} successfully set age to {age}.")
            except Exception as e:
                logger.error(f"Error updating age for user {user_id}: {e}",
                             exc_info=True)
                await message.answer(
                    "❌ Umurii kee osoo qusattu dogongorri uumame. Mee booda irra deebi'ii yaalaa."
                )
            finally:
                if conn:
                    await conn.close()
            await state.clear()
        else:
            await message.answer(
                "❌ Maaloo umrii sirrii 10 hanga 100 gidduu jiru galchi.")
            logger.warning(f"User {user_id} entered invalid age: {age}.")
    else:
        await message.answer("❌ Mee umrii lakkoofsaa sirrii ta'e galchi.")
        logger.warning(f"User {user_id} entered non-numeric age: '{text}'.")

@router.message(lambda message: message.text == "🏙️ Magaalaan Barbaadi")
async def search_by_city_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    conn = None

    try:
        conn = await create_database_connection()
        if not conn:
            logger.error("Failed to connect to DB in search_by_city_handler.")
            await message.answer(
                "Dogoggorri keessoo uumame. Mee booda irra deebi'ii yaalaa.")
            return

        user_row = await conn.fetchrow(
            "SELECT is_vip, vip_expires_at, location FROM users WHERE user_id = $1",
            user_id)

        if not user_row or not user_row['is_vip'] or \
           (user_row['vip_expires_at'] and user_row['vip_expires_at'] < datetime.now(timezone.utc)):
            await message.answer(
                "💎 Walsimsiisuun magaalaa irratti hundaa'e **Amaloota VIP qofaa**.\n"
                "Itti hiikuuf miseensa /vip ta'i!"
            )
            logger.info(
                f"User {user_id} tried city search without active VIP.")
            return

        user_location = user_row['location']
        if not user_location:
            await message.answer(
                "📍 Mee dursa bakka jirtan ajaja /setlocation fayyadamuun qoodaa."
            )
            logger.info(
                f"User {user_id} tried city search but has no location set.")
            return

        if user_id in current_chats:
            await message.answer(
                "⚠️ Duraan chat keessa jirta. Hiriyaa haaraa barbaaduu dura jalqaba xumuruuf /stop fayyadami."
            )
            logger.info(
                f"User {user_id} tried city search while in an active chat.")
            return

        if any(user_id == uid for uid, _, _ in search_queue):
            await message.answer(
                "⏳ Duraan walsimsiisaa barbaadaa jirta. Mee eegaa ykn yoo haquu barbaaddan /stop fayyadamaa."
            )
            logger.info(
                f"User {user_id} tried city search but is already in the queue."
            )
            return

        city = user_location.strip()

        # Remove any previous presence in queue
        search_queue[:] = [(uid, ts, loc) for uid, ts, loc in search_queue
                           if uid != user_id]
        search_queue.append((user_id, time.time(), city))
        logger.info(
            f"User {user_id} added to city search queue for city: {city}.")

        searching_msg = await message.answer(
            "🔍 Magaalaa keessan keessatti hiriyaa barbaaduu...")

        match_found = False
        partner_id = None
        partner_is_vip = False

        shuffled_queue = list(search_queue)
        random.shuffle(shuffled_queue)

        # 1. First try matching with a VIP user
        for p_id, _, p_city in shuffled_queue:
            if p_id != user_id and p_city == city and p_id not in current_chats:
                partner_row = await conn.fetchrow(
                    "SELECT is_vip, vip_expires_at FROM users WHERE user_id = $1",
                    p_id)
                if partner_row and partner_row['is_vip'] and \
                   (partner_row['vip_expires_at'] and partner_row['vip_expires_at'] > datetime.now(timezone.utc)):
                    partner_id = p_id
                    partner_is_vip = True
                    match_found = True
                    break

        # 2. If no VIP found, try matching with a non-VIP user
        if not match_found:
            for p_id, _, p_city in shuffled_queue:
                if p_id != user_id and p_city == city and p_id not in current_chats:
                    partner_row = await conn.fetchrow(
                        "SELECT is_vip FROM users WHERE user_id = $1", p_id)
                    if partner_row and not partner_row['is_vip']:
                        partner_id = p_id
                        partner_is_vip = False
                        match_found = True
                        break

        if match_found:
            current_chats[user_id] = partner_id
            current_chats[partner_id] = user_id
            logger.info(
                f"City match: {user_id} matched with {partner_id} in {city}. Partner VIP: {partner_is_vip}"
            )

            try:
                await bot.delete_message(chat_id=user_id,
                                         message_id=searching_msg.message_id)
            except Exception as e:
                logger.error(
                    f"Failed to delete search message for user {user_id}: {e}")

            message_text = (
                "💎 **VIP City Match Found!** Amma miseensa **VIP** kan biraa magaalaa kee keessa jiru waliin chat gochaa jirta.\n\n"
                if partner_is_vip else
                "🏙️ **City Match Found!** Amma nama magaalaa kee keessa jiru waliin chat gochaa jirta.\n\n"
            )

            await bot.send_message(
                partner_id,
                message_text + "/next — hiriyaa haaraa barbaadi\n/stop — marii xumuri",
                parse_mode=ParseMode.HTML)
            await message.answer(
                message_text + "/next — hiriyaa haaraa barbaadi\n/stop — marii xumuri",
                parse_mode=ParseMode.HTML)

            search_queue[:] = [(uid, ts, loc) for uid, ts, loc in search_queue
                               if uid not in (user_id, partner_id)]
            return

        else:
            try:
                await bot.delete_message(chat_id=user_id,
                                         message_id=searching_msg.message_id)
            except Exception as e:
                logger.error(
                    f"Failed to delete search message for user {user_id} (no match): {e}"
                )

            await message.answer(
                "😔 Yeroo ammaa kana magaalaa keessan keessatti fayyadamtoonni sochii qaban hin jiran. Tarree barbaacha keessa turta, akkuma namni naannoo keessan jiru argameen walsimsiifamta."
            )
            logger.info(
                f"No match found for user {user_id} in {city}. Remaining in queue."
            )

    except Exception as e:
        logger.error(
            f"An unexpected error occurred in search_by_city_handler for user {user_id}: {e}",
            exc_info=True)
        await message.answer(
            "❌ Hiriyaa magaalaa barbaadaa osoo jiranii dogongorri hin eegamne uumame. Mee booda irra deebi'ii yaalaa."
        )
    finally:
        if conn:
            await conn.close()


# Common handler logic
async def handle_fallback(message: Message):
    user_id = message.from_user.id

    if user_id not in current_chats:
        await message.answer("🤖 Yeroo ammaa kana chat keessa hin jirtu.\n\n"
                             "Chatting jalqabuuf /Search tuqi.")


@router.message(F.text)
async def chat_handler(message: types.Message, bot: Bot):
    """Handles chat messages."""
    user_id = message.from_user.id
    if user_id in current_chats:
        partner_id = current_chats[user_id]
        await bot.send_message(partner_id, message.text)


@router.message(F.photo)
async def photo_handler(message: types.Message, bot: Bot):
    """Handles photo messages."""
    user_id = message.from_user.id
    if user_id in current_chats:
        partner_id = current_chats[user_id]
        await bot.send_photo(partner_id, message.photo[-1].file_id)


@router.message(F.video)
async def video_handler(message: types.Message, bot: Bot):
    """Handles video messages."""
    user_id = message.from_user.id
    if user_id in current_chats:
        partner_id = current_chats[user_id]
        await bot.send_video(partner_id, message.video.file_id)


@router.message(F.voice)
async def voice_handler(message: types.Message, bot: Bot):
    """Handles voice messages."""
    user_id = message.from_user.id
    if user_id in current_chats:
        partner_id = current_chats[user_id]
        await bot.send_voice(partner_id, message.voice.file_id)


@router.message(F.document)
async def document_handler(message: types.Message, bot: Bot):
    """Handles document messages."""
    user_id = message.from_user.id
    if user_id in current_chats:
        partner_id = current_chats[user_id]
        await bot.send_document(partner_id, message.document.file_id)


@router.message(F.animation)
async def animation_handler(message: types.Message, bot: Bot):
    """Handles GIF messages."""
    user_id = message.from_user.id
    if user_id in current_chats:
        partner_id = current_chats[user_id]
        await bot.send_animation(partner_id, message.animation.file_id)


@router.message(F.photo)
async def payment_proof_handler(message: types.Message, bot: Bot):
    """Handles payment proof photo."""
    user_id = message.from_user.id
    admin_id = config.ADMIN_USER_ID
    conn = await create_database_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO subscription_requests (user_id, payment_proof, request_date, status) VALUES (%s, %s, now(), %s)",
        (user_id, message.photo[-1].file_id, "pending"))
    conn.commit()
    cursor.close()
    conn.close()
    await bot.send_photo(admin_id,
                         message.photo[-1].file_id,
                         caption=f"User {user_id} requests VIP.")
    await message.answer("Your request has been sent to the admin.")


@router.message(Command("approve_vip"))
async def approve_vip_command(message: types.Message, bot: Bot):
    """Handles the /approve_vip command."""
    if message.from_user.id != config.ADMIN_USER_ID:
        await message.answer("You are not authorized to use this command.")
        return

    try:
        user_id = int(message.text.split()[1])
    except (ValueError, IndexError):
        await message.answer("Usage: /approve_vip <user_id>")
        return

    conn = await create_database_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET is_vip = TRUE, subscription_expiry = now() + interval '30 days' WHERE user_id = %s",
        (user_id, ))
    cursor.execute(
        "UPDATE subscription_requests SET status = 'approved' WHERE user_id = %s",
        (user_id, ))
    conn.commit()
    cursor.close()
    conn.close()
    await message.answer(f"User {user_id} VIP approved.")
    await bot.send_message(user_id, "Your VIP status has been approved!")


@router.message(Command("reject_vip"))
async def reject_vip_command(message: types.Message, bot: Bot):
    """Handles the /reject_vip command."""
    if message.from_user.id != config.ADMIN_USER_ID:
        await message.answer("You are not authorized to use this command.")
        return

    try:
        user_id = int(message.text.split()[1])
    except (ValueError, IndexError):
        await message.answer("Usage: /reject_vip <user_id>")
        return

    conn = await create_database_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE subscription_requests SET status = 'rejected' WHERE user_id = %s",
        (user_id, ))
    conn.commit()
    cursor.close()
    conn.close()
    await message.answer(f"User {user_id} VIP rejected.")
    await bot.send_message(user_id, "Your VIP request has been rejected.")


@router.message(F.voice)
async def vip_voice_handler(message: types.Message, bot: Bot):
    """Handles VIP voice messages."""
    user_id = message.from_user.id
    conn = await create_database_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_vip FROM users WHERE user_id = %s", (user_id, ))
    is_vip = cursor.fetchone()['is_vip']
    cursor.close()
    conn.close()

    if is_vip and user_id in current_chats:
        partner_id = current_chats[user_id]
        await bot.send_voice(partner_id, message.voice.file_id)
    elif not is_vip:
        await message.answer(
            "This is a VIP feature. Become a /VIP to use voice messages.")


@router.message(Command("voicecall"))
async def voice_call_command(message: types.Message, bot: Bot):
    """Handles the /voicecall command (simulated)."""
    user_id = message.from_user.id
    conn = await create_database_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_vip FROM users WHERE user_id = %s", (user_id, ))
    is_vip = cursor.fetchone()['is_vip']
    cursor.close()
    conn.close()

    if is_vip and user_id in current_chats:
        partner_id = current_chats[user_id]
        await message.answer("📞 Initiating voice call (simulated).")
        await bot.send_message(partner_id,
                               "📞 Incoming voice call (simulated).")
    elif not is_vip:
        await message.answer(
            "This is a /VIP feature. Become a VIP to use voice calls.")
    else:
        await message.answer("You are not currently in a chat.")


# In your webhook/handlers.py file


# In your webhook/handlers.py file
async def create_tables():
    """Creates necessary database tables if they don't exist."""
    conn = None  # Initialize conn to None
    try:
        conn = await create_database_connection(
        )  # This now returns an asyncpg connection

        # Execute the SQL directly on the connection
        # You don't need 'cursor = conn.cursor()' or 'cursor.execute()' for asyncpg.
        # Use await conn.execute() for DDL (CREATE TABLE) statements.
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                gender TEXT,
                age INTEGER,
                location TEXT,
                is_vip BOOLEAN DEFAULT FALSE,
                subscription_expiry TIMESTAMP,
                pending_vip BOOLEAN DEFAULT FALSE,
                credit INTEGER DEFAULT 0,
                vip_expires_at TIMESTAMP WITH TIME ZONE,
                last_search_date DATE,
                search_count INTEGER DEFAULT 0,
                vip_plan TEXT,
                notified_before_expiry BOOLEAN DEFAULT FALSE 
            );
            CREATE TABLE IF NOT EXISTS subscription_requests (
                request_id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                payment_proof TEXT,
                request_date TIMESTAMP,
                status TEXT
            );
            CREATE TABLE IF NOT EXISTS chapa_payments (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                tx_ref TEXT NOT NULL UNIQUE,
                plan TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                amount NUMERIC(10, 2) NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            );
           CREATE TABLE IF NOT EXISTS banned_users (
               user_id BIGINT PRIMARY KEY,
               banned_until TIMESTAMP WITH TIME ZONE NOT NULL,
               reason TEXT
           );
        """)
        # conn.commit() is generally not needed for DDL (CREATE TABLE) in asyncpg
        # when executed directly, as it auto-commits.
        # But if you run multiple DDL statements in a transaction, you'd use conn.transaction()

        logger.info("Database tables created or already exist.")

    except Exception as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)
        raise  # Re-raise the exception to prevent bot from starting with broken DB
    finally:
        if conn:
            await conn.close()  # Close the connection when done



feedback_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="👍 Gaarii", callback_data="feedback_good")
], [
    InlineKeyboardButton(text="👎 Hamaa", callback_data="feedback_bad")
], [InlineKeyboardButton(text="⚠️ Gabaasa", callback_data=f"feedback_report")]])


@router.callback_query(F.data == "feedback_good")
async def feedback_good(callback: CallbackQuery):
    await callback.answer("Yaadni keessan milkaa'inaan dhiyaateera.",
                          show_alert=True)

    # Optional: Log or save feedback to DB here

    try:
        await callback.message.delete(
        )  # Delete the whole message (text + buttons)
    except Exception as e:
        logging.error(f"Failed to delete feedback message: {e}")


# Remove inline buttons


@router.callback_query(F.data == "feedback_bad")
async def feedback_bad(callback: CallbackQuery):
    await callback.answer("Yaadni keessan milkaa'inaan dhiyaateera.",
                          show_alert=True)
    # Optional: Save to DB or log it
    try:
        await callback.message.delete(
        )  # Delete the whole message (text + buttons)
    except Exception as e:
        logging.error(f"Failed to delete feedback message: {e}")


@router.callback_query(F.data == "feedback_report")
async def feedback_report(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            text="⚠️ Maaloo sababa hiriyaa kee gabaasuuf filadhu:",
            reply_markup=report_reasons_keyboard)
    except Exception as e:
        logging.error(f"Failed to update message with report reasons: {e}")


# Remove inline buttons

report_reasons_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="📢 Beeksisa",
                             callback_data="report_advertising")
    ], [
        InlineKeyboardButton(text="💰 Gurgurtaa", callback_data="report_selling")
    ], [InlineKeyboardButton(text="🔞", callback_data="report_childporn")],
    [InlineKeyboardButton(text="🤲 Kadhachuu", callback_data="report_begging")],
    [InlineKeyboardButton(text="😡 Arrabsoo", callback_data="report_insult")],
    [InlineKeyboardButton(text="🪓 Jeequmsa", callback_data="report_violence")],
    [InlineKeyboardButton(text="🌍 Gandummaa", callback_data="report_racism")],
    [
        InlineKeyboardButton(text="🤬 Hiriyaa Vulgar",
                             callback_data="report_vulgar")
    ],
    [InlineKeyboardButton(text="🔙 Duuba", callback_data="feedback_keyboard")]
])


@router.callback_query(F.data == "feedback_keyboard")
async def handle_feedback_main(callback: CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=feedback_keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("report_"))
async def handle_report_reason(callback: CallbackQuery):
    user_id = callback.from_user.id
    reason = callback.data.replace("report_", "")
    reported_id = 0  # Fake ID since we don't track partners yet

    # Log or store report (optional)
    print(f"[FAKE REPORT] User {user_id} reported UNKNOWN user for: {reason}")

    # Optional: Save to DB if needed
    # await db.execute(
    #     "INSERT INTO reports (reporter_id, reported_id, reason) VALUES ($1, $2, $3)",
    #     user_id, reported_id, reason
    # )

    try:
        await callback.message.edit_text(
            "✅ Gabaasni keessan dhiyaateera. Galatoomaa!")
    except Exception as e:
        logging.error(f"Failed to send report confirmation: {e}")


@router.callback_query(F.data == "pay_telegram")
async def choose_telegram_plan(callback: CallbackQuery):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="100 ⭐ / $1.99 a week", callback_data="tgpay_week")
    keyboard.button(text="250 ⭐ / $3.99 a month", callback_data="tgpay_1m")
    keyboard.button(text="1000 ⭐ / $19.99 a year", callback_data="tgpay_1y")
    await callback.message.edit_text("💫 Choose your plan with Telegram Stars:",
                                     reply_markup=keyboard.as_markup())


# Inside your chapa_payment_callback function:
@router.callback_query(F.data == "pay_chapa")
async def choose_chapa_plan(callback: CallbackQuery):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Ji'a 1 - 400 ETB", callback_data="chapa_1m")
    keyboard.button(text="Ji'a 6 - 1500 ETB", callback_data="chapa_6m")
    keyboard.button(text="Waggaa 1 - 2500 ETB", callback_data="chapa_1y")
    await callback.message.edit_text("Karoora Chapa keessan filadhaa:",
                                     reply_markup=keyboard.as_markup())


@router.callback_query(F.data.startswith("chapa_"))
async def handle_chapa_plan(callback: CallbackQuery):
    user_id = callback.from_user.id
    selected_callback_data = callback.data  # Renamed 'plan' to 'selected_callback_data' for clarity
    tx_ref = str(uuid.uuid4())

    prices = {
        "chapa_1m": {
            "amount": 400.00,
            "name": "1 Month VIP"
        },
        "chapa_6m": {
            "amount": 1500.00,
            "name": "6 Months VIP"
        },
        "chapa_1y": {
            "amount": 2500.00,
            "name": "1 Year VIP"
        }
    }

    plan_info = prices.get(selected_callback_data)

    if not plan_info:
        await callback.answer("Invalid plan.", show_alert=True)
        return

    vip_amount = plan_info["amount"]
    vip_plan_name = plan_info["name"]  # This is the human-readable plan name

    await callback.answer("Kaffaltii Chapa qopheessuu...")

    # Prepare Chapa payment request
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "amount": str(vip_amount),  # Use vip_amount here
            "currency": "ETB",
            "email": "salahadinshemsu0@gmail.com",  # Your test email
            "first_name": f"user_{user_id}",
            "tx_ref": tx_ref,
            "callback_url": CHAPA_CALLBACK_URL,
            "return_url": "https://t.me/Selameselambot",
            "customization": {
                "title": "VIP Subscription",
                "description": "Unlock VIP features in the bot"
            }
        }

        async with session.post(CHAPA_BASE_URL, json=payload,
                                headers=headers) as resp:
            text = await resp.text()
            try:
                data = await resp.json()
            except Exception as e:
                await callback.message.answer(
                    "❌ Chapa response is not valid JSON.")
                print("Response text:", text)
                return

            if resp.status == 200 and data.get("status") == "success":
                payment_url = data["data"]["checkout_url"]

                # Save transaction to DB
                conn = None  # Initialize conn
                try:
                    conn = await create_database_connection()
                    # --- FIXED INSERT STATEMENT ---
                    await conn.execute(
                        """
                            INSERT INTO chapa_payments (user_id, tx_ref, plan, amount, status)
                            VALUES ($1, $2, $3, $4::NUMERIC, $5);
                            """,
                        user_id,
                        tx_ref,
                        vip_plan_name,
                        vip_amount,
                        'pending'  # Pass all values
                    )
                    logger.info(
                        f"Payment record for {user_id} ({vip_plan_name}) with tx_ref {tx_ref} saved                           as pending."
                    )
                except Exception as db_error:
                    # Logging the actual error
                    logger.error(
                        f"DB error saving Chapa payment for {user_id}: {db_error}",
                        exc_info=True)
                    await callback.message.answer(
                        "⚠ Kaffaltiin qophaa'e, garuu galmee qusachuu dadhabe. Mee deeggarsa qunnamaa."
                    )
                    return  # Stop execution if DB save fails
                finally:
                    if conn:
                        await conn.close()

                # Send payment link
                builder = InlineKeyboardBuilder()
                builder.button(text="✅ Chaappaa waliin kaffalaa", url=payment_url)
                await callback.message.edit_text(
                    "💳 Kaffaltii keessan haala nageenya qabuun xumuruuf armaan gadii cuqaasaa:",
                    reply_markup=builder.as_markup())
            else:
                await callback.message.answer(
                    "❌ Kaffaltii uumuu dadhabe. Mee booda irra deebi'ii yaalaa.")
                print("Chapa error response:", text)
            # Send payment link


# Assuming this is in db_utils.py or handlers.py

# You'll need your database connection function here
# from .db_utils import create_database_connection # Example import if in a separate file



# --- Your existing calculate_expiry_date function ---
def calculate_expiry_date(plan: str) -> datetime.datetime:
    """
    Calculates the VIP subscription expiry date based on the plan name.
    """
    now = datetime.datetime.now(datetime.timezone.utc) # Use UTC for consistency

    if "1 Week VIP" in plan or "7 Days VIP" in plan: # Added 7 Days VIP for Chapa consistency
        return now + timedelta(days=7)
    elif "1 Month VIP" in plan or "30 Days VIP" in plan: # Added 30 Days VIP
        return now + timedelta(days=30)
    elif "3 Months VIP" in plan or "90 Days VIP" in plan:
        return now + timedelta(days=90)
    elif "6 Months VIP" in plan or "180 Days VIP" in plan:
        return now + timedelta(days=180)
    elif "1 Year VIP" in plan or "365 Days VIP" in plan: # Added 365 Days VIP
        return now + timedelta(days=365)
    logger.warning(f"Unknown VIP plan '{plan}'. Defaulting to 7 days expiry.")
    return now + timedelta(days=7)


async def grant_vip_access(user_id: int, source_type: str, payment_detail: str) -> bool:
    """
    Grants VIP access to a user based on the payment source (Chapa or Telegram Stars)
    and the relevant payment detail (duration for Chapa, payload for Stars).
    This function *must* interact with your database to update VIP status.
    """
    conn = None # Initialize connection
    try:
        logger.info(f"Attempting to grant VIP to user {user_id} via {source_type}.")

        expiry_date = None
        plan_name_for_calc = "" # This will be used to pass to calculate_expiry_date

        if source_type == 'chapa':
            try:
                # payment_detail for Chapa is the duration in days (e.g., "365")
                duration_days = int(payment_detail)
                # For Chapa, we just need to get the "plan name" string for calculate_expiry_date
                # which then determines the timedelta.
                if duration_days == 7: plan_name_for_calc = "7 Days VIP"
                elif duration_days == 30: plan_name_for_calc = "30 Days VIP"
                elif duration_days == 90: plan_name_for_calc = "90 Days VIP"
                elif duration_days == 180: plan_name_for_calc = "180 Days VIP"
                elif duration_days == 365: plan_name_for_calc = "365 Days VIP"
                else:
                    logger.error(f"Unknown Chapa duration: '{duration_days}'. Cannot map to VIP plan.")
                    return False

                expiry_date = calculate_expiry_date(plan_name_for_calc)
                logger.info(f"VIP duration from Chapa: {duration_days} days. Raw expiry: {expiry_date}")

            except ValueError:
                logger.error(f"Invalid duration_days for Chapa: '{payment_detail}'. Cannot grant VIP.")
                return False

        elif source_type == 'telegram_stars':
            # payment_detail for Stars is the payload (e.g., "premium_week_sub")
            if payment_detail == "premium_week_sub":
                plan_name_for_calc = "1 Week VIP"
            elif payment_detail == "premium_month_sub":
                plan_name_for_calc = "1 Month VIP"
            elif payment_detail == "premium_year_sub":
                plan_name_for_calc = "1 Year VIP"
            else:
                logger.error(f"Unknown Telegram Stars payload: '{payment_detail}'. Cannot determine VIP duration.")
                return False

            expiry_date = calculate_expiry_date(plan_name_for_calc)
            logger.info(f"VIP duration from Telegram Stars payload '{payment_detail}' determined as {plan_name_for_calc}. Raw expiry: {expiry_date}")
        else:
            logger.error(f"Unknown payment source type: {source_type}. Cannot grant VIP.")
            return False

        if not expiry_date:
            logger.error(f"Could not determine expiry date for user {user_id}. Source: {source_type}, Detail: {payment_detail}")
            return False

        # --- DATABASE INTERACTION START ---
        # 1. Get DB connection/session
        conn = await create_database_connection()
        if not conn:
            logger.error("Failed to acquire DB connection in grant_vip_access.")
            return False

        # 2. Fetch current user VIP status to determine if we need to extend or set new
        user_record = await conn.fetchrow("SELECT vip_expires_at FROM users WHERE user_id = $1", user_id)
        current_vip_expiry = user_record['vip_expires_at'] if user_record and 'vip_expires_at' in user_record else None

        final_expiry_date = expiry_date # Default to the newly calculated expiry

        if current_vip_expiry and current_vip_expiry > datetime.datetime.now(datetime.timezone.utc):
            # If current VIP is still active, extend from the current expiry date
            # Calculate the duration of the new purchase
            duration_of_new_purchase = expiry_date - datetime.datetime.now(datetime.timezone.utc)
            final_expiry_date = current_vip_expiry + duration_of_new_purchase
            logger.info(f"Extending VIP for user {user_id}. Old expiry: {current_vip_expiry}, Adding: {duration_of_new_purchase}, New final expiry: {final_expiry_date}")
        else:
            # If current VIP is expired or non-existent, set new expiry from now
            final_expiry_date = expiry_date
            logger.info(f"Setting new VIP for user {user_id}. New final expiry: {final_expiry_date}")

        # 3. Update the user's record in your 'users' table
        await conn.execute(
            """
            UPDATE users
            SET is_vip = TRUE,
                vip_plan = $1,
                vip_expires_at = $2,
                notified_before_expiry = FALSE
            WHERE user_id = $3
            """,
            plan_name_for_calc, # This variable now consistently holds the plan string like "1 Week VIP"
            final_expiry_date,
            user_id
        )

        logger.info(f"Database: User {user_id} VIP status updated. New expiry: {final_expiry_date}")
        return True # Return True if DB update was successful

    except Exception as e:
        logger.error(f"Error granting VIP access to user {user_id} (Source: {source_type}, Detail: {payment_detail}): {e}", exc_info=True)
        return False
    finally:
        if conn:
            await conn.close() # Ensure connection is closed
async def check_and_deactivate_expired_vip(bot: Bot):
    """
    Checks for expired VIP subscriptions in the database and deactivates them.
    Also sends expiry notifications if 'notified_before_expiry' is FALSE.
    """
    conn = None
    try:
        conn = await create_database_connection()
        if not conn:
            logger.error("Failed to acquire DB connection in check_and_deactivate_expired_vip.")
            return

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        logger.info(f"Running VIP expiry check at {now_utc}.")

        # --- Phase 1: Notify users before expiry (e.g., 24 hours before) ---
        # Select users who are VIP, not yet notified, and expiring within 24 hours
        expiring_soon_threshold = now_utc + datetime.timedelta(hours=24)

        users_to_notify = await conn.fetch(
            """
            SELECT user_id, vip_expires_at
            FROM users
            WHERE is_vip = TRUE
              AND notified_before_expiry = FALSE
              AND vip_expires_at <= $1
              AND vip_expires_at > $2
            """,
            expiring_soon_threshold,
            now_utc # Ensure it's in the future from now, but within 24 hours
        )

        for user_data in users_to_notify:
            user_id = user_data['user_id']
            expires_at = user_data['vip_expires_at']
            time_until_expiry = expires_at - now_utc

            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ Maallaqni VIP keessan yeroo gadi {int(time_until_expiry.total_seconds() / 3600)} sa'aatiiwwan ({expires_at.strftime('%Y-%m-%d %H:%M UTC')})!\n\n"
                         "Amaloota addaa kan akka walsimsiisaa magaalaa irratti hundaa'e argachuu hin dhabinaa. Haala VIP kee amma haaromsi: /vip",
                    parse_mode=ParseMode.HTML
                )
                await conn.execute(
                    "UPDATE users SET notified_before_expiry = TRUE WHERE user_id = $1", user_id
                )
                logger.info(f"Sent VIP expiry notification to user {user_id}. Expires at {expires_at}.")
            except Exception as e:
                logger.warning(f"Could not send VIP expiry notification to user {user_id}: {e}")
                # Don't mark as notified if message failed, so it can be retried


        # --- Phase 2: Deactivate expired VIPs ---
        # Select users who are VIP, and their expiry date is in the past
        expired_users = await conn.fetch(
            """
            SELECT user_id, vip_plan
            FROM users
            WHERE is_vip = TRUE AND vip_expires_at <= $1
            """,
            now_utc
        )

        for user_data in expired_users:
            user_id = user_data['user_id']
            vip_plan = user_data['vip_plan']
            logger.info(f"Deactivating VIP for user {user_id}. Plan: {vip_plan}. Expiry was in the past.")

            # Update user's VIP status
            await conn.execute(
                """
                UPDATE users
                SET is_vip = FALSE,
                    vip_expires_at = NULL,
                    vip_plan = NULL,
                    notified_before_expiry = FALSE
                WHERE user_id = $1
                """,
                user_id
            )

            # Optionally notify the user they've lost VIP access
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text="😔 VIP subscription keessan yeroon isaa darbee jira. Kana booda amaloota adda ta'an argachuu hin dandeessu.\n\n"
                         "Faayidaa gatii olaanaa hunda banuuf yeroo barbaaddetti qaqqabummaa VIP kee haaromsi: /vip.",
                    parse_mode=ParseMode.HTML
                )
                logger.info(f"Sent VIP expired message to user {user_id}.")
            except Exception as e:
                logger.warning(f"Could not send VIP expired message to user {user_id}: {e}")

    except Exception as e:
        logger.error(f"Error in check_and_deactivate_expired_vip task: {e}", exc_info=True)
    finally:
        if conn:
            await conn.close()

# handlers.py (Add this new function)
# In webhook/handlers.py (at the very top, with other imports)


# --- Chapa Webhook Handler ---
async def chapa_webhook_handler(request: web.Request):
    """
    Handles incoming webhook notifications from Chapa.
    """
    conn = None  # Initialize conn to None for finally block
    try:
        data = await request.json()
        logger.info(f"Received Chapa webhook: {data}")
    except Exception as e:
        logger.error(f"Failed to parse Chapa webhook JSON: {e}")
        return web.Response(status=400, text="Bad Request: Invalid JSON")

    tx_ref = data.get("tx_ref")
    if not tx_ref:
        logger.warning("Chapa webhook received without tx_ref.")
        return web.Response(status=400, text="Bad Request: Missing tx_ref")

    try:
        # Assuming create_database_connection and config are properly set up
        conn = await create_database_connection()
        if not conn:
            logger.error(
                "Failed to connect to DB for Chapa webhook verification.")
            return web.Response(status=500, text="Internal Server Error")

        async with ClientSession(
        ) as session:  # Use ClientSession from aiohttp
            headers = {
                "Authorization": f"Bearer {config.CHAPA_SECRET_KEY}",
                "Content-Type": "application/json"
            }
            async with session.get(f"{config.CHAPA_VERIFY_URL}{tx_ref}",
                                   headers=headers) as resp:
                verify_data = await resp.json()
                logger.info(
                    f"Chapa verification response for {tx_ref}: {verify_data}")

                if resp.status == 200 and \
                   verify_data.get("status") == "success" and \
                   verify_data["data"]["status"] == "success":

                    user_id = None
                    try:
                        # Select user_id and plan from chapa_payments table
                        original_record = await conn.fetchrow(
                            "SELECT user_id, status, plan FROM chapa_payments WHERE tx_ref = $1",
                            tx_ref)

                        if original_record:
                            user_id = original_record['user_id']
                            current_status = original_record['status']
                            plan_name = original_record[
                                'plan']  # Get the plan name from your record

                            if current_status != 'success':
                                # Update chapa_payments table status
                                await conn.execute(
                                    "UPDATE chapa_payments SET status = $1 WHERE tx_ref = $2",
                                    'success', tx_ref)
                                logger.info(
                                    f"Chapa payment for {tx_ref} (user {user_id}) confirmed as SUCCESS and DB chapa_payments updated."
                                )

                                # --- START MODIFICATION: Call grant_vip_access ---
                                # Convert your plan_name (e.g., "1 Month VIP") into its duration in days
                                # This assumes your plan_name directly implies the duration for Chapa.
                                # Alternatively, you could pass the plan_name string itself,
                                # and modify grant_vip_access to extract days if source_type is 'chapa'.
                                # For simplicity, let's map it to days directly here or in config if complex.
                                duration_map = {
                                    "1 Week VIP": 7,
                                    "1 Month VIP":
                                    30,  # Or 31, depending on exact months
                                    "3 Months VIP": 90,
                                    "6 Months VIP": 180,
                                    "1 Year VIP": 365
                                }
                                chapa_duration_days = duration_map.get(
                                    plan_name,
                                    7)  # Default to 7 if plan not found

                                vip_granted = await grant_vip_access(
                                    user_id, 'chapa', str(chapa_duration_days))

                                if vip_granted:
                                    # Get the bot instance from the web app's context
                                    bot_instance = request.app[
                                        "bot"]  # Assuming you pass bot instance to app via setup
                                    # Calculate expiry date to show to user
                                    expiry_date_display = calculate_expiry_date(
                                        plan_name).strftime(
                                            '%Y-%m-%d %H:%M UTC')

                                    try:
                                        await bot_instance.send_message(
                                            chat_id=user_id,
                                            text=
                                            f"🎉 Baga gammaddan! Kan kee 💎{plan_name}💎 VIP subscription hojiirra ooleera! Yeroon isaa ni dhumata **{expiry_date_display}**.",
                                            parse_mode=ParseMode.HTML)
                                        logger.info(
                                            f"VIP activation message sent to user {user_id}."
                                        )
                                    except Exception as send_err:
                                        logger.error(
                                            f"Failed to send VIP activation message to {user_id}: {send_err}"
                                        )
                                else:
                                    logger.error(
                                        f"Failed to grant VIP access via grant_vip_access for user {user_id} after Chapa success."
                                    )
                                    # Potentially send a message to the user about an internal error,
                                    # or log it for manual review.

                                # --- END MODIFICATION ---

                            else:
                                logger.info(
                                    f"Chapa payment {tx_ref} already marked as success. Skipping update."
                                )
                        else:
                            logger.warning(
                                f"Chapa payment for {tx_ref} not found in DB. Cannot update or activate VIP."
                            )

                    except Exception as db_update_err:
                        logger.error(
                            f"DB/VIP update error for Chapa webhook {tx_ref}: {db_update_err}",
                            exc_info=True)
                        return web.Response(
                            status=
                            200,  # Return 200 to Chapa so it doesn't retry endlessly, but log the error internally
                            text=
                            "Webhook received, but internal DB/VIP update failed."
                        )

                else:
                    chapa_data_status = verify_data.get('data', {}).get(
                        'status', 'N/A')
                    logger.warning(
                        f"Chapa verification failed for {tx_ref}. Status: {chapa_data_status}. Response: {verify_data}"
                    )
                    if chapa_data_status == 'failed':
                        await conn.execute(
                            "UPDATE chapa_payments SET status = $1 WHERE tx_ref = $2",
                            'failed', tx_ref)
                        logger.info(
                            f"Chapa payment for {tx_ref} marked as FAILED in DB."
                        )

                    return web.Response(
                        status=200,
                        text=
                        f"Verification failed or not success: {chapa_data_status}"
                    )

    except ClientError as ce:
        logger.error(
            f"Network error during Chapa verification for {tx_ref}: {ce}",
            exc_info=True)
        return web.Response(
            status=500,
            text="Internal Server Error: Network issue with Chapa API")
    except Exception as general_err:
        logger.error(
            f"Unexpected error in Chapa webhook handler for {tx_ref}: {general_err}",
            exc_info=True)
        return web.Response(status=500,
                            text="Internal Server Error: Unexpected issue")
    finally:
        if conn:
            await conn.close()

    return web.Response(status=200, text="Webhook received and processed.")

    # --- Function to set up the Aiogram Dispatcher and aiohttp.web Application ---


WEEKLY_STARS_AMOUNT = 100
WEEKLY_TITLE = "Premium Access (1 Week)"
WEEKLY_DESCRIPTION = "Unlock premium features for 7 days!"
WEEKLY_PAYLOAD = "premium_week_sub"

MONTHLY_STARS_AMOUNT = 250
MONTHLY_TITLE = "Premium Access (1 Month)"
MONTHLY_DESCRIPTION = "Unlock premium features for 30 days!"
MONTHLY_PAYLOAD = "premium_month_sub"

YEARLY_STARS_AMOUNT = 1000
YEARLY_TITLE = "Premium Access (1 Year)"
YEARLY_DESCRIPTION = "Unlock premium features for 365 days!"
YEARLY_PAYLOAD = "premium_year_sub"

PLAN_DETAILS = {
    "tgpay_week": {
        "amount": WEEKLY_STARS_AMOUNT,
        "title": WEEKLY_TITLE,
        "description": WEEKLY_DESCRIPTION,
        "payload": WEEKLY_PAYLOAD
    },
    "tgpay_1m": {
        "amount": MONTHLY_STARS_AMOUNT,
        "title": MONTHLY_TITLE,
        "description": MONTHLY_DESCRIPTION,
        "payload": MONTHLY_PAYLOAD
    },
    "tgpay_1y": {
        "amount": YEARLY_STARS_AMOUNT,
        "title": YEARLY_TITLE,
        "description": YEARLY_DESCRIPTION,
        "payload": YEARLY_PAYLOAD
    },
}

# handlers.py

# ... (other imports and code) ...


@router.callback_query(F.data.startswith("tgpay_"))
async def handle_tgpay_plan_selection(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id

    # 1. Acknowledge the callback immediately
    await callback.answer("Invoice keessan qopheessuu...", show_alert=False)

    plan_callback_data = callback.data  # e.g., "tgpay_week"

    plan_details = PLAN_DETAILS.get(plan_callback_data)
    if not plan_details:
        logger.error(
            f"User {user_id} selected unknown Telegram Stars plan callback: {plan_callback_data}"
        )
        await callback.message.answer(
            "An error occurred: Invalid plan selected. Please try again."
        )  # Send a new message for error
        return

    amount = plan_details["amount"]
    title = plan_details["title"]
    description = plan_details["description"]
    payload = plan_details["payload"]

    try:
        # 2. Delete the message that contained the plan selection keyboard
        # This removes the old message so you don't try to edit it.
        await callback.message.delete()
        logger.info(
            f"Deleted previous plan selection message for user {user_id}.")

        # 3. Send a *new* message confirming invoice readiness
        await bot.send_message(
            chat_id=user_id,
            text=f"💫 Invoice keessan kan **{title}** qophiidha!",
            parse_mode=ParseMode.HTML  # Assuming you want bold text
        )
        logger.info(f"Sent 'invoice ready' message to user {user_id}.")

        # 4. Send the actual invoice
        await bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            currency="XTR",
            prices=[types.LabeledPrice(label=title, amount=amount)
                    ],  # Use types.LabeledPrice
            provider_token="",
            is_flexible=False,
        )
        logger.info(
            f"Invoice for {title} ({amount} Stars) sent to user {user_id}.")

    except Exception as e:
        logger.error(
            f"Failed to send Stars invoice to {user_id} for {plan_callback_data}: {e}",
            exc_info=True)
        # Send a new message to the user if sending the invoice fails
        await bot.send_message(
            chat_id=user_id,
            text=
            "Dhiifama, yeroo invoice kee uumtu wanti tokko dogoggora ta'eera. Mee booda irra deebi'ii yaalaa."
        )


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    user_id = pre_checkout_query.from_user.id
    payload = pre_checkout_query.invoice_payload
    total_amount_stars = pre_checkout_query.total_amount  # Amount user is paying

    logger.info(
        f"Received pre_checkout_query from {user_id} for payload: '{payload}', amount: {total_amount_stars} Stars."
    )

    # Validate the payload against your defined products
    if payload in [WEEKLY_PAYLOAD, MONTHLY_PAYLOAD, YEARLY_PAYLOAD]:
        # Optional: You can verify the amount matches your expectations for the payload
        # expected_amount = next((p['amount'] for k, p in PLAN_DETAILS.items() if p['payload'] == payload), None)
        # if expected_amount is not None and total_amount_stars != expected_amount:
        #     await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Payment amount mismatch.")
        #     logger.warning(f"Pre-checkout amount mismatch for {user_id} with payload '{payload}'. Expected {expected_amount}, got {total_amount_stars}.")
        #     return

        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
        logger.info(
            f"Pre-checkout query from {user_id} for payload '{payload}' answered OK."
        )
    else:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Invalid product or service.")
        logger.warning(
            f"Pre-checkout query from {user_id} for unknown payload '{payload}' answered with error."
        )


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    user_id = message.from_user.id
    payment_info = message.successful_payment
    invoice_payload = payment_info.invoice_payload

    logger.info(f"Successful payment received from {user_id}: {payment_info}")

    # Call grant_vip_access for Telegram Stars payment
    # The 'payment_detail' for Telegram Stars is the payload itself.
    if await grant_vip_access(user_id, 'telegram_stars', invoice_payload):
        # We need to determine the plan name for the message to the user
        plan_name_display = ""
        for key, details in PLAN_DETAILS.items():
            if details["payload"] == invoice_payload:
                plan_name_display = details["title"].replace(
                    "Premium Access (",
                    "").replace(")",
                                "")  # Extract "1 Week", "1 Month", "1 Year"
                break
        if not plan_name_display:
            plan_name_display = "VIP"  # Fallback if not found

        # Calculate expiry date to show to user
        expiry_date_for_display = calculate_expiry_date(
            plan_name_display + " VIP").strftime('%Y-%m-%d %H:%M UTC')

        await message.answer(
            f"🎉 Baga gammaddan! Kan kee 💎**{plan_name_display}**💎VIP subscription hojiirra ooleera! Yeroon isaa ni dhumata **{expiry_date_for_display}**.",
            parse_mode=ParseMode.HTML)
        logger.info(
            f"User {user_id} successfully bought VIP with Stars via payload '{invoice_payload}'."
        )
    else:
        await message.answer(
            "Thank you for your payment, but there was an issue granting your VIP access. Please contact support."
        )
        logger.error(
            f"Failed to grant VIP access for user {user_id} with payload '{invoice_payload}'."
        )
