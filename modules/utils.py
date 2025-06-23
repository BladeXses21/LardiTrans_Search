from datetime import datetime

from modules.lardi_api_client import LardiClient


def date_format(date_string: str) -> str:
    if date_string.endswith('+00:00'):
        date_string = date_string[:-16]
    try:
        dt_object = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        dt_object = datetime.strptime(date_string, '%Y-%m-%dT%H')

    return dt_object.strftime('%d.%m.%y %H:%M')  # Коротка дата


def add_line(prefix: str, value: any, important: bool = False) -> str:
    """
    Допоміжна функція для форматування рядків виводу.
    """
    if value is None or str(value).strip() == '' or str(value).strip() == 'Н/Д' or str(value).strip() == '—':
        return ""
    if important:
        return f"{prefix}*{value}*\n"
    return f"{prefix}{value}\n"


def user_filter_to_dict(lardi_filter_obj) -> dict:
    user_filters = {
        "directionFrom": lardi_filter_obj.direction_from,
        "directionTo": lardi_filter_obj.direction_to,
        "mass1": lardi_filter_obj.mass1,
        "mass2": lardi_filter_obj.mass2,
        "volume1": lardi_filter_obj.volume1,
        "volume2": lardi_filter_obj.volume2,
        "dateFromISO": lardi_filter_obj.date_from_iso,
        "dateToISO": lardi_filter_obj.date_to_iso,
        "bodyTypeIds": lardi_filter_obj.body_type_ids,
        "loadTypes": lardi_filter_obj.load_types,
        "paymentFormIds": lardi_filter_obj.payment_form_ids,
        "groupage": lardi_filter_obj.groupage,
        "photos": lardi_filter_obj.photos,
        "show_ignore": lardi_filter_obj.show_ignore,
        "only_actual": lardi_filter_obj.only_actual,
        "only_new": lardi_filter_obj.only_new,
        "only_relevant": lardi_filter_obj.only_relevant,
        "only_shippers": lardi_filter_obj.only_shippers,
        "only_carrier": lardi_filter_obj.only_carrier,
        "only_expedition": lardi_filter_obj.only_expedition,
        "only_with_stavka": lardi_filter_obj.only_with_stavka,
        "distanceKmFrom": lardi_filter_obj.distance_km_from,
        "distanceKmTo": lardi_filter_obj.distance_km_to,
        "only_partners": lardi_filter_obj.only_partners,
        "partnerGroups": lardi_filter_obj.partner_groups,
        "cargos": lardi_filter_obj.cargos,
        "cargoPackagingIds": lardi_filter_obj.cargo_packaging_ids,
        "excludeCargos": lardi_filter_obj.exclude_cargos,
        "cargoBodyTypeProperties": lardi_filter_obj.cargo_body_type_properties,
        "paymentCurrencyId": lardi_filter_obj.payment_currency_id,
        "paymentValue": lardi_filter_obj.payment_value,
        "paymentValueType": lardi_filter_obj.payment_value_type,
        "companyRefId": lardi_filter_obj.company_ref_id,
        "companyName": lardi_filter_obj.company_name,
        "length1": lardi_filter_obj.length1,
        "length2": lardi_filter_obj.length2,
        "width1": lardi_filter_obj.width1,
        "width2": lardi_filter_obj.width2,
        "height1": lardi_filter_obj.height1,
        "height2": lardi_filter_obj.height2,
        "includeDocuments": lardi_filter_obj.include_documents,
        "excludeDocuments": lardi_filter_obj.exclude_documents,
        "adr": lardi_filter_obj.adr,
    }

    return user_filters


boolean_options_names = {
    "groupage": "Збірний вантаж",
    "photos": "З фотографіями",
    "show_ignore": "Показувати ігноровані (В розробці)",
    "only_actual": "Тільки актуальні",
    "only_new": "Тільки нові",
    "only_relevant": "Тільки релевантні",
    "only_shippers": "Тільки відправники",
    "only_carrier": "Тільки перевізники",
    "only_expedition": "Тільки експедитори",
    "only_with_stavka": "Тільки зі ставкою",
    "only_partners": "Тільки партнери",
}