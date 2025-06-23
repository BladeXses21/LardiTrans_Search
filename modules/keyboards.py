from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from modules.app_config import settings_manager, env_config
import json

from modules.utils import boolean_options_names


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


def get_numeric_input_keyboard(param_name: str) -> InlineKeyboardMarkup:
    """
    Повертає клавіатуру для вводу числових значень, включаючи кнопку "Скинути значення".
    param_name: назва параметру, який скидається (наприклад, "mass1", "volume2")
    """
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Відмінити", callback_data="cancel_input"))
    builder.row(InlineKeyboardButton(text="🗑️ Скинути значення", callback_data=f"clear_{param_name}"))
    return builder.as_markup()


def get_cargo_params_filter_keyboard(current_filters: dict) -> InlineKeyboardMarkup:
    """
    Клавіатура для меню параметрів вантажу з поточними значеннями фільтрів.
    Приймає словник current_filters з поточними значеннями.
    """
    builder = InlineKeyboardBuilder()

    # Функція для отримання значення фільтра або "не вказано"
    def get_filter_value(key1, key2=None):
        val1 = current_filters.get(key1)
        val2 = current_filters.get(key2) if key2 else None

        if val1 is not None and val2 is not None:
            return f"{val1}-{val2}"
        elif val1 is not None:
            return f"від {val1}"
        elif val2 is not None:
            return f"до {val2}"
        return "не вказано"

    builder.row(
        InlineKeyboardButton(text=f"Маса: {get_filter_value('mass1', 'mass2')} т", callback_data="set_mass1"),
        InlineKeyboardButton(text=f"Об'єм: {get_filter_value('volume1', 'volume2')} м³", callback_data="set_volume1")
    )
    builder.row(
        InlineKeyboardButton(text=f"Довжина: {get_filter_value('length1', 'length2')} м", callback_data="set_length1"),
        InlineKeyboardButton(text=f"Ширина: {get_filter_value('width1', 'width2')} м", callback_data="set_width1")
    )
    builder.row(
        InlineKeyboardButton(text=f"Висота: {get_filter_value('height1', 'height2')} м", callback_data="set_height1")
    )
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


def get_payment_forms_keyboard(selected_payment_forms: list) -> InlineKeyboardMarkup:
    """
    Клавіатура для вибору форм оплати.
    selected_payment_forms: список ідентифікаторів обраних форм оплати.
    """
    builder = InlineKeyboardBuilder()

    all_payment_forms = {
        2: "Готівка",
        4: "Безготівка",
        6: "Комбінована",
        8: "Електронний платіж",
        10: "Карта"
    }

    for form_id, form_name in all_payment_forms.items():
        # Перетворюємо form_id на рядок для порівняння, якщо selected_payment_forms містить рядки
        status = "✅" if form_id in selected_payment_forms else "❌"
        builder.row(InlineKeyboardButton(text=f"{status} {form_name}", callback_data=f"toggle_payment_form_{form_id}"))

    builder.row(InlineKeyboardButton(text="⬅️ Назад до меню фільтрів", callback_data="back_to_filter_main_menu"))
    return builder.as_markup()


def get_boolean_options_keyboard(current_filters: dict) -> InlineKeyboardMarkup:
    """
    Клавіатура для вибору булевих (true/false) опцій.
    current_filters: словник з поточними значеннями булевих фільтрів (snake_case ключі).
    """
    builder = InlineKeyboardBuilder()

    for param_name, display_name in boolean_options_names.items():
        # param_name буде snake_case (наприклад, "only_new")
        current_value = current_filters.get(param_name, False) # Отримуємо значення за snake_case ключем

        status = "✅" if current_value is True else "❌"
        button_text = f"{status} {display_name}"

        # callback_data буде виглядати "toggle_boolean_only_new" (snake_case)
        builder.row(InlineKeyboardButton(text=button_text, callback_data=f"toggle_boolean_{param_name}"))

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
