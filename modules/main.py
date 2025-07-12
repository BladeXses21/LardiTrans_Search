import os
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lardiweb.settings')
django.setup()

from modules.notifications_module import notification_checker
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from asgiref.sync import sync_to_async

from modules.app_config import env_config
from modules.handlers import user_handlers, admin_handlers, payment_handlers
from modules.web_server import webapp_handler, cargo_details_proxy_api
from modules.cookie_manager import CookieManager
from modules.handlers.user_handlers import lardi_client
from modules.lardi_api_client import LardiGeoClient

from django.utils import timezone
from users.models import UserProfile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def refresh_cookies_periodically(cookie_manager_instance: CookieManager):
    """
    Фонове завдання для періодичного оновлення Lardi-Trans cookie.
    """
    # Перше оновлення при старті
    logger.info("Performing initial Lardi-Trans cookie refresh...")
    success = await sync_to_async(cookie_manager_instance.refresh_lardi_cookies)()
    if success:
        logger.info("Initial Lardi-Trans cookies refreshed successfully.")
    else:
        logger.warning("Failed to perform initial Lardi-Trans cookie refresh.")

    # Періодичні оновлення
    while True:
        await asyncio.sleep(2 * 3600) # Чекати 2 години (2 * 60 хвилин * 60 секунд)
        logger.info("Attempting to refresh Lardi-Trans cookies periodically...")
        success = await sync_to_async(cookie_manager_instance.refresh_lardi_cookies)()
        if success:
            logger.info("Lardi-Trans cookies refreshed successfully.")
        else:
            logger.warning("Failed to refresh Lardi-Trans cookies.")


async def main() -> None:
    """
    Основна функція для запуску бота та веб-сервера.
    """
    if not env_config.TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is not set in .env. Exiting.")
        return

    if not env_config.WEBAPP_BASE_URL:
        logger.warning("WEBAPP_BASE_URL is not configured in .env. Web App functionality may not work.")

    if not env_config.WEBAPP_API_PROXY_URL:
        logger.warning("WEBAPP_API_PROXY_URL is not configured in .env. Web App proxy functionality may not work.")

    if not env_config.LARDI_USERNAME or not env_config.LARDI_PASSWORD:
        logger.warning("LARDI_USERNAME or LARDI_PASSWORD is not configured in .env. LARDI functionality may not work.")

    cookie_manager = CookieManager()

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

    logger.info("Оновлення notification_time для активних користувачів...")
    current_time = timezone.now()

    @sync_to_async
    def update_all_notification_times(time_to_set):
        # Оновлюємо notification_time лише для користувачів з увімкненими сповіщеннями
        UserProfile.objects.filter(notification_status=True).update(notification_time=time_to_set)
        logger.info(f"Оновлено notification_time до {time_to_set} для всіх користувачів з увімкненими сповіщеннями.")

    await update_all_notification_times(current_time)

    # Запускаємо веб-сервер у фоновому режимі
    web_server_task = asyncio.create_task(web_site.start())
    logger.info("Web server started on http://0.0.0.0:8080")

    # Запускаємо фонову задачу для перевірки сповіщень
    notification_task = asyncio.create_task(notification_checker(bot))
    logger.info("Запущено фонову задачу перевірки сповіщень.")

    # todo - тут потрібно буде зняти коментарій
    cookie_refresh_task = asyncio.create_task(refresh_cookies_periodically(cookie_manager))
    logger.info("Запущено фонову задачу оновлення Lardi-Trans cookie.")

    # try:
    #     get_client = LardiGeoClient()
    #     logger.info("Testing LardiGeoClient.get_geo_data for 'Львів'...")
    #     lviv_data = await get_client.get_geo_data(query="Львів")
    #     logger.info(f"Geographical data for 'Львів': {lviv_data}")
    # except Exception as e:
    #     logger.error(f"Error testing LardiGeoClient: {e}")

    # Запускаємо бота
    logger.info("Бот запущено!")
    await dp.start_polling(bot)

    await web_server_task
    await notification_task

    try:
        await lardi_client.get_proposals(filters=lardi_client.default_filter)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            await cookie_refresh_task

if __name__ == "__main__":


    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot and Web App stopped by user.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")

