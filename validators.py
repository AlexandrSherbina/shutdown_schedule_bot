import re


def validate_time_format(time_str: str) -> bool:
    """Проверяет формат времени ЧЧ:МММ."""
    pattern = r'^\d{2}:\d{2}$'
    return bool(re.match(pattern, time_str))


def validate_queue_format(queue: str) -> bool:
    """Проверяет формат очереди (например, '1.2')."""
    pattern = r'^\d+\.\d+$'
    return bool(re.match(pattern, queue))


def normalize_time(start_hour: str, end_hour: str) -> tuple[str, str]:
    """Преобразует '02-04' в '02:00-04:00'."""
    if end_hour == '24':
        end_hour = '00'
    return f"{start_hour}:00", f"{end_hour}:00"
