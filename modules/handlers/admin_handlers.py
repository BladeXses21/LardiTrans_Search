from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from modules.filters import AdminFilter
from modules.keyboards import get_back_to_main_menu_button # Ви можете додати окремі клавіатури для адміна, якщо потрібно

router = Router()
router.message.filter(AdminFilter()) # Застосовуємо фільтр адміністратора до всіх обробників у цьому роутері
router.callback_query.filter(AdminFilter())


@router.message(F.text == "/admin")
async def cmd_admin_panel(message: Message):
    """
    Обробник команди /admin (для адміністраторів).
    Наразі це заглушка.
    """
    await message.answer(
        "Привіт, адміністраторе! Тут буде меню адміністратора.",
        reply_markup=get_back_to_main_menu_button()
    )


# Додайте сюди інші обробники для адміністраторів, якщо це потрібно.
# Наприклад:
# @router.callback_query(F.data == "admin_change_settings")
# async def cb_admin_change_settings(callback: CallbackQuery):
#     await callback.message.edit_text("Тут можна буде змінювати налаштування Lardi API.", reply_markup=...)
#     await callback.answer()

