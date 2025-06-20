import json
import os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async

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
    get_cargo_details_webapp_keyboard
)
from modules.fsm_states import LardiForm, FilterForm
from modules.lardi_api_client import LardiClient, LardiOfferClient

from modules.utils import date_format, add_line, user_filter_to_dict

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


# Ім'я бота для посилання на Web App
# BOT_USERNAME = 'LardiSearch_bot'


# Допоміжна функція для отримання фільтрів користувача
async def get_user_filters_from_db(telegram_id: int) -> LardiSearchFilter:
    """
    Отримує об'єкт LardiSearchFilter для даного Telegram ID.
    Якщо об'єкт не існує, створює його з default_filters.
    """
    # Змінено: асинхронні методи ORM await-уємо напряму
    user_profile = await UserProfile.objects.aget(telegram_id=telegram_id)
    lardi_filter, created = await LardiSearchFilter.objects.aget_or_create(user=user_profile)
    return lardi_filter

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """
    Обробник команди /start.
    Реєструє користувача та створює для нього фільтр за замовчуванням, якщо їх ще немає.
    """
    await state.clear() # Очищуємо стан FSM

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

        # Повідомлення користувачу
        if user_created or profile_created:
            await message.answer(settings_manager.get("user_create"), reply_markup=get_main_menu_keyboard())
        else:
            await message.answer(settings_manager.get("user_comeback"), reply_markup=get_main_menu_keyboard())

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
    await callback.message.edit_text(
        settings_manager.get("text_welcome_message"),
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


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

        user_profile, created = await UserProfile.objects.aget_or_create(telegram_id=telegram_id)

        lardi_filter_obj, created_filter = await LardiSearchFilter.objects.aget_or_create(user=user_profile)

        user_filters = user_filter_to_dict(lardi_filter_obj) if user_filter_to_dict(lardi_filter_obj) else lardi_client.filters

        data = lardi_client.get_proposals(filters=user_filters)
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
            block += add_line("📦 Обʼєм: ", volume)
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


@router.message(LardiForm.waiting_for_new_cookie)
async def process_new_cookie(message: Message, state: FSMContext):
    """
    Обробник отримання нового cookie від користувача.
    """
    new_cookie = message.text.strip()
    try:
        # Використання вашого класу LardiClient для оновлення cookie
        lardi_client.update_cookie(new_cookie)
        await message.answer(settings_manager.get("text_cookie_updated"), reply_markup=get_main_menu_keyboard())
    except Exception as e:
        await message.answer(f"❌ Сталася помилка при оновленні cookie: {e}", reply_markup=get_back_to_main_menu_button())
    finally:
        await state.clear()


@router.callback_query(F.data == "cancel_action")
async def cb_cancel_action(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для кнопки "Відмінити" в будь-якому стані FSM.
    """
    await state.clear()
    await callback.message.edit_text(
        settings_manager.get("text_welcome_message"),
        reply_markup=get_main_menu_keyboard()
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


@router.callback_query(F.data == "filter_cargo_params_menu")
async def cb_filter_cargo_params_menu(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для переходу в меню параметрів вантажу.
    """
    await state.set_state(FilterForm.cargo_params_menu)
    await callback.message.edit_text(
        "Оберіть параметр вантажу для зміни:",
        reply_markup=get_cargo_params_filter_keyboard(lardi_client.filters)
    )
    await callback.answer()


@router.callback_query(F.data == "set_mass1")
async def cb_set_mass1(callback: CallbackQuery, state: FSMContext):
    """
    Запит на введення мінімальної маси.
    """
    await state.set_state(FilterForm.waiting_for_mass1)
    await callback.message.edit_text(
        settings_manager.get("text_enter_mass_from"),
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(FilterForm.waiting_for_mass1)
async def process_mass1_input(message: Message, state: FSMContext):
    """
    Обробка введеної мінімальної маси.
    """
    try:
        mass1 = float(message.text.replace(',', '.'))
        lardi_client.set_filter("mass1", mass1)
        await state.set_state(FilterForm.cargo_params_menu)  # Повертаємось у меню параметрів вантажу
        await message.answer(
            settings_manager.get("text_mass_updated"),
            reply_markup=get_cargo_params_filter_keyboard(lardi_client.filters)
        )
    except ValueError:
        await message.answer(
            settings_manager.get("text_invalid_number_input"),
            reply_markup=get_cancel_keyboard()
        )


@router.callback_query(F.data == "set_mass2")
async def cb_set_mass2(callback: CallbackQuery, state: FSMContext):
    """
    Запит на введення максимальної маси.
    """
    await state.set_state(FilterForm.waiting_for_mass2)
    await callback.message.edit_text(
        settings_manager.get("text_enter_mass_to"),
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(FilterForm.waiting_for_mass2)
async def process_mass2_input(message: Message, state: FSMContext):
    """
    Обробка введеної максимальної маси.
    """
    try:
        mass2 = float(message.text.replace(',', '.'))
        lardi_client.set_filter("mass2", mass2)
        await state.set_state(FilterForm.cargo_params_menu)  # Повертаємось у меню параметрів вантажу
        await message.answer(
            settings_manager.get("text_mass_updated"),
            reply_markup=get_cargo_params_filter_keyboard(lardi_client.filters)
        )
    except ValueError:
        await message.answer(
            settings_manager.get("text_invalid_number_input"),
            reply_markup=get_cancel_keyboard()
        )


# НОВІ ОБРОБНИКИ ДЛЯ ІНШИХ ПАРАМЕТРІВ ВАНТАЖУ (об'єм, довжина, ширина, висота)
@router.callback_query(F.data == "set_volume1")
async def cb_set_volume1(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterForm.waiting_for_volume1)
    await callback.message.edit_text("Введіть мінімальний об'єм (у м³), наприклад: 10", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(FilterForm.waiting_for_volume1)
async def process_volume1_input(message: Message, state: FSMContext):
    try:
        volume1 = float(message.text.replace(',', '.'))
        lardi_client.set_filter("volume1", volume1)
        await state.set_state(FilterForm.cargo_params_menu)
        await message.answer(settings_manager.get("text_mass_updated").replace("Маса", "Об'єм"),
                             reply_markup=get_cargo_params_filter_keyboard(lardi_client.filters))
    except ValueError:
        await message.answer(settings_manager.get("text_invalid_number_input"), reply_markup=get_cancel_keyboard())


@router.callback_query(F.data == "set_volume2")
async def cb_set_volume2(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterForm.waiting_for_volume2)
    await callback.message.edit_text("Введіть максимальний об'єм (у м³), наприклад: 100", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(FilterForm.waiting_for_volume2)
async def process_volume2_input(message: Message, state: FSMContext):
    try:
        volume2 = float(message.text.replace(',', '.'))
        lardi_client.set_filter("volume2", volume2)
        await state.set_state(FilterForm.cargo_params_menu)
        await message.answer(settings_manager.get("text_mass_updated").replace("Маса", "Об'єм"),
                             reply_markup=get_cargo_params_filter_keyboard(lardi_client.filters))
    except ValueError:
        await message.answer(settings_manager.get("text_invalid_number_input"), reply_markup=get_cancel_keyboard())


@router.callback_query(F.data == "set_length1")
async def cb_set_length1(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterForm.waiting_for_length1)
    await callback.message.edit_text("Введіть мінімальну довжину (у м.), наприклад: 5", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(FilterForm.waiting_for_length1)
async def process_length1_input(message: Message, state: FSMContext):
    try:
        length1 = float(message.text.replace(',', '.'))
        lardi_client.set_filter("length1", length1)
        await state.set_state(FilterForm.cargo_params_menu)
        await message.answer(settings_manager.get("text_mass_updated").replace("Маса", "Довжина"),
                             reply_markup=get_cargo_params_filter_keyboard(lardi_client.filters))
    except ValueError:
        await message.answer(settings_manager.get("text_invalid_number_input"), reply_markup=get_cancel_keyboard())


@router.callback_query(F.data == "set_length2")
async def cb_set_length2(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterForm.waiting_for_length2)
    await callback.message.edit_text("Введіть максимальну довжину (у м.), наприклад: 13.6", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(FilterForm.waiting_for_length2)
async def process_length2_input(message: Message, state: FSMContext):
    try:
        length2 = float(message.text.replace(',', '.'))
        lardi_client.set_filter("length2", length2)
        await state.set_state(FilterForm.cargo_params_menu)
        await message.answer(settings_manager.get("text_mass_updated").replace("Маса", "Довжина"),
                             reply_markup=get_cargo_params_filter_keyboard(lardi_client.filters))
    except ValueError:
        await message.answer(settings_manager.get("text_invalid_number_input"), reply_markup=get_cancel_keyboard())


@router.callback_query(F.data == "set_width1")
async def cb_set_width1(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterForm.waiting_for_width1)
    await callback.message.edit_text("Введіть мінімальну ширину (у м.), наприклад: 2.2", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(FilterForm.waiting_for_width1)
async def process_width1_input(message: Message, state: FSMContext):
    try:
        width1 = float(message.text.replace(',', '.'))
        lardi_client.set_filter("width1", width1)
        await state.set_state(FilterForm.cargo_params_menu)
        await message.answer(settings_manager.get("text_mass_updated").replace("Маса", "Ширина"),
                             reply_markup=get_cargo_params_filter_keyboard(lardi_client.filters))
    except ValueError:
        await message.answer(settings_manager.get("text_invalid_number_input"), reply_markup=get_cancel_keyboard())


@router.callback_query(F.data == "set_width2")
async def cb_set_width2(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterForm.waiting_for_width2)
    await callback.message.edit_text("Введіть максимальну ширину (у м.), наприклад: 2.5", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(FilterForm.waiting_for_width2)
async def process_width2_input(message: Message, state: FSMContext):
    try:
        width2 = float(message.text.replace(',', '.'))
        lardi_client.set_filter("width2", width2)
        await state.set_state(FilterForm.cargo_params_menu)
        await message.answer(settings_manager.get("text_mass_updated").replace("Маса", "Ширина"),
                             reply_markup=get_cargo_params_filter_keyboard(lardi_client.filters))
    except ValueError:
        await message.answer(settings_manager.get("text_invalid_number_input"), reply_markup=get_cancel_keyboard())


@router.callback_query(F.data == "set_height1")
async def cb_set_height1(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterForm.waiting_for_height1)
    await callback.message.edit_text("Введіть мінімальну висоту (у м.), наприклад: 2.0", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(FilterForm.waiting_for_height1)
async def process_height1_input(message: Message, state: FSMContext):
    try:
        height1 = float(message.text.replace(',', '.'))
        lardi_client.set_filter("height1", height1)
        await state.set_state(FilterForm.cargo_params_menu)
        await message.answer(settings_manager.get("text_mass_updated").replace("Маса", "Висота"),
                             reply_markup=get_cargo_params_filter_keyboard(lardi_client.filters))
    except ValueError:
        await message.answer(settings_manager.get("text_invalid_number_input"), reply_markup=get_cancel_keyboard())


@router.callback_query(F.data == "set_height2")
async def cb_set_height2(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FilterForm.waiting_for_height2)
    await callback.message.edit_text("Введіть максимальну висоту (у м.), наприклад: 3.0", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(FilterForm.waiting_for_height2)
async def process_height2_input(message: Message, state: FSMContext):
    try:
        height2 = float(message.text.replace(',', '.'))
        lardi_client.set_filter("height2", height2)
        await state.set_state(FilterForm.cargo_params_menu)
        await message.answer(settings_manager.get("text_mass_updated").replace("Маса", "Висота"),
                             reply_markup=get_cargo_params_filter_keyboard(lardi_client.filters))
    except ValueError:
        await message.answer(settings_manager.get("text_invalid_number_input"), reply_markup=get_cancel_keyboard())


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
    await lardi_filter_obj.asave() # Використовуємо async save

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
    await state.set_state(FilterForm.payment_forms_menu)
    await callback.message.edit_text(
        settings_manager.get("text_payment_forms_filter_menu"),
        reply_markup=get_back_to_filter_main_menu_button()
    )
    await callback.answer()


@router.callback_query(F.data == "filter_boolean_options_menu")
async def cb_filter_boolean_options_menu(callback: CallbackQuery, state: FSMContext):
    """
    Обробник для переходу в меню налаштувань додаткових опцій.
    """
    await state.set_state(FilterForm.boolean_options_menu)
    await callback.message.edit_text(
        settings_manager.get("text_boolean_options_filter_menu"),
        reply_markup=get_back_to_filter_main_menu_button()
    )
    await callback.answer()


@router.callback_query(FilterForm.main_menu, F.data == "show_current_filters")
async def cb_show_current_filters(callback: CallbackQuery):
    """
    Обробник для показу поточних фільтрів.
    Тепер показує фільтри користувача з бази даних.
    """
    try:
        user_filter_obj = await get_user_filters_from_db(telegram_id=callback.from_user.id)

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
