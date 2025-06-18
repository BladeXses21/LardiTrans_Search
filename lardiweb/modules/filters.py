from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery
# from app_config import env_config # Закоментовано, якщо адмін-фільтр поки не потрібен


class AdminFilter(Filter):
    """
    Фільтр для перевірки, чи є користувач адміністратором.
    Наразі заглушка, оскільки ADMIN_USER_IDS не визначено.
    """
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        # Поки що, цей фільтр завжди повертає False, оскільки ADMIN_USER_IDS не визначено.
        # Розкоментуйте та налаштуйте його, коли будете готові до функціоналу адміністратора.
        # return event.from_user.id in env_config.ADMIN_USER_IDS
        return False

