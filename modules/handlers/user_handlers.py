import json

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.state import State
from typing import Optional, List, Union, Any, Dict

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from logger import logger

from modules.app_config import settings_manager, env_config
from modules.keyboards import (
    get_main_menu_keyboard,
    get_back_to_main_menu_button,
    get_cancel_keyboard,
    get_filter_main_menu_keyboard,
    get_cargo_params_filter_keyboard,
    get_load_types_filter_keyboard,
    get_reset_filters_confirm_keyboard,
    get_back_to_filter_main_menu_button,
    get_cargo_details_webapp_keyboard,
    get_numeric_input_keyboard,
    get_payment_forms_keyboard,
    get_boolean_options_keyboard,
    get_notification_settings_keyboard, get_country_options_keyboard, get_direction_filter_menu_keyboard,
)
from modules.fsm_states import LardiForm, FilterForm
from modules.lardi_api_client import LardiClient, LardiOfferClient

from modules.utils import date_format, add_line, user_filter_to_dict, boolean_options_names, ALL_COUNTRIES_FOR_SELECTION, COUNTRIES_PER_PAGE
from datetime import datetime, timezone, timedelta

# --- Django моделі ---
from django.contrib.auth.models import User
from filters.models import LardiSearchFilter
from users.models import UserProfile
from asgiref.sync import sync_to_async

# ------

router = Router()

# Ініціалізація клієнтів Lardi
lardi_client = LardiClient()
lardi_offer_client = LardiOfferClient()

INITIAL_NOTIFICATION_OFFSET_MINUTES = 5  # Вантажі за останні 10 хвилин


# Ім'я бота для посилання на Web App
# BOT_USERNAME = 'LardiSearch_bot'


# Допоміжна функція для отримання фільтрів користувача
async def _get_or_create_lardi_filter(telegram_id: int) -> LardiSearchFilter:
    """
    Отримує об'єкт LardiSearchFilter для даного Telegram ID.
    Якщо об'єкт не існує, створює його з default_filters.
    """
    # Змінено: асинхронні методи ORM await-уємо напряму
    lardi_filter_obj = await LardiSearchFilter.objects.filter(user__telegram_id=telegram_id).afirst()
    if not lardi_filter_obj:
        user_profile, created = await UserProfile.objects.aget_or_create(telegram_id=telegram_id)
        lardi_filter_obj = await LardiSearchFilter.objects.acreate(user=user_profile, **lardi_client.default_filters())
        logger.info(f"Створено новий LardiSearchFilter для користувача {telegram_id}")
    return lardi_filter_obj


@sync_to_async
def update_user_notification_status(user_profile: UserProfile, status: bool):
    user_profile.notification_status = status
    user_profile.notification_time = datetime.now(timezone.utc) if status else None
    user_profile.cargo_skip = []
    user_profile.save(update_fields=['notification_status', 'notification_time', 'cargo_skip'])


@sync_to_async
def get_user_profile(telegram_id: int) -> Optional[UserProfile]:
    try:
        return UserProfile.objects.get(telegram_id=telegram_id)
    except UserProfile.DoesNotExist:
        return None


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """
    Обробник команди /start.
    Реєструє користувача та створює для нього фільтр за замовчуванням, якщо їх ще немає.
    """
    await state.clear()  # Очищуємо стан FSM

    telegram_id = message.from_user.id
    username = message.from_user.username or f"telegram_user_{telegram_id}"

    try:
        # 1. Спочатку створюємо або отримуємо Django User
        django_user, user_created = await User.objects.aget_or_create(
            username=username,
            defaults={
                'first_name': message.from_user.first_name or '',
                'last_name': message.from_user.last_name or '',
            }
        )

        # Якщо user_created дорівнює False, але username змінився, оновлюємо
        if not user_created and await sync_to_async(lambda: django_user.username)() != username:
            django_user.username = username
            await sync_to_async(django_user.asave)()

        # 2. Потім створюємо або отримуємо UserProfile, використовуючи django_user
        user_profile, profile_created = await UserProfile.objects.aget_or_create(
            telegram_id=telegram_id,
            defaults={'user': django_user}
        )
        if not profile_created and await sync_to_async(lambda: user_profile.user)() != django_user:
            user_profile.user = django_user
            await sync_to_async(user_profile.asave)()

        notifications_enabled = user_profile.notification_status

        # Повідомлення користувачу
        if user_created or profile_created:
            await message.answer(settings_manager.get("user_create"), reply_markup=get_main_menu_keyboard(notifications_enabled))
        else:
            await message.answer(settings_manager.get("user_comeback"), reply_markup=get_main_menu_keyboard(notifications_enabled))

        # 3. Перевіряємо, чи існує LardiSearchFilter для цього користувача
        await LardiSearchFilter.objects.aget_or_create(user=user_profile)

    except Exception as e:
        await message.answer(f"Виникла помилка під час реєстрації: {e}")
        print(f"Error during user registration: {e}")
        return


@router.callback_query(F.data == "start_menu")
async def cb_start_menu(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для повернення в головне меню.
    """
    await state.clear()
    user_profile = await get_user_profile(callback.from_user.id)
    notifications_enabled = user_profile.notification_status if user_profile else False
    await callback.message.edit_text(
        settings_manager.get("text_welcome_message"),
        reply_markup=get_main_menu_keyboard(notifications_enabled)
    )
    await callback.answer()


# --- Обробники для сповіщень ---
@router.callback_query(F.data == "notification_settings")
async def cb_notification_settings(callback: CallbackQuery):
    user_profile = await get_user_profile(callback.from_user.id)
    if not user_profile:
        await callback.message.answer(settings_manager.get("text_error_user_not_found"))
        await callback.answer()
        return

    status_text = (
        settings_manager.get("text_notifications_status_enabled")
        if user_profile.notification_status
        else settings_manager.get("text_notifications_status_disabled")
    )
    await callback.message.edit_text(
        status_text,
        reply_markup=get_notification_settings_keyboard(user_profile.notification_status)
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_notifications")
async def cb_toggle_notifications(callback: CallbackQuery):
    user_profile = await get_user_profile(callback.from_user.id)
    if not user_profile:
        await callback.message.answer(settings_manager.get("text_error_user_not_found"))
        await callback.answer()
        return

    new_status = not user_profile.notification_status
    await update_user_notification_status(user_profile, new_status)

    confirmation_text = (
        settings_manager.get("text_notifications_toggle_success_enabled")
        if new_status
        else settings_manager.get("text_notifications_toggle_success_disabled")
    )

    # Оновлюємо головне меню з новим статусом сповіщень
    main_menu_keyboard = get_main_menu_keyboard(new_status)
    try:
        await callback.message.edit_text(
            settings_manager.get("text_welcome_message"),  # Можна залишити "Головне меню" або щось більш інформативне
            reply_markup=main_menu_keyboard
        )
    except TelegramBadRequest:
        # Якщо повідомлення не змінилось, просто оновлюємо клавіатуру
        await callback.message.edit_reply_markup(reply_markup=main_menu_keyboard)

    await callback.answer(confirmation_text)


@router.callback_query(F.data == "search_offers")
async def cb_search_offers(callback: CallbackQuery):
    """
    Обробник для кнопки "Пошук вантажів".
    Тут буде реалізована логіка пошуку вантажів за замовчуванням
    або з використанням встановлених фільтрів користувача.
    """
    await callback.answer(text="Шукаю вантажі...", show_alert=False)

    try:
        telegram_id = callback.from_user.id

        user_profile = await UserProfile.objects.aget(telegram_id=telegram_id)

        lardi_filter_obj = await LardiSearchFilter.objects.aget(user=user_profile)

        user_filters = user_filter_to_dict(lardi_filter_obj) if user_filter_to_dict(lardi_filter_obj) else lardi_client.filters

        data = await lardi_client.get_proposals(filters=user_filters)
        results = data.get("result", {}).get("proposals", {})

        if not results:
            await callback.message.answer("🔍 Нічого не знайдено за вашими критеріями.", reply_markup=get_back_to_main_menu_button())
            return

        # Відправляємо максимум 5 вантажів (як у вашому прикладі)
        for i, item in enumerate(results[:5], 1):
            _id = item.get('id', '')
            status = item.get('status', '')

            from_data = item.get("waypointListSource", [{}])[0]
            from_city = from_data.get("town", "Невідомо")
            from_region = from_data.get("region", "")
            from_country = from_data.get("countrySign", "")
            from_address = from_data.get('address', "")

            to_data = item.get("waypointListTarget", [{}])[0]
            to_city = to_data.get("town", "Невідомо")
            to_region = to_data.get("region", "")
            to_country = to_data.get("countrySign", "")
            to_address = to_data.get("address", "")

            cargo = item.get("gruzName", "—")
            mass = item.get("gruzMass", "—")
            volume = item.get("gruzVolume", "—")
            load_type = item.get("loadTypes", "—")
            payment = item.get("payment", "—")
            payment_form = ", ".join(pf.get("name", "") for pf in item.get("paymentForms", []))
            distance_km = round(item.get("distance", 0) / 1000) if item.get("distance") else '—'
            repeated_status = "🔁 Повторюваний" if item.get("repeated") else ""

            # Основна шапка
            block = f"📦 #{i} | ID: {_id} | {status}\n"
            block += f"🕒 {date_format(item.get('dateFrom', ''))} → {date_format(item.get('dateTo', ''))}\n"
            block += f"📅 Ств.: {date_format(item.get('dateCreate', ''))} | Змін.: {date_format(item.get('dateEdit', ''))}\n"
            # Місце відвантаження
            block += add_line("📌 Завантаження: ", f"{from_city}, {from_region} ({from_country})", important=True)
            block += add_line("◽ Адреса: ", f"{from_address}")
            # Місце призначення
            block += add_line("📍 Вивантаження: ", f"{to_city}, {to_region} ({to_country})", important=True)
            block += add_line("◾ Адреса: ", f"{to_address}")
            block += add_line("🚚 Тип завантаження: ", load_type, important=True)
            # Вантаж
            block += add_line("📦 Вантаж: ", cargo)
            block += add_line("⚖️ Вага: ", mass)
            block += add_line("📐 Обʼєм: ", volume)
            # Оплата
            block += add_line("💰 Оплата: ", f"{payment} ({payment_form})", important=True)
            # Відстань і повтор
            if distance_km != '—':
                block += f"🛣️ Відстань: {distance_km} км\n"
            if repeated_status:
                block += f"{repeated_status}\n"

            # Відправка кожного із вантажів окремо із webapp button
            await callback.message.answer(block, reply_markup=get_cargo_details_webapp_keyboard(_id), parse_mode="Markdown")

        await callback.message.answer("Завершено показ вантажів.", reply_markup=get_back_to_main_menu_button())

    except Exception as e:
        await callback.message.answer(f"❌ Сталася помилка при завантаженні вантажів: {e}", reply_markup=get_back_to_main_menu_button())
    finally:
        await callback.answer()


@router.callback_query(F.data == "view_offer_by_id")
async def cb_view_offer_by_id(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для кнопки "Переглянути вантаж за ID".
    Запитує ID вантажу у користувача.
    """
    await state.set_state(LardiForm.waiting_for_offer_id)
    await callback.message.edit_text(
        settings_manager.get("text_enter_offer_id"),
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(LardiForm.waiting_for_offer_id)
async def process_offer_id(message: Message, state: FSMContext):
    """
    Обробник отримання ID вантажу від користувача.
    """
    try:
        offer_id = int(message.text)
        await message.answer("Завантажую інформацію про вантаж...")

        # Використання вашого класу LardiOfferClient для отримання інформації
        data = lardi_offer_client.get_offer(offer_id)

        if data:
            cargo_data = data.get('cargo', {})
            if cargo_data:
                # Формуємо красивий рядок для виводу в Telegram
                response_text = f"📄 Деталі вантажу (ID: {offer_id})\n" + "=" * 40 + "\n"
                for key, value in cargo_data.items():
                    if isinstance(value, (dict, list)):
                        # Для вкладених об'єктів/списків виводимо їх як JSON рядок
                        try:
                            response_text += f"{key}: {json.dumps(value, ensure_ascii=False, indent=2)}\n"
                        except TypeError:  # На випадок, якщо об'єкт не серіалізується
                            response_text += f"{key}: {str(value)}\n"
                    else:
                        response_text += f"{key}: {value}\n"
                response_text += "=" * 40
                await message.answer(response_text, reply_markup=get_back_to_main_menu_button())
            else:
                await message.answer(settings_manager.get("text_offer_not_found"), reply_markup=get_back_to_main_menu_button())
        else:
            await message.answer(settings_manager.get("text_offer_not_found"), reply_markup=get_back_to_main_menu_button())

    except ValueError:
        await message.answer(
            settings_manager.get("text_invalid_offer_id"),
            reply_markup=get_cancel_keyboard()
        )
    except Exception as e:
        await message.answer(f"❌ Сталася помилка: {e}", reply_markup=get_back_to_main_menu_button())
    finally:
        await state.clear()


@router.callback_query(F.data == "update_lardi_cookie")
async def cb_update_lardi_cookie(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для кнопки "Оновити Cookie Lardi".
    Запитує новий cookie у користувача.
    """
    await state.set_state(LardiForm.waiting_for_new_cookie)
    await callback.message.edit_text(
        settings_manager.get("text_enter_new_cookie"),
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_action")
async def cb_cancel_action(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для кнопки "Відмінити" в будь-якому стані FSM.
    """
    await state.clear()
    user_profile = await get_user_profile(callback.from_user.id)
    notifications_enabled = user_profile.notification_status if user_profile else False
    await callback.message.edit_text(
        settings_manager.get("text_welcome_message"),
        reply_markup=get_main_menu_keyboard(notifications_enabled)
    )
    await callback.answer()


@router.callback_query(F.data == "change_filters")
async def cb_change_filters(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для кнопки "Змінити фільтри".
    Переводить у головне меню фільтрів.
    """
    await state.set_state(FilterForm.main_menu)
    await callback.message.edit_text(
        settings_manager.get("text_filter_main_menu"),
        reply_markup=get_filter_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_filter_main_menu")
async def cb_back_to_filter_main_menu(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для повернення в головне меню фільтрів з підменю.
    """
    await state.set_state(FilterForm.main_menu)
    await callback.message.edit_text(
        settings_manager.get("text_filter_main_menu"),
        reply_markup=get_filter_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "filter_directions_menu")
async def cb_filter_directions_menu(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для переходу в меню налаштувань напрямків.
    """
    await state.set_state(FilterForm.direction_menu)
    await callback.message.edit_text(
        settings_manager.get("text_directions_filter_menu"),
        reply_markup=get_back_to_filter_main_menu_button()
    )
    await callback.answer()


async def _handle_set_numeric_param(callback: CallbackQuery, state: FSMContext,
                                    param_name: str, prompt_text: str, current_value: Optional[float]):
    """
    Загальний обробник для ініціалізації введення числових параметрів.
    """
    await state.set_state(getattr(FilterForm, f"waiting_for_{param_name}"))
    current_val_str = f"{current_value}" if current_value is not None else 'не встановлено'
    await callback.message.edit_text(
        f"{prompt_text} Поточне значення: {current_val_str}",
        reply_markup=get_numeric_input_keyboard(param_name)
    )
    await callback.answer()


async def _process_numeric_param_input(message: Message, state: FSMContext,
                                       param_name: str, next_state: State,
                                       prompt_text_next: Optional[str] = None,
                                       validation_key: Optional[str] = None,
                                       min_value: Optional[float] = None):
    """
    Загальний обробник для обробки введених числових значень фільтрів.
    param_name: назва поля в LardiSearchFilter (наприклад, "mass1", "mass2")
    next_state: наступний FSM стан після успішного введення
    prompt_text_next: текст, який буде відправлений, якщо є наступний крок
    validation_key: ключ для даних стану FSM, щоб зберігати попереднє значення для валідації (наприклад, "mass1" для перевірки mass2)
    min_value: мінімальне значення для валідації (наприклад, якщо param_name - це mass2, а validation_key - mass1, то min_value буде значенням mass1)
    """
    telegram_id = message.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)

    try:
        value = float(message.text.replace(',', '.'))
        if value < 0:
            raise ValueError(settings_manager.get("text_invalid_number_input"))

        # Валідація "до" значення (mass2, volume2, etc.)
        if validation_key:
            user_data = await state.get_data()
            prev_value = user_data.get(validation_key)
            # Отримаємо актуальне значення з lardi_filter_obj, якщо воно не в FSM (наприклад, якщо користувач змінив mass2 без зміни mass1)
            if prev_value is not None and value < prev_value:
                await message.answer(
                    f"Максимальне значення не може бути меншим за мінімальне ({validation_key.replace('1', '')} від: {prev_value}). Спробуйте ще раз.",
                    reply_markup=get_numeric_input_keyboard(param_name)
                )
                return

        # Зберігаємо значення в моделі LardiSearchFilter
        setattr(lardi_filter_obj, param_name, value)
        await lardi_filter_obj.asave()

        # Зберігаємо значення в FSM контексті для подальших перевірок
        await state.update_data({param_name: value})

        if next_state == FilterForm.cargo_params_menu:
            await state.clear()  # Очищаємо всі дані FSM context
            lardi_filter_obj_reloaded = await _get_or_create_lardi_filter(telegram_id)
            current_filters_dict = user_filter_to_dict(lardi_filter_obj_reloaded)
            await message.answer(
                settings_manager.get("text_mass_updated").replace("Маса", prompt_text_next),  # Тут prompt_text_next буде як "Маса", "Об'єм" і т.д.
                reply_markup=get_cargo_params_filter_keyboard(current_filters_dict)
            )
            await state.set_state(FilterForm.cargo_params_menu)  # Повертаємось до меню параметрів
        else:
            await state.set_state(next_state)
            await message.answer(prompt_text_next, reply_markup=get_numeric_input_keyboard(param_name=param_name.replace('1', '2')))

    except ValueError as e:
        await message.answer(f"Невірний формат. Будь ласка, введіть числове значення. {e}", reply_markup=get_numeric_input_keyboard(param_name=param_name))
    except Exception as e:
        logger.error(f"Помилка при обробці вводу для {param_name}: {e}")
        await message.answer("Виникла невідома помилка. Спробуйте ще раз.", reply_markup=get_numeric_input_keyboard(param_name=param_name))


@router.callback_query(F.data == "filter_cargo_params_menu")
async def cb_filter_cargo_params_menu(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для переходу в меню параметрів вантажу.
    """
    telegram_id = callback.from_user.id
    lardi_client_obj = await _get_or_create_lardi_filter(telegram_id=telegram_id)

    # Збираємо словник фільтрів з об'єктами моделі
    current_filters_dict = user_filter_to_dict(lardi_filter_obj=lardi_client_obj)

    await state.set_state(FilterForm.cargo_params_menu)
    await callback.message.edit_text(
        "Оберіть параметр вантажу для зміни:",
        reply_markup=get_cargo_params_filter_keyboard(current_filters_dict)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("clear_"))  # Обробляє будь-який стан
async def cb_clear_numeric_param(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    # Отримуємо назву параметра з callback_data (наприклад, "clear_mass1" -> "mass1")
    param_to_clear = callback.data.replace("clear_", "")

    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)

    # Встановлюємо значення параметра в None
    setattr(lardi_filter_obj, param_to_clear, None)
    await lardi_filter_obj.asave()

    # Очищаємо даний параметр зі стану FSM, якщо він там був
    user_data = await state.get_data()
    if param_to_clear in user_data:
        del user_data[param_to_clear]
        await state.set_data(user_data)

    # Перевіряємо, чи це був "перший" параметр (mass1, volume1, etc.)
    # Якщо так, то ми також скидаємо "другий" параметр (mass2, volume2, etc.)
    if param_to_clear.endswith('1'):
        param_to_clear_2 = param_to_clear.replace('1', '2')
        if hasattr(lardi_filter_obj, param_to_clear_2):
            setattr(lardi_filter_obj, param_to_clear_2, None)
            await lardi_filter_obj.asave()  # Зберігаємо знову після обнулення другого параметра
            if param_to_clear_2 in user_data:
                del user_data[param_to_clear_2]
                await state.set_data(user_data)
        message_text_part = f"{param_to_clear.replace('1', '').capitalize()} (та {param_to_clear_2.replace('2', '')}) скинуто."
    else:
        message_text_part = f"{param_to_clear.capitalize()} скинуто."

    # Повертаємо користувача до меню параметрів вантажу та оновлюємо клавіатуру
    await state.clear()  # Очищаємо весь стан, оскільки значення скинуто
    lardi_filter_obj_reloaded = await _get_or_create_lardi_filter(telegram_id)  # Перезавантажуємо для актуальних значень
    current_filters_dict = user_filter_to_dict(lardi_filter_obj_reloaded)

    await callback.message.edit_text(
        f"✅ {message_text_part}\nОберіть параметр вантажу для зміни:",
        reply_markup=get_cargo_params_filter_keyboard(current_filters_dict)
    )
    await state.set_state(FilterForm.cargo_params_menu)
    await callback.answer()


@router.callback_query(F.data == "cancel_input")
async def cb_cancel_input(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для кнопки "Відмінити" під час введення числових значень.
    Повертає користувача до меню параметрів вантажу.
    """
    await state.clear()  # Очищаємо стан
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)
    current_filters_dict = user_filter_to_dict(lardi_filter_obj)

    await callback.message.edit_text(
        "Введення скасовано.\nОберіть параметр вантажу для зміни:",
        reply_markup=get_cargo_params_filter_keyboard(current_filters_dict)
    )
    await state.set_state(FilterForm.cargo_params_menu)
    await callback.answer()


@router.callback_query(F.data == "set_mass1")
async def cb_set_mass1(callback: CallbackQuery, state: FSMContext):
    """
    Запит на введення мінімальної маси.
    """
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)
    await _handle_set_numeric_param(
        callback, state, "mass1", "Введіть мінімальну масу (у тоннах), наприклад: 1.5", lardi_filter_obj.mass1
    )


@router.message(FilterForm.waiting_for_mass1)
async def process_mass1_input(message: Message, state: FSMContext):
    await _process_numeric_param_input(
        message, state, "mass1", FilterForm.waiting_for_mass2, "Введіть максимальну масу (у тоннах), наприклад: 20"
    )


@router.callback_query(F.data == "set_mass2")
async def cb_set_mass2(callback: CallbackQuery, state: FSMContext):
    """
    Запит на введення максимальної маси.
    """
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)
    await _handle_set_numeric_param(
        callback, state, "mass2", "Введіть максимальну масу (у тоннах), наприклад: 20", lardi_filter_obj.mass2
    )


@router.message(FilterForm.waiting_for_mass2)
async def process_mass2_input(message: Message, state: FSMContext):
    await _process_numeric_param_input(
        message, state, "mass2", FilterForm.cargo_params_menu, "Маса", validation_key="mass1"
    )


# НОВІ ОБРОБНИКИ ДЛЯ ІНШИХ ПАРАМЕТРІВ ВАНТАЖУ (об'єм, довжина, ширина, висота)
@router.callback_query(F.data == "set_volume1")
async def cb_set_volume1(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)
    await _handle_set_numeric_param(
        callback, state, "volume1", "Введіть мінімальний об'єм (у м³), наприклад: 1.0", lardi_filter_obj.volume1
    )


@router.message(FilterForm.waiting_for_volume1)
async def process_volume1_input(message: Message, state: FSMContext):
    await _process_numeric_param_input(
        message, state, "volume1", FilterForm.waiting_for_volume2, "Введіть максимальний об'єм (у м³), наприклад: 10.0"
    )


@router.callback_query(F.data == "set_volume2")
async def cb_set_volume2(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)
    await _handle_set_numeric_param(
        callback, state, "volume2", "Введіть максимальний об'єм (у м³), наприклад: 10.0", lardi_filter_obj.volume2
    )


@router.message(FilterForm.waiting_for_volume2)
async def process_volume2_input(message: Message, state: FSMContext):
    await _process_numeric_param_input(
        message, state, "volume2", FilterForm.cargo_params_menu, "Об'єм", validation_key="volume1"
    )


@router.callback_query(F.data == "set_length1")
async def cb_set_length1(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)
    await _handle_set_numeric_param(
        callback, state, "length1", "Введіть мінімальну довжину (у м/ldm), наприклад: 13.6", lardi_filter_obj.length1
    )


@router.message(FilterForm.waiting_for_length1)
async def process_length1_input(message: Message, state: FSMContext):
    await _process_numeric_param_input(
        message, state, "length1", FilterForm.waiting_for_length2, "Введіть максимальну довжину (у м/ldm), наприклад: 13.6"
    )


@router.callback_query(F.data == "set_length2")
async def cb_set_length2(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)
    await _handle_set_numeric_param(
        callback, state, "length2", "Введіть максимальну довжину (у м/ldm), наприклад: 13.6", lardi_filter_obj.length2
    )


@router.message(FilterForm.waiting_for_length2)
async def process_length2_input(message: Message, state: FSMContext):
    await _process_numeric_param_input(
        message, state, "length2", FilterForm.cargo_params_menu, "Довжина", validation_key="length1"
    )


@router.callback_query(F.data == "set_width1")
async def cb_set_width1(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)
    await _handle_set_numeric_param(
        callback, state, "width1", "Введіть мінімальну ширину (у м.), наприклад: 2.2", lardi_filter_obj.width1
    )


@router.message(FilterForm.waiting_for_width1)
async def process_width1_input(message: Message, state: FSMContext):
    await _process_numeric_param_input(
        message, state, "width1", FilterForm.waiting_for_width2, "Введіть максимальну ширину (у м.), наприклад: 2.5"
    )


@router.callback_query(F.data == "set_width2")
async def cb_set_width2(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)
    await _handle_set_numeric_param(
        callback, state, "width2", "Введіть максимальну ширину (у м.), наприклад: 2.5", lardi_filter_obj.width2
    )


@router.message(FilterForm.waiting_for_width2)
async def process_width2_input(message: Message, state: FSMContext):
    await _process_numeric_param_input(
        message, state, "width2", FilterForm.cargo_params_menu, "Ширина", validation_key="width1"
    )


@router.callback_query(F.data == "set_height1")
async def cb_set_height1(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)
    await _handle_set_numeric_param(
        callback, state, "height1", "Введіть мінімальну висоту (у м.), наприклад: 2.0", lardi_filter_obj.height1
    )


@router.message(FilterForm.waiting_for_height1)
async def process_height1_input(message: Message, state: FSMContext):
    await _process_numeric_param_input(
        message, state, "height1", FilterForm.waiting_for_height2, "Введіть максимальну висоту (у м.), наприклад: 2.5"
    )


@router.callback_query(F.data == "set_height2")
async def cb_set_height2(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)
    await _handle_set_numeric_param(
        callback, state, "height2", "Введіть максимальну висоту (у м.), наприклад: 2.5", lardi_filter_obj.height2
    )


@router.message(FilterForm.waiting_for_height2)
async def process_height2_input(message: Message, state: FSMContext):
    await _process_numeric_param_input(
        message, state, "height2", FilterForm.cargo_params_menu, "Висота", validation_key="height1"
    )


@router.callback_query(F.data == "filter_load_types_menu")
async def cb_filter_load_types_menu(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для переходу в меню типів завантаження.
    """
    telegram_id = callback.from_user.id

    lardi_filter_obj = await LardiSearchFilter.objects.filter(user__telegram_id=telegram_id).afirst()

    if not lardi_filter_obj:
        user_profile, created = await UserProfile.objects.aget_or_create(telegram_id=telegram_id)
        lardi_filter_obj = await LardiSearchFilter.objects.acreate(user=user_profile, **lardi_client.default_filters())

    current_load_types = lardi_filter_obj.load_types if lardi_filter_obj.load_types is not None else []

    await state.set_state(FilterForm.load_types_menu)
    await callback.message.edit_text(
        settings_manager.get("text_select_load_types"),
        reply_markup=get_load_types_filter_keyboard(current_load_types)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_load_type_"))
async def cb_toggle_load_type(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для перемикання типу завантаження.
    """
    telegram_id = callback.from_user.id

    load_type_to_toggle = callback.data.replace("toggle_load_type_", "")

    lardi_filter_obj = await LardiSearchFilter.objects.filter(user__telegram_id=telegram_id).afirst()

    if not lardi_filter_obj:
        # Це не повинно статися, якщо cb_filter_load_types_menu вже створив його,
        # але на всяк випадок.
        await callback.message.answer("Помилка: Не вдалося знайти ваші налаштування фільтрів. Спробуйте знову.")
        await callback.answer()
        return

    current_load_types = lardi_filter_obj.load_types if lardi_filter_obj.load_types is not None else []

    # 2. Оновлюємо список: додаємо або видаляємо тип
    if load_type_to_toggle in current_load_types:
        current_load_types.remove(load_type_to_toggle)
        message_text = f"❌ Тип завантаження '{load_type_to_toggle}' вимкнено."
    else:
        current_load_types.append(load_type_to_toggle)
        message_text = f"✅ Тип завантаження '{load_type_to_toggle}' увімкнено."

    # 3. Зберігаємо оновлений список у базу даних
    lardi_filter_obj.load_types = current_load_types
    await lardi_filter_obj.asave()  # Використовуємо async save

    # 4. Оновлюємо клавіатуру, щоб відобразити зміни
    await callback.message.edit_reply_markup(
        reply_markup=get_load_types_filter_keyboard(current_load_types)
    )
    # Відправляємо тимчасове повідомлення про зміну статусу
    await callback.answer(message_text, show_alert=False)


@router.callback_query(F.data == "filter_payment_forms_menu")
async def cb_filter_payment_forms_menu(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для переходу в меню налаштувань форм оплати.
    """
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id=telegram_id)

    # `payment_forms` в моделі - це список цілих чисел.
    # Якщо воно None або порожній список, використовуємо порожній список для відображення.
    current_payment_forms = lardi_filter_obj.payment_form_ids if lardi_filter_obj.payment_form_ids is not None else []

    await state.set_state(FilterForm.payment_forms_menu)
    await callback.message.edit_text(
        settings_manager.get("text_select_payment_forms"),
        reply_markup=get_payment_forms_keyboard(current_payment_forms)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_payment_form_"))
async def cb_toggle_payment_form(callback: CallbackQuery):
    """
    Обробник для перемикання статусу форми оплати.
    """
    telegram_id = callback.from_user.id
    form_id_to_toggle = int(callback.data.replace("toggle_payment_form_", ""))  # Отримуємо ID форми оплати як int

    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)
    current_payment_forms = lardi_filter_obj.payment_form_ids if lardi_filter_obj.payment_form_ids is not None else []

    # Допоміжний словник для назв форм оплати (для повідомлень)
    payment_forms_names = {
        2: "Готівка",
        4: "Безготівка",
        6: "Комбінована",
        8: "Електронний платіж",
        10: "Карта"
    }
    form_name = payment_forms_names.get(form_id_to_toggle, f"Невідома форма ({form_id_to_toggle})")

    if form_id_to_toggle in current_payment_forms:
        current_payment_forms.remove(form_id_to_toggle)
        message_text = f"❌ Форма оплати '{form_name}' вимкнена."
    else:
        current_payment_forms.append(form_id_to_toggle)
        message_text = f"✅ Форма оплати '{form_name}' увімкнена."

    # Зберігаємо оновлений список
    lardi_filter_obj.payment_form_ids = current_payment_forms
    await lardi_filter_obj.asave()

    # Оновлюємо клавіатуру
    await callback.message.edit_reply_markup(
        reply_markup=get_payment_forms_keyboard(current_payment_forms)
    )
    await callback.answer(message_text, show_alert=False)


# Функція для вилучення countrySign з JSON-поля
def _extract_country_signs(direction_data: Union[Dict[str, Any], List[Any], str, None]) -> List[str]:
    """
    Вилучає коди країн зі структури даних напрямку (direction_data).
    Робить це стійко до різних можливих форматів збережених даних (словник, список, JSON-рядок).
    """
    selected_countries = []

    parsed_data = None
    if isinstance(direction_data, str):
        try:
            parsed_data = json.loads(direction_data)
        except json.JSONDecodeError:
            if len(direction_data) == 2 and direction_data.isalpha():
                return [direction_data.upper()]
            return []
    elif isinstance(direction_data, (dict, list)):
        parsed_data = direction_data
    elif direction_data is None:
        return []

    if isinstance(parsed_data, dict) and "directionRows" in parsed_data \
            and isinstance(parsed_data["directionRows"], list):
        for row in parsed_data["directionRows"]:
            if isinstance(row, dict) and "countrySign" in row:
                selected_countries.append(row["countrySign"])
    elif isinstance(parsed_data, list):
        for item in parsed_data:
            if isinstance(item, dict) and "directionRows" in item \
                    and isinstance(item["directionRows"], list):
                for row in item["directionRows"]:
                    if isinstance(row, dict) and "countrySign" in row:
                        selected_countries.append(row["countrySign"])
            elif isinstance(item, str) and len(item) == 2 and item.isalpha():
                selected_countries.append(item)

    return [c.upper() for c in list(set(selected_countries))]


@router.callback_query(F.data == "direction_filter_menu")
async def cb_direction_filter_menu(callback: CallbackQuery, state: FSMContext):
    """
    Показує меню налаштування напрямків.
    """
    await callback.message.edit_text(
        "Text directions menu",
        reply_markup=get_direction_filter_menu_keyboard()
    )
    await state.set_state(FilterForm.direction_menu)
    await callback.answer()


@router.callback_query(F.data == "set_direction_from_country")
async def cb_set_direction_from_country(callback: CallbackQuery, state: FSMContext):
    """
    Показує клавіатуру для вибору країни відправлення.
    """
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)

    current_selected_countries = _extract_country_signs(lardi_filter_obj.direction_from)

    await callback.message.edit_text(
        settings_manager.get("text_countries_menu"),
        reply_markup=get_country_options_keyboard(current_selected_countries, current_page=0, is_from_direction=True)
    )
    await state.set_state(FilterForm.waiting_for_country_from)
    await callback.answer()


@router.callback_query(F.data == "set_direction_to_country")
async def cb_set_direction_to_country(callback: CallbackQuery, state: FSMContext):
    """
    Показує клавіатуру для вибору країни призначення.
    """
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)

    current_selected_countries = _extract_country_signs(lardi_filter_obj.direction_to)

    await callback.message.edit_text(
        "2",
        reply_markup=get_country_options_keyboard(current_selected_countries, current_page=0, is_from_direction=False)
    )
    await state.set_state(FilterForm.waiting_for_country_to)
    await callback.answer()


@router.callback_query(F.data.startswith("country_page:"))
async def cb_country_pagination(callback: CallbackQuery, state: FSMContext):
    """
    Обробляє навігацію по сторінках вибору країн.
    Callback data: "country_page:{'from'|'to'}:{'prev'|'next'}:{current_page}"
    """
    try:
        data = callback.data.split(':')
        direction_type = data[1]  # 'from' або 'to'
        action = data[2]  # 'prev' або 'next'
        current_page = int(data[3]) # Поточна сторінка, з якої йде запит

        telegram_id = callback.from_user.id
        lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)

        is_from_direction = (direction_type == 'from')

        if is_from_direction:
            current_selected_countries = _extract_country_signs(lardi_filter_obj.direction_from)
        else:
            current_selected_countries = _extract_country_signs(lardi_filter_obj.direction_to)

        all_country_codes = list(ALL_COUNTRIES_FOR_SELECTION.keys())
        total_countries = len(all_country_codes)
        total_pages = (total_countries + COUNTRIES_PER_PAGE - 1) // COUNTRIES_PER_PAGE

        new_page = current_page

        if action == 'next':
            if current_page < total_pages - 1:
                new_page = current_page + 1
        elif action == 'prev':
            if current_page > 0:
                new_page = current_page - 1

        if new_page != current_page:
            await callback.message.edit_reply_markup(
                reply_markup=get_country_options_keyboard(
                    current_selected_countries,
                    current_page=new_page,
                    is_from_direction=is_from_direction
                )
            )
        await callback.answer()

    except Exception as e:
        logger.error(f"Помилка в cb_country_pagination: {e}", exc_info=True)
        await callback.answer("Виникла помилка при зміні сторінки країн.", show_alert=True)


@router.callback_query(F.data.startswith("select_from_country:"))
@router.callback_query(F.data.startswith("select_to_country:"))
async def cb_select_country(callback: CallbackQuery, state: FSMContext):
    """
    Обробляє вибір/скасування вибору країни.
    Callback data: "select_from_country:{country_code}:{current_page}"
    Callback data: "select_to_country:{country_code}:{current_page}"
    """
    data = callback.data.split(':')
    callback_prefix = data[0]
    country_code = data[1]
    current_page = int(data[2])

    is_from_direction = (callback_prefix == "select_from_country")

    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)

    # --- ЛОГУВАННЯ ДЛЯ ДІАГНОСТИКИ ---
    logger.info(f"cb_select_country: Запущено для user_id={telegram_id}, country_code={country_code}, direction_type={'from' if is_from_direction else 'to'}")
    logger.info(f"cb_select_country: LardiSearchFilter ID: {lardi_filter_obj.id}")
    logger.info(f"cb_select_country: direction_from (з БД ДО обробки): {lardi_filter_obj.direction_from}")
    logger.info(f"cb_select_country: direction_to (з БД ДО обробки): {lardi_filter_obj.direction_to}")
    # --- КІНЕЦЬ ЛОГІВ ---

    if is_from_direction:
        current_selected_countries = _extract_country_signs(lardi_filter_obj.direction_from)
    else:
        current_selected_countries = _extract_country_signs(lardi_filter_obj.direction_to)

    logger.info(f"cb_select_country: current_selected_countries (після _extract_country_signs): {current_selected_countries}")

    new_selected_countries_data = {"directionRows": []}

    if country_code.upper() in [c.upper() for c in current_selected_countries]:
        logger.info(f"cb_select_country: Країна {country_code} вже була обрана. Знімаємо вибір.")
    else:
        new_selected_countries_data["directionRows"].append({"countrySign": country_code.upper()})
        logger.info(f"cb_select_country: Обрано країну {country_code}. Тепер це єдина обрана країна.")

    if is_from_direction:
        lardi_filter_obj.direction_from = new_selected_countries_data
        logger.info(f"cb_select_country: Призначаємо direction_from: {new_selected_countries_data}")
    else:
        lardi_filter_obj.direction_to = new_selected_countries_data
        logger.info(f"cb_select_country: Призначаємо direction_to: {new_selected_countries_data}")

    logger.info(f"cb_select_country: LardiSearchFilter перед збереженням. direction_from: {lardi_filter_obj.direction_from}")
    logger.info(f"cb_select_country: LardiSearchFilter перед збереженням. direction_to: {lardi_filter_obj.direction_to}")

    try:
        await sync_to_async(lardi_filter_obj.save)()
        logger.info(f"cb_select_country: Фільтр LardiSearchFilter (ID: {lardi_filter_obj.id}) УСПІШНО збережено в БД.")
    except Exception as e:
        logger.error(f"cb_select_country: ПОМИЛКА при збереженні LardiSearchFilter (ID: {lardi_filter_obj.id}): {e}", exc_info=True)
        await callback.message.answer(settings_manager.get("text_error_saving_filters", default="Помилка при збереженні фільтрів."))

    if is_from_direction:
        updated_selected_countries_for_keyboard = _extract_country_signs(lardi_filter_obj.direction_from)
    else:
        updated_selected_countries_for_keyboard = _extract_country_signs(lardi_filter_obj.direction_to)

    await callback.message.edit_reply_markup(
        reply_markup=get_country_options_keyboard(
            selected_countries=updated_selected_countries_for_keyboard,
            current_page=current_page,
            is_from_direction=is_from_direction
        )
    )

    selected_count_text = (
        f"Обрана країна: {len(updated_selected_countries_for_keyboard)}"
        if updated_selected_countries_for_keyboard else "Жодної країни не обрано"
    )
    try:
        await callback.message.edit_text(
            f"{settings_manager.get('text_countries_menu')}\n\n{selected_count_text}",
            reply_markup=get_country_options_keyboard(
                selected_countries=updated_selected_countries_for_keyboard,
                current_page=current_page,
                is_from_direction=is_from_direction
            )
        )
    except TelegramBadRequest as e:
        logger.warning(f"TelegramBadRequest при оновленні тексту: {e}. Ігноруємо, ймовірно, текст не змінився суттєво, але розмітка оновлена.")

    answer_text = (
        f"Обрано: {ALL_COUNTRIES_FOR_SELECTION.get(country_code, country_code)}"
        if country_code.upper() in [c.upper() for c in updated_selected_countries_for_keyboard]
        else "Вибір країни скасовано"
    )
    await callback.answer(answer_text)


@router.callback_query(F.data == "filter_boolean_options_menu")
async def cb_filter_boolean_options_menu(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для переходу в меню додаткових булевих опцій.
    """
    telegram_id = callback.from_user.id
    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)

    # Передаємо об'єкт фільтра, щоб клавіатура могла прочитати всі булеві поля
    current_filters_dict = user_filter_to_dict(lardi_filter_obj)

    await state.set_state(FilterForm.boolean_options_menu)
    await callback.message.edit_text(
        settings_manager.get("text_boolean_options_filter_menu"),
        reply_markup=get_boolean_options_keyboard(current_filters_dict)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_boolean_"))
async def cb_toggle_boolean_option(callback: CallbackQuery):
    """
    Обробник для перемикання статусу булевої опції (True <-> False).
    """
    telegram_id = callback.from_user.id
    param_name = callback.data.replace("toggle_boolean_", "")

    lardi_filter_obj = await _get_or_create_lardi_filter(telegram_id)

    # --- Debugging Start ---
    # Отримуємо значення до зміни
    current_value_before_set = getattr(lardi_filter_obj, param_name, False)
    logger.info(f"User {telegram_id}: Toggling option '{param_name}'.")
    logger.info(f"Before change - LardiFilter object state for '{param_name}': {current_value_before_set}")
    # --- Debugging End ---

    new_value = not current_value_before_set

    # Встановлюємо нове значення для об'єкта в пам'яті
    setattr(lardi_filter_obj, param_name, new_value)

    # --- Debugging Start ---
    logger.info(f"After setattr (in-memory) - LardiFilter object state for '{param_name}': {getattr(lardi_filter_obj, param_name, 'N/A')}")
    # --- Debugging End ---

    # Зберігаємо зміни в базу даних
    await lardi_filter_obj.asave()

    # --- КЛЮЧОВИЙ КРОК: Явно перезавантажуємо об'єкт з бази даних ---
    # Це гарантує, що ми працюємо з найактуальнішим станом з БД,
    # а не з можливим застарілим станом об'єкта в пам'яті.
    lardi_filter_obj_reloaded = await _get_or_create_lardi_filter(telegram_id)

    # --- Debugging Start ---
    logger.info(f"After asave() and RELOAD - LardiFilter object state for '{param_name}': {getattr(lardi_filter_obj_reloaded, param_name, 'N/A')}")
    # --- Debugging End ---

    # Тепер перевіряємо, чи фактично змінилось значення в ПЕРЕЗАВАНТАЖЕНОМУ об'єкті
    # Якщо значення в перезавантаженому об'єкті дорівнює тому, що було ДО ЗМІНИ,
    # це означає, що збереження або перезавантаження не спрацювало належним чином,
    # або значення в БД вже було таким, як ми намагалися встановити.
    if getattr(lardi_filter_obj_reloaded, param_name) == current_value_before_set:
        display_name = boolean_options_names.get(param_name, param_name)
        status_text = "увімкнено" if current_value_before_set else "вимкнено"  # Використовуємо значення до зміни, бо фактичної зміни не відбулось
        await callback.answer(f"Опція '{display_name}' вже {status_text} (без змін).", show_alert=False)
        return  # Виходимо, оскільки немає чого змінювати

    # Якщо ми дійшли сюди, то зміна відбулася і була успішно перезавантажена
    display_name = boolean_options_names.get(param_name, param_name)
    status_text = "увімкнено" if new_value else "вимкнено"  # Використовуємо intended new_value для повідомлення
    message_text = f"✅ Опція '{display_name}' {status_text}."

    # Генеруємо клавіатуру з ПЕРЕЗАВАНТАЖЕНОГО об'єкта
    current_filters_dict_updated = user_filter_to_dict(lardi_filter_obj_reloaded)

    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_boolean_options_keyboard(current_filters_dict_updated)
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logger.warning(f"Message reply markup not modified for user {telegram_id}: {e}")
        else:
            raise  # Перевикидаємо інші помилки TelegramBadRequest
    finally:
        # Завжди відповідаємо на callback
        await callback.answer(message_text, show_alert=False)


@router.callback_query(FilterForm.main_menu, F.data == "show_current_filters")
async def cb_show_current_filters(callback: CallbackQuery):
    """
    Обробник для показу поточних фільтрів.
    Тепер показує фільтри користувача з бази даних.
    """
    try:
        user_filter_obj = await _get_or_create_lardi_filter(telegram_id=callback.from_user.id)

        # Перетворюємо об'єкт фільтра на словник для відображення
        # Доступ до атрибутів _meta.fields обгортаємо sync_to_async
        filters_to_display = await sync_to_async(lambda: {
            field.name: getattr(user_filter_obj, field.name)
            for field in user_filter_obj._meta.fields
            if field.name not in ['id', 'user', 'created_at', 'updated_at']  # Виключаємо службові поля
        })()

        filters_json = json.dumps(filters_to_display, indent=2, ensure_ascii=False)
        await callback.message.edit_text(
            settings_manager.get("text_current_filters").format(filters_json=filters_json),
            reply_markup=get_back_to_filter_main_menu_button()
        )
    except Exception as e:
        await callback.message.answer(f"Помилка при отриманні фільтрів: {e}")
        print(f"Error showing current filters: {e}")

    await callback.answer()


@router.callback_query(F.data == "reset_filters_confirm")
async def cb_reset_filters_confirm(callback: CallbackQuery):
    """
    Запит на підтвердження скидання фільтрів.
    """
    await callback.message.edit_text(
        settings_manager.get("text_filters_reset_confirm"),
        reply_markup=get_reset_filters_confirm_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "reset_filters_confirmed")
async def cb_reset_filters_confirmed(callback: CallbackQuery, state: FSMContext):
    """
    Скидання фільтрів до значень за замовчуванням.
    """
    lardi_client.filters = lardi_client.default_filters()  # Скидаємо фільтри до дефолтних
    await state.set_state(FilterForm.main_menu)  # Повертаємось у головне меню фільтрів
    await callback.message.edit_text(
        settings_manager.get("text_filters_reset_done"),
        reply_markup=get_filter_main_menu_keyboard()
    )
    await callback.answer()
