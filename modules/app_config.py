import os
from dotenv import load_dotenv

load_dotenv()


class EnvConfig:
    """
    Клас для зберігання конфігурації з змінних середовища.
    """
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    LARDI_USERNAME: str = os.getenv("LARDI_USERNAME", "") # Нова змінна для логіну Lardi-Trans
    LARDI_PASSWORD: str = os.getenv("LARDI_PASSWORD", "") # Нова змінна для пароля Lardi-Trans
    LARDI_LOGIN_URL: str = os.getenv("LARDI_LOGIN_URL", "")

    # Виправлено типографічну помилку в домені для всіх URL
    WEBAPP_BASE_URL: str = os.getenv("WEBAPP_BASE_URL", "https://9891-91-245-124-201.ngrok-free.app/webapp/cargo_details")
    WEBAPP_API_PROXY_URL: str = os.getenv("WEBAPP_API_PROXY_URL", "https://9891-91-245-124-201.ngrok-free.app/api/cargo_details")


env_config = EnvConfig()


class SettingsManager:
    """
    Менеджер для зберігання та доступу до налаштувань бота.
    Цей клас буде тимчасовим, для демонстрації структури.
    На практиці, ці налаштування краще зберігати в базі даних.
    """
    _settings: dict = {
        "user_create": "Ваш акаунт був успішно зареєстрований.",
        "user_comeback": "З поверненням!",
        "text_button_search": "🔍 Пошук вантажів",
        "text_button_view_offer": "📄 Переглянути вантаж за ID",
        "text_welcome_message": "Вітаємо! Використовуйте кнопки нижче для взаємодії з Lardi-Trans.",
        "text_enter_offer_id": "Будь ласка, введіть ID вантажу:",
        "text_invalid_offer_id": "Невірний ID вантажу. Будь ласка, введіть числове значення.",
        "text_offer_not_found": "Вантаж з таким ID не знайдено або стався збій.",
        "text_button_update_cookie": "🍪 Оновити Cookie Lardi",
        "text_enter_new_cookie": "Будь ласка, введіть новий Lardi Cookie:",
        "text_cookie_updated": "✅ Cookie оновлено!",
        "text_button_change_filters": "⚙️ Змінити фільтри",
        "text_filter_main_menu": "Оберіть категорію фільтрів для зміни:",
        "text_filter_directions": "🗺️ Напрямки (Звідки/Куди)",
        "text_filter_cargo_params": "📦 Параметри вантажу (Маса, Об'єм, Габарити)",
        "text_filter_load_types": "⬆️ Типи завантаження",
        "text_filter_payment_forms": "💰 Форма оплати",
        "text_filter_boolean_options": "☑️ Додаткові опції (Тільки нові, групові і т.д.)",
        "text_show_current_filters": "👁️ Показати поточні фільтри",
        "text_distance_options": "🚩 Опції відстані",
        "text_reset_filters": "🔄 Скинути фільтри",
        "text_filters_reset_confirm": "Ви впевнені, що хочете скинути всі фільтри до значень за замовчуванням?",
        "text_filters_reset_done": "✅ Фільтри скинуто до значень за замовчуванням.",
        "text_enter_mass_from": "Введіть мінімальну масу (у тоннах), наприклад: 1.5",
        "text_enter_mass_to": "Введіть максимальну масу (у тоннах), наприклад: 20",
        "text_invalid_number_input": "Невірний формат. Будь ласка, введіть числове значення.",
        "text_mass_updated": "✅ Маса оновлена!",
        "text_current_filters": "Поточні фільтри:\n```json\n{filters_json}\n```",
        "text_select_load_types": "Оберіть типи завантаження (натисніть, щоб увімкнути/вимкнути):",
        "text_directions_filter_menu": "Тут будуть налаштування напрямків (звідки/куди).\nНаразі UA -> UA",
        "text_select_payment_forms": "Оберіть форми оплати (натисніть, щоб увімкнути/вимкнути):",
        "text_boolean_options_filter_menu": "Оберіть додаткові опції (натисніть, щоб увімкнути/вимкнути):",
        "text_no_active_filters": "У вас немає активних фільтрів. Всі значення за замовчуванням.",
        "text_offer_details_unavailable": "Деталі вантажу наразі недоступні.",
        "text_error_fetching_offers": "Сталася помилка під час отримання пропозицій.",
        "text_not_set": "Не встановлено",


        # Тексти для сповіщень
        "text_button_notifications": "🔔 Сповіщення",
        "text_button_notifications_enabled": "🔔 Сповіщення: Увімкнено",
        "text_button_notifications_disabled": "🔕 Сповіщення: Вимкнено",
        "text_notifications_status_enabled": "Сповіщення увімкнено. Ви отримуватимете повідомлення про нові вантажі за вашими фільтрами.",
        "text_notifications_status_disabled": "Сповіщення вимкнено. Ви не отримуватимете повідомлення про нові вантажі.",
        "text_button_notifications_enable": "✅ Увімкнути сповіщення",
        "text_button_notifications_disable": "❌ Вимкнути сповіщення",
        "text_notifications_toggle_success_enabled": "✅ Сповіщення успішно увімкнено!",
        "text_notifications_toggle_success_disabled": "❌ Сповіщення успішно вимкнено!",

        "text_notification_new_cargo": (
            "🚛 Новий вантаж\\! ID: *{cargo_id}*\n"
            "🕒 {dateFrom} → {dateTo}\n"
            "📅 Ств\\.: {dateCreate} \\| Змін\\.: {dateEdit}\n"
            "📌 Завантаження: *{from_town}* *{from_region}* *{from_countrySign}*\n"
            "◽ {from_address}\n" 
            "📍 Вивантаження: *{to_town}* *{to_region}* *{to_countrySign}*\n"
            "◾ {to_address}\n" 
            "🚚 Тип завантаження: *{loadTypes}*\n"
            "📦 Вантаж: {gruzName}\n"
            "⚖️ Вага: {gruzMass}\n"
            "📐 Обʼєм: {gruzVolume}\n"
            "💰 Оплата: *{payment} \\({paymentForms}\\)*\n"
            "🛣️ Відстань: {distance} км\n"
            "{repeated}"
        ),

    }

    def get(self, key: str):
        """Отримати значення налаштування за ключем."""
        return self._settings.get(key, f"Помилка: Текст для '{key}' не знайдено.")

    def set(self, key: str, value):
        """Встановити значення налаштування за ключем."""
        self._settings[key] = value


settings_manager = SettingsManager()
