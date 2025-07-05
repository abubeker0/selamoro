import asyncio
import logging
import datetime # Import datetime for use in the periodic check
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

import webhook.config as config
import webhook.handlers as handlers # This import is good!

logger = logging.getLogger(__name__)

# --- New: Define the periodic VIP check task ---
async def periodic_vip_check(bot: Bot):
    """
    Runs the VIP expiry check function periodically.
    """
    while True:
        try:
            # Call the function from your handlers module
            await handlers.check_and_deactivate_expired_vip(bot)
        except Exception as e:
            logger.error(f"Error in periodic_vip_check loop: {e}", exc_info=True)
        # Run every 6 hours (adjust as needed)
        # For testing, you might reduce this to a smaller value like 60 seconds
        await asyncio.sleep(6 * 3600) # 6 hours in seconds

# --- Function to set up the Aiogram Dispatcher and aiohttp.web Application ---
async def create_bot_app(bot: Bot) -> tuple[web.Application, Dispatcher]:
    """
    Creates and configures the aiohttp web application and Aiogram Dispatcher.
    This function prepares the bot's webhooks and routing.
    """
    dp = Dispatcher()
    dp.include_router(handlers.router) # Access router via 'handlers.router'

    # Create aiohttp web application
    app = web.Application()
    app["bot"] = bot

    # Aiogram's webhook endpoint (for receiving updates from Telegram)
    request_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    request_handler.register(app, path="/bot") # Registers the POST route for Telegram updates

    # Add your custom Chapa webhook handler
    app.router.add_post(config.WEBHOOK_PATH, handlers.chapa_webhook_handler) # Access handler via 'handlers.chapa_webhook_handler'

    logger.info("Aiogram Dispatcher and aiohttp web application configured.")
    return app, dp


async def main():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    bot = Bot(token=config.BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # --- CORRECTED CALL FOR create_tables() ---
    await handlers.create_tables() # Access via 'handlers.'
    logger.info("Database tables created or already exist.") # Added confirmation log
    # --- END CORRECTED CALL ---

    app, dp = await create_bot_app(bot)

    await bot.delete_webhook(drop_pending_updates=True)

    if not config.BASE_WEBHOOK_URL:
        logger.error(
            "BASE_WEBHOOK_URL is not set. This is required for webhooks.")
        logger.warning(
            "Falling back to long polling for development. Set WEBHOOK_URL for production."
        )
        await dp.start_polling(bot)
        return

    telegram_webhook_url = f"{config.BASE_WEBHOOK_URL}/bot"
    logger.info(f"Setting Telegram webhook to: {telegram_webhook_url}")
    await bot.set_webhook(url=telegram_webhook_url)

    # --- New: Start the background VIP expiry check task ---
    asyncio.create_task(periodic_vip_check(bot))
    logger.info("Started periodic VIP expiry check task.")
    # --- End new section ---

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner,
                       host=config.WEB_SERVER_HOST,
                       port=config.WEB_SERVER_PORT)
    logger.info(
        f"Starting web server on {config.WEB_SERVER_HOST}:{config.WEB_SERVER_PORT}"
    )
    await site.start()

    # Keep the main task running indefinitely
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
