import asyncio
import logging
from typing import List, Dict, Any
import re

from django.utils import timezone

from aiogram import Bot
from aiogram.enums import ParseMode
from asgiref.sync import sync_to_async

from users.models import UserProfile
from modules.lardi_api_client import lardi_notification_client
from modules.keyboards import get_cargo_details_webapp_keyboard
from modules.app_config import settings_manager
from modules.utils import date_format

logger = logging.getLogger(__name__)

NOTIFICATION_CHECK_INTERVAL = 30  # 5 хвилин у секундах


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

    from_address = str(cargo.get("waypointListSource", [{}])[0].get("address", "-"))
    to_address = str(cargo.get("waypointListTarget", [{}])[0].get("address", "-"))
    message_parts = {
        "cargo_id": str(cargo_id),
        "dateFrom": str(date_format(cargo.get("dateFrom", "-"))),
        "dateTo": str(date_format(cargo.get("dateTo", "-"))),
        "dateCreate": str(date_format(cargo.get("dateCreate", "-"))),
        "dateEdit": str(date_format(cargo.get("dateEdit", "-"))),

        "from_town": str(cargo.get("waypointListTarget", [{}])[0].get("town", "-")),
        "from_region": str(cargo.get("waypointListTarget", [{}])[0].get("region", "-")),
        "from_countrySign": str(cargo.get("waypointListTarget", [{}])[0].get("countrySign", "-")),
        "from_address": from_address if not None else "Пусто",

        "to_town": str(cargo.get("waypointListTarget", [{}])[0].get("town", "-")),
        "to_region": str(cargo.get("waypointListTarget", [{}])[0].get("region", "-")),
        "to_countrySign": str(cargo.get("waypointListTarget", [{}])[0].get("countrySign", "-")),
        "to_address": to_address if not None else "Пусто",

        "loadTypes": str(cargo.get("loadTypes", "-")),
        "gruzName": str(cargo.get("gruzName", "-")),
        "gruzMass": str(cargo.get("gruzMass", "-")),
        "gruzVolume": str(cargo.get("gruzVolume", "-")),
        "payment": str(cargo.get("payment", "-")),
        "paymentForms": ", ".join(pf.get("name", "") for pf in cargo.get("paymentForms", [])),
        "distance": round(cargo.get("distance", 0) / 1000) if cargo.get("distance") else '—',
        "repeated": "🔁 Повторюваний" if cargo.get("repeated") else "",
    }

    escaped_message_parts = {k: escape_markdown_v2(v) for k, v in message_parts.items()}

    template = settings_manager.get("text_notification_new_cargo")

    try:
        message_text = template.format(
            **escaped_message_parts
        )
    except KeyError as e:
        logger.error(
            f"Помилка форматування шаблону 'text_notification_new_cargo'. Відсутня змінна {e} у даних вантажу або escape_markdown_v2: {cargo}. Шаблон: {template}")
        return await bot.send_message(
            chat_id=user_profile.telegram_id,
            text="Не вдалось сформувати повідомлення про новий вантаж.",
            parse_mode=ParseMode.HTML,
        )

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
            logger.info("Запуск періодичної перевірки вантажів для сповіщень...")
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
                            await asyncio.sleep(0.5)
                            await send_cargo_notification(bot, user_profile, cargo)
                    else:
                        logger.info(f"Не знайдено нових вантажів для {user_profile.user.username}.")


                except Exception as e:
                    logger.error(f"Помилка при перевірці сповіщень для користувача {user_profile.user.username}: {e}")

                @sync_to_async
                def update_user_notification_time(user_prof_obj, time_to_set):
                    user_prof_obj.notification_time = time_to_set
                    user_prof_obj.save(update_fields=["notification_time"])
                    local_time_for_log = timezone.localtime(time_to_set)
                    logger.info(f"Оновлено notification_time до {local_time_for_log} для користувача {user_prof_obj.user.username}.")

                await update_user_notification_time(user_profile, timezone.now())

        except Exception as e:
            logger.error(f"FATAL ERROR in notification_checker: {e}", exc_info=True)

        await asyncio.sleep(NOTIFICATION_CHECK_INTERVAL)  # Чекаємо 5 хвилин
