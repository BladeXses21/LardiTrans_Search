import os
import django

# Налаштування Django оточення
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lardiweb.settings')
django.setup()

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web  # Імпортуємо web для запуску веб-сервера

from modules.app_config import env_config
from modules.handlers import user_handlers, admin_handlers, payment_handlers
from modules.web_server import webapp_handler, cargo_details_proxy_api  # Імпортуємо функції з web_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Основна функція для запуску бота та веб-сервера.
    """
    if not env_config.TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is not set in .env. Exiting.")
        return

    if not env_config.WEBAPP_BASE_URL or env_config.WEBAPP_BASE_URL == "https://a454-91-245-124-201.ngrok-free.app/webapp/cargo_details.html":
        logger.warning("WEBAPP_BASE_URL is not configured in .env. Web App functionality may not work.")

    if not env_config.WEBAPP_API_PROXY_URL == "https://a454-91-245-124-201.ngrok-free.app/api/cargo_details":
        logger.warning("WEBAPP_API_PROXY_URL is not configured in .env. Web App proxy functionality may not work.")

    # Ініціалізація бота
    bot = Bot(token=env_config.TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    dp.include_router(payment_handlers.router)

    # Ініціалізація веб-додатку aiohttp
    web_app = web.Application()
    # Маршрут для подачі HTML-сторінки Web App (без ID у шляху, ID буде в параметрі запиту)
    web_app.router.add_get('/webapp/cargo_details.html', webapp_handler)
    # Проксі API для отримання даних про вантаж (без ID у шляху, ID буде в параметрі запиту)
    web_app.router.add_get('/api/cargo_details', cargo_details_proxy_api)


    web_runner = web.AppRunner(web_app)
    await web_runner.setup()
    web_site = web.TCPSite(web_runner, '0.0.0.0', 8080)

    # Запускаємо веб-сервер у фоновому режимі
    await web_site.start()
    logger.info("Web server started on http://0.0.0.0:8080")

    # Запускаємо бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot and Web App stopped by user.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

