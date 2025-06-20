from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from modules.app_config import settings_manager, env_config
import json


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Повертає головну клавіатуру меню бота.
    """
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=settings_manager.get("text_button_search"), callback_data="search_offers"))
    builder.row(InlineKeyboardButton(text=settings_manager.get("text_button_view_offer"), callback_data="view_offer_by_id"))
    builder.row(InlineKeyboardButton(text=settings_manager.get("text_button_change_filters"), callback_data="change_filters"))
    builder.row(InlineKeyboardButton(text=settings_manager.get("text_button_update_cookie"), callback_data="update_lardi_cookie"))
    return builder.as_markup()


def get_back_to_main_menu_button() -> InlineKeyboardMarkup:
    """
    Повертає кнопку "Назад до головного меню".
    """
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад в головне меню", callback_data="start_menu"))
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Повертає кнопку "Відмінити" для скасування поточних дій.
    """
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🚫 Відмінити", callback_data="cancel_action"))
    return builder.as_markup()


def get_filter_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Повертає головне меню для зміни фільтрів.
    """
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=settings_manager.get("text_filter_directions"), callback_data="filter_directions_menu"))
    builder.row(InlineKeyboardButton(text=settings_manager.get("text_filter_cargo_params"), callback_data="filter_cargo_params_menu"))
    builder.row(InlineKeyboardButton(text=settings_manager.get("text_filter_load_types"), callback_data="filter_load_types_menu"))
    builder.row(InlineKeyboardButton(text=settings_manager.get("text_filter_payment_forms"), callback_data="filter_payment_forms_menu"))
    builder.row(InlineKeyboardButton(text=settings_manager.get("text_filter_boolean_options"), callback_data="filter_boolean_options_menu"))
    builder.row(InlineKeyboardButton(text=settings_manager.get("text_show_current_filters"), callback_data="show_current_filters"))
    builder.row(InlineKeyboardButton(text=settings_manager.get("text_reset_filters"), callback_data="reset_filters_confirm"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в головне меню", callback_data="start_menu"))
    return builder.as_markup()


def get_cargo_params_filter_keyboard(current_filters: dict) -> InlineKeyboardMarkup:
    """
    :param current_filters:
    :return: Меню для зміни параметрів вантажу.
    """
    builder = InlineKeyboardBuilder()
    mass1 = current_filters.get("mass1", "Не встановлено")
    mass2 = current_filters.get("mass2", "Не встановлено")
    builder.row(InlineKeyboardButton(text=f"Маса від: {mass1} т.", callback_data="set_mass1"))
    builder.row(InlineKeyboardButton(text=f"Маса до: {mass2} т.", callback_data="set_mass2"))

    volume1 = current_filters.get("volume1", "Не встановлено")
    volume2 = current_filters.get("volume2", "Не встановлено")
    builder.row(InlineKeyboardButton(text=f"Об'єм від: {volume1} м3", callback_data="set_volume1"))
    builder.row(InlineKeyboardButton(text=f"Об'єм до: {volume2} м3", callback_data="set_volume2"))

    length1 = current_filters.get("length1", "Не встановлено")
    length2 = current_filters.get("length2", "Не встановлено")
    builder.row(InlineKeyboardButton(text=f"Довжина навантаження від: {length1} m/ldm", callback_data="set_length1"))
    builder.row(InlineKeyboardButton(text=f"Довжина навантаження до: {length2} m/ldm", callback_data="set_length2"))

    width1 = current_filters.get("width1", "Не встановлено")
    width2 = current_filters.get("width2", "Не встановлено")
    builder.row(InlineKeyboardButton(text=f"Ширина від: {width1} м.", callback_data="set_width1"))
    builder.row(InlineKeyboardButton(text=f"Ширина до: {width2} м.", callback_data="set_width2"))

    height1 = current_filters.get("height1", "Не встановлено")
    height2 = current_filters.get("height2", "Не встановлено")
    builder.row(InlineKeyboardButton(text=f"Висота від: {height1} м.", callback_data="set_height1"))
    builder.row(InlineKeyboardButton(text=f"Висота до: {height2} м.", callback_data="set_height2"))

    builder.row(InlineKeyboardButton(text="⬅️ Назад до меню фільтрів", callback_data="back_to_filter_main_menu"))
    return builder.as_markup()



def get_load_types_filter_keyboard(current_load_types: list) -> InlineKeyboardMarkup:
    """
    Повертає меню для зміни типів завантаження.
    """
    builder = InlineKeyboardBuilder()
    all_load_types = ["top", "side", "back", "tent_off", "beam_off", "rack_off", "gate_off", "tail_lift"]  # Всі можливі значення типу завантаження
    ua_names_load_types = {
        "top": "Верхнє",
        "side": "Бічне",
        "back": "Заднє",
        "tent_off": "З повним розтентуванням",
        "beam_off": "Зі зняттям поперечок",
        "rack_off": "Зі зняттям стійок",
        "gate_off": "Без воріт",
        "tail_lift": "Гідроборт",
    }

    # Створюємо кнопки для кожного типу завантаження, показуючи його поточний статус
    for load_type in all_load_types:
        emoji = "✅" if load_type in current_load_types else "❌"
        builder.row(InlineKeyboardButton(text=f"{emoji} {ua_names_load_types[load_type.lower()]}", callback_data=f"toggle_load_type_{load_type}"))

    builder.row(InlineKeyboardButton(text="⬅️ Назад до меню фільтрів", callback_data="back_to_filter_main_menu"))
    return builder.as_markup()


def get_reset_filters_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Клавіатура для підтвердження скидання фільтрів.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Так, скинути", callback_data="reset_filters_confirmed"),
        InlineKeyboardButton(text="❌ Ні, залишити", callback_data="back_to_filter_main_menu")
    )
    return builder.as_markup()


def get_back_to_filter_main_menu_button() -> InlineKeyboardMarkup:
    """
    Повертає кнопку "Назад до меню фільтрів".
    """
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад до меню фільтрів", callback_data="back_to_filter_main_menu"))
    return builder.as_markup()


def get_cargo_details_webapp_keyboard(cargo_id: int) -> InlineKeyboardMarkup:
    """
    Повертає клавіатуру з кнопкою для запуску Web App з деталями вантажу.
    """
    builder = InlineKeyboardBuilder()
    # URL для WebApp буде виглядати: https://your-domain.com/webapp/cargo_details.html?id={cargo_id}
    # Змінено, щоб відповідати маршруту `/webapp/cargo_details.html` у `web_server.py`
    webapp_url_with_id = f"{env_config.WEBAPP_BASE_URL}.html?id={cargo_id}"

    # Створюємо кнопку, яка відкриває Web App
    builder.row(InlineKeyboardButton(text="Деталі вантажу", web_app=WebAppInfo(url=webapp_url_with_id)))
    builder.row(InlineKeyboardButton(text="⬅️ Назад в головне меню", callback_data="start_menu"))
    return builder.as_markup()

