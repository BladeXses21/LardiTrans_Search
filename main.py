import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app_config import env_config
from handlers import user_handlers, admin_handlers, payment_handlers


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Основна функція для запуску бота.
    """
    if not env_config.TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is not set in .env. Exiting.")
        return

    # Ініціалізація бота з токеном та властивостями за замовчуванням
    bot = Bot(token=env_config.TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    # Використання MemoryStorage для FSM (краще використовувати RedisStorage)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Включення роутерів для обробки повідомлень
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    dp.include_router(payment_handlers.router) # Заглушка, на функціонал оплати

    logger.info("Bot starting...")
    try:
        # Запуск поллінгу для отримання оновлень від Telegram API
        await dp.start_polling(bot)
    finally:
        # Закриття сесії бота при завершенні роботи
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())

