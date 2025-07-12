from aiogram.fsm.state import State, StatesGroup


class LardiForm(StatesGroup):
    """
    FSM стани для взаємодії з Lardi-Trans API.
    """
    waiting_for_offer_id = State()
    waiting_for_new_cookie = State()


class FilterForm(StatesGroup):
    """
    FSM стани для зміни фільтрів.
    """
    main_menu = State()
    direction_menu = State()
    cargo_params_menu = State()
    load_types_menu = State()
    payment_forms_menu = State()
    boolean_options_menu = State()
    waiting_for_mass1 = State()
    waiting_for_mass2 = State()
    waiting_for_volume1 = State()
    waiting_for_volume2 = State()
    waiting_for_length1 = State()
    waiting_for_length2 = State()
    waiting_for_width1 = State()
    waiting_for_width2 = State()
    waiting_for_height1 = State()
    waiting_for_height2 = State()

    waiting_for_country_from = State()
    waiting_for_country_to = State()

    select_direction_type = State()
    select_country = State()
    select_region = State()
    select_town = State()

    waiting_for_town_query = State()
    select_town_from_search_results = State()