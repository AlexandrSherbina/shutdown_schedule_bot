import re
from datetime import datetime
from constants import QUEUE_PATTERN_FORMAT, TIME_PAIRS_PATTERN
from logger import logger
from validators import normalize_time


class ScheduleParser:
    """Парсер графика отключения света."""

    def __init__(self, target_queue: str, schedule_date: datetime = None):
        self.target_queue = target_queue
        self.schedule_date = schedule_date or datetime.now()

    def set_schedule_date(self, schedule_date: datetime):
        """Установить дату графика."""
        self.schedule_date = schedule_date

    def parse(self, text: str) -> list[tuple[str, str, datetime]]:
        """
        Парсит текст и возвращает список кортежей (начало, конец, дата_применения).
        """

        try:
            queue_pattern = re.compile(
                QUEUE_PATTERN_FORMAT.format(re.escape(self.target_queue)),
                re.MULTILINE | re.IGNORECASE
            )

            match = queue_pattern.search(text)
            if not match:
                return []

            schedule_text = match.group(1).strip()
            time_pairs = re.findall(TIME_PAIRS_PATTERN, schedule_text)

            periods = []
            for start_hour, end_hour in time_pairs:
                start_time, end_time = normalize_time(start_hour, end_hour)
                # Возвращаем также дату, на которую этот график
                periods.append((start_time, end_time, self.schedule_date))

            return periods

        except Exception as e:
            logger.error(f"Ошибка парсинга: {e}")
            return []
