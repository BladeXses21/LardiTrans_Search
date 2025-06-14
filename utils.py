from datetime import datetime

def date_format(date_string: str) -> str:
    if date_string.endswith('+00:00'):
        date_string = date_string[:-16]
    try:
        dt_object = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        dt_object = datetime.strptime(date_string, '%Y-%m-%dT%H')

    return dt_object.strftime('%d.%m.%y %H:%M')  # Коротка дата