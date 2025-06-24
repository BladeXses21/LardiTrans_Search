# modules/notifications_module.py
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import re

from aiogram import Bot
from asgiref.sync import sync_to_async

from users.models import UserProfile
from modules.lardi_api_client import lardi_notification_client
from modules.keyboards import get_cargo_details_webapp_keyboard
from modules.app_config import settings_manager
from modules.utils import add_line, date_format

logger = logging.getLogger(__name__)

NOTIFICATION_CHECK_INTERVAL = 50  # 5 хвилин у секундах


def escape_markdown_v2(text: str) -> str:
    """
    Екранує всі спецсимволи для Telegram MarkdownV2.
    """
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r'_*\[\]()~`>#+-=|{}.!'
    return re.sub(r'([%s])' % re.escape(escape_chars), r'\\\1', text)


async def send_cargo_notification(bot: Bot, user_profile: UserProfile, cargo: Dict[str, Any]):
    """
    Надсилає користувачу повідомлення про новий вантаж.
    """
    if not isinstance(cargo, dict):
        logger.error(f"CARGO IS NOT DICT! {cargo}")
        return
    cargo_id = cargo.get("id")
    if not cargo_id:
        logger.error(f"Відсутній ID вантажу для сповіщення користувача {user_profile.user.username}")
        return

    # Перевіряємо, чи вантаж вже був пропущений користувачем
    cargo_skip_list = user_profile.cargo_skip if user_profile.cargo_skip else []
    if cargo_id in cargo_skip_list:
        logger.info(f"Вантаж {cargo_id} вже був надісланий або пропущений для {user_profile.user.username}. Пропускаємо.")
        return

    # Оновлюємо cargo_skip, щоб не надсилати цей вантаж знову
    @sync_to_async
    def update_cargo_skip(user_profile_obj, cargo_id_to_add):
        if user_profile_obj.cargo_skip is None:
            user_profile_obj.cargo_skip = []
        if cargo_id_to_add not in user_profile_obj.cargo_skip:
            user_profile_obj.cargo_skip.append(cargo_id_to_add)
            user_profile_obj.save(update_fields=['cargo_skip'])
            logger.info(f"Додано {cargo_id_to_add} до cargo_skip для {user_profile_obj.user.username}")

    await update_cargo_skip(user_profile, cargo_id)

    # Формування повідомлення з екранацією ВСІХ динамічних даних!
    template = settings_manager.get("text_notification_new_cargo")
    # Формування повідомлення
    message_text = template.format(
        cargo_id=escape_markdown_v2(cargo_id)
    )

    created_at_str = cargo.get("createDate")
    if created_at_str:
        try:
            # Парсимо дату з урахуванням різних форматів і часових поясів
            if '.' in created_at_str and '+' in created_at_str:
                dt_object = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%S.%f%z')
            elif '.' in created_at_str:
                 dt_object = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%S.%f')
                 dt_object = dt_object.replace(tzinfo=timezone.utc) # Припускаємо UTC, якщо немає зони
            elif '+' in created_at_str:
                dt_object = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%S%z')
            else:
                dt_object = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M:%S')
                dt_object = dt_object.replace(tzinfo=timezone.utc) # Припускаємо UTC, якщо немає зони

            message_text += add_line(
                escape_markdown_v2(settings_manager.get("text_created")),
                escape_markdown_v2(date_format(created_at_str)),
            )
        except ValueError as e:
            logger.warning(f"Не вдалося розпарсити дату створення вантажу '{created_at_str}': {e}")

    try:
        await bot.send_message(
            chat_id=user_profile.telegram_id,
            text=message_text,
            reply_markup=get_cargo_details_webapp_keyboard(cargo_id),
            parse_mode="MarkdownV2"
        )
        logger.info(f"Надіслано сповіщення про вантаж {cargo_id} користувачу {user_profile.user.username}")
    except Exception as e:
        logger.error(
            f"Не вдалося надіслати сповіщення користувачу {user_profile.user.username} (ID: {user_profile.telegram_id}): {e}\n"
            f"Текст повідомлення: {message_text}"
        )

@sync_to_async
def get_active_notification_users() -> List[UserProfile]:
    """
    Повертає список UserProfile, у яких увімкнено сповіщення.
    """
    return list(UserProfile.objects.select_related("user").filter(
        notification_status=True,
        notification_time__isnull=False
    ))


async def notification_checker(bot: Bot):
    """
    Основна функція, яка періодично перевіряє наявність нових вантажів
    для всіх користувачів з увімкненими сповіщеннями.
    """
    while True:
        try:
            logger.info("Запуск перевірки сповіщень...")
            users_to_notify = await get_active_notification_users()
            logger.info(f"Користувачі для сповіщень (id): {[u.id for u in users_to_notify]}")

            for user_profile in users_to_notify:
                logger.info(f"user_id={user_profile.id}, telegram_id={user_profile.telegram_id}")  # Не чіпаємо user.username тут
                last_notification_time = user_profile.notification_time
                if not last_notification_time:
                    logger.warning(f"Користувач {user_profile.user.username} має увімкнені сповіщення, але відсутній notification_time. Пропускаємо.")
                    continue

                try:
                    # Отримуємо нові вантажі для користувача, використовуючи його фільтри
                    new_cargos = await lardi_notification_client.get_new_offers(
                        user_profile.telegram_id,
                        last_notification_time
                    )

                    if new_cargos:
                        logger.info(f"Знайдено {len(new_cargos)} нових вантажів для {user_profile.user.username}.")
                        for cargo in new_cargos:
                            await asyncio.sleep(0.3)
                            await send_cargo_notification(bot, user_profile, cargo)
                    else:
                        logger.info(f"Не знайдено нових вантажів для {user_profile.user.username}.")

                except Exception as e:
                    logger.error(f"Помилка при перевірці сповіщень для користувача {user_profile.user.username}: {e}")

        except Exception as e:
            logger.error(f"FATAL ERROR in notification_checker: {e}", exc_info=True)

        await asyncio.sleep(NOTIFICATION_CHECK_INTERVAL) # Чекаємо 5 хвилин