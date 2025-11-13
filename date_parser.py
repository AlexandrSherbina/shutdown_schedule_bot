import re
from datetime import datetime
from logger import logger


class DateParser:
    """Парсит дату графика из текста сообщения."""

    def __init__(self):
        # Паттерны для поиска даты
        self.date_patterns = [
            # 12.11.2025
            r'(?:За розпорядженням|графіка)\s+(\d{1,2})\.(\d{1,2})\.(\d{4})',
            r'(\d{1,2})[._-](\d{1,2})[._-](\d{4})',  # универсальный
            # словами
            r'(?:на\s+)?(\d{1,2})\s+(?:листопада|novembre|november)\s+(\d{4})',
        ]

    def parse_date(self, text: str) -> datetime | None:
        """Извлекает дату графика из текста."""

        for pattern in self.date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    day, month, year = int(groups[0]), int(
                        groups[1]), int(groups[2])

                    schedule_date = datetime(year, month, day)
                    logger.info(
                        f"✓ Найдена дата графика: {schedule_date.strftime('%d.%m.%Y')}")
                    return schedule_date

                except (ValueError, IndexError) as e:
                    logger.debug(f"Ошибка парсинга даты: {e}")
                    continue

        logger.warning(
            "Дата графика не найдена в сообщении. Используется текущая дата.")
        return datetime.now()

    def is_schedule_valid(self, schedule_date: datetime) -> bool:
        """Проверяет, не устарел ли график."""

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        schedule_date = schedule_date.replace(
            hour=0, minute=0, second=0, microsecond=0)

        # График действует на сегодня или на будущее
        is_valid = schedule_date >= today

        if not is_valid:
            days_old = (today - schedule_date).days
            logger.warning(
                f"⚠️ График устарел на {days_old} день(ей). Игнорируем.")

        return is_valid
