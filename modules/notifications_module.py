# modules/notifications_module.py
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

from aiogram import Bot
from asgiref.sync import sync_to_async
from django.db.models import Q

from users.models import UserProfile
from modules.lardi_api_client import lardi_notification_client
from modules.keyboards import get_cargo_details_webapp_keyboard
from modules.app_config import settings_manager, env_config
from modules.utils import add_line, date_format

logger = logging.getLogger(__name__)

NOTIFICATION_CHECK_INTERVAL = 50  # 5 хвилин у секундах


async def send_cargo_notification(bot: Bot, user_profile: UserProfile, cargo: Dict[str, Any]):
    """
    Надсилає користувачу повідомлення про новий вантаж.
    """
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

    # Формування повідомлення
    message_text = settings_manager.get("text_notification_new_cargo").format(cargo_id=cargo_id)

    message_text += add_line(settings_manager.get("text_from_short"), cargo.get("from").get("name"))
    message_text += add_line(settings_manager.get("text_to_short"), cargo.get("to").get("name"))

    mass = cargo.get("mass")
    if mass:
        message_text += add_line(settings_manager.get("text_mass"), f"{mass} т", important=True)

    volume = cargo.get("volume")
    if volume:
        message_text += add_line(settings_manager.get("text_volume"), f"{volume} м³", important=True)

    payment = cargo.get("payment")
    if payment and payment.get("value"):
        payment_value = payment.get("value")
        payment_currency = payment.get("currencyName")
        message_text += add_line(settings_manager.get("text_payment"), f"{payment_value} {payment_currency}", important=True)
    else:
        message_text += add_line(settings_manager.get("text_payment"), settings_manager.get("text_not_set"))

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

            message_text += add_line(settings_manager.get("text_created"), date_format(created_at_str))
        except ValueError as e:
            logger.warning(f"Не вдалося розпарсити дату створення вантажу '{created_at_str}': {e}")


    try:
        await bot.send_message(
            chat_id=user_profile.telegram_id,
            text=message_text,
            reply_markup=get_cargo_details_webapp_keyboard(cargo_id),
            parse_mode="Markdown"
        )
        logger.info(f"Надіслано сповіщення про вантаж {cargo_id} користувачу {user_profile.user.username}")
    except Exception as e:
        logger.error(f"Не вдалося надіслати сповіщення користувачу {user_profile.user.username} (ID: {user_profile.telegram_id}): {e}")


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
                            await send_cargo_notification(bot, user_profile, cargo)
                    else:
                        logger.info(f"Не знайдено нових вантажів для {user_profile.user.username}.")

                except Exception as e:
                    logger.error(f"Помилка при перевірці сповіщень для користувача {user_profile.user.username}: {e}")

        except Exception as e:
            logger.error(f"FATAL ERROR in notification_checker: {e}", exc_info=True)

        await asyncio.sleep(NOTIFICATION_CHECK_INTERVAL) # Чекаємо 5 хвилин