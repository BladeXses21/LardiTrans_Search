import asyncio
import logging
from aiogram import Bot
from datetime import datetime
from lardi_api_client import LardiClient
from keyboards import get_cargo_details_webapp_keyboard
from utils import date_format  # Assuming utils.py has date_format

logger = logging.getLogger(__name__)

# Ініціалізуємо LardiClient один раз
lardi_client_notifications = LardiClient()


async def start_notification_checker(bot: Bot, db):
    """
    Запускає фонове завдання для періодичної перевірки нових вантажів
    для користувачів з увімкненими сповіщеннями.
    """
    logger.info("Notification checker started.")
    while True:
        try:
            users_to_notify = await get_enabled_notification_users()
            logger.info(f"Checking for new cargoes for {len(users_to_notify)} users.")

            for user_settings in users_to_notify:
                user_id = int(user_settings.get('user_id'))  # Ensure user_id is int for aiogram
                user_filters = user_settings.get('filters', LardiClient.default_filters())
                last_checked_cargo_id = user_settings.get('last_checked_cargo_id')

                logger.info(f"User {user_id}: Checking with filters {user_filters}. Last ID: {last_checked_cargo_id}")

                try:
                    # Завантажуємо дані за фільтрами користувача
                    data = lardi_client_notifications.load_data(user_filters)
                    proposals = data.get("result", {}).get("proposals", [])

                    new_cargoes = []
                    current_max_cargo_id = last_checked_cargo_id

                    for item in proposals:
                        cargo_id = item.get('id')
                        if cargo_id and (last_checked_cargo_id is None or cargo_id > last_checked_cargo_id):
                            new_cargoes.append(item)

                        # Оновлюємо максимальний ID для цього проходу
                        if cargo_id and (current_max_cargo_id is None or cargo_id > current_max_cargo_id):
                            current_max_cargo_id = cargo_id

                    # Sort new cargoes by ID to send them in order
                    new_cargoes.sort(key=lambda x: x.get('id', 0))

                    if last_checked_cargo_id is not None and new_cargoes:  # Тільки якщо це не перший запуск і є нові вантажі
                        for item in new_cargoes:
                            _id = item.get('id', '')
                            status = item.get('status', '')

                            from_data = item.get("waypointListSource", [{}])[0]
                            from_city = from_data.get("town", "Невідомо")
                            from_region = from_data.get("region", "")
                            from_country = from_data.get("countrySign", "")

                            to_data = item.get("waypointListTarget", [{}])[0]
                            to_city = to_data.get("town", "Невідомо")
                            to_region = to_data.get("region", "")
                            to_country = to_data.get("countrySign", "")

                            cargo_name = item.get("gruzName", "—")
                            mass = item.get("gruzMass", "—")
                            payment = item.get("payment", "—")
                            payment_form = ", ".join(pf.get("name", "") for pf in item.get("paymentForms", []))
                            distance_km = round(item.get("distance", 0) / 1000) if item.get("distance") else '—'

                            block = f"🆕 *Новий вантаж!* 🆕\n"
                            block += f"📦 ID: {_id} | {status}\n"
                            block += f"🕒 {date_format(item.get('dateFrom', ''))} → {date_format(item.get('dateTo', ''))}\n"
                            block += f"📌 Завантаження: {from_city}, {from_region} ({from_country})\n"
                            block += f"📍 Вивантаження: {to_city}, {to_region} ({to_country})\n"
                            block += f"📦 Вантаж: {cargo_name}\n"
                            block += f"⚖️ Вага: {mass}\n"
                            block += f"💰 Оплата: {payment} ({payment_form})\n"
                            if distance_km != '—':
                                block += f"🛣️ Відстань: {distance_km} км\n"

                            await bot.send_message(
                                chat_id=user_id,
                                text=block,
                                reply_markup=get_cargo_details_webapp_keyboard(_id),
                                parse_mode="Markdown"
                            )
                            logger.info(f"Sent new cargo {_id} to user {user_id}")

                    # Оновлюємо last_checked_cargo_id лише якщо були пропозиції
                    if proposals and current_max_cargo_id is not None:
                        await update_user_setting(user_id, "last_checked_cargo_id", current_max_cargo_id)
                        logger.info(f"Updated last_checked_cargo_id for user {user_id} to {current_max_cargo_id}")

                except Exception as e:
                    logger.error(f"Error checking or sending notifications for user {user_id}: {e}")
                    # Continue to next user even if one fails

        except Exception as e:
            logger.error(f"Error in main notification checker loop: {e}")

        # Чекаємо 5 хвилин перед наступною перевіркою
        await asyncio.sleep(300)  # 300 seconds = 5 minutes

