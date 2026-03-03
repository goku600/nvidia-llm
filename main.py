"""
Main entry point for the NVIDIA AI Telegram Bot.
Runs as a webhook server on Render free tier.
"""
import logging
import asyncio
from aiohttp import web

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, PORT, HOST
from handlers import (
    cmd_start,
    cmd_clear,
    cmd_privacy,
    cmd_help,
    handle_text,
    handle_photo,
    handle_document,
    handle_callback_query,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def health(request):
    """Health check endpoint — keeps Render from spinning down (use UptimeRobot)."""
    return web.Response(text="OK")


async def main():
    # Build the bot application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("privacy", cmd_privacy))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Set webhook
    webhook_path = f"/webhook/{TELEGRAM_BOT_TOKEN}"
    full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}{webhook_path}"

    await app.bot.set_webhook(
        url=full_webhook_url,
        allowed_updates=Update.ALL_TYPES,
    )
    logger.info(f"Webhook set to: {full_webhook_url}")

    # Build aiohttp web app
    web_app = web.Application()
    web_app.router.add_get("/", health)
    web_app.router.add_get("/health", health)

    # Register the PTB webhook handler
    async def telegram_webhook(request):
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
        return web.Response(text="OK")

    web_app.router.add_post(webhook_path, telegram_webhook)

    # Initialize and start the bot application
    await app.initialize()
    await app.start()

    logger.info(f"Bot started. Listening on {HOST}:{PORT}")

    # Start aiohttp server
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()

    # Run forever
    try:
        await asyncio.Event().wait()
    finally:
        await app.stop()
        await app.shutdown()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
