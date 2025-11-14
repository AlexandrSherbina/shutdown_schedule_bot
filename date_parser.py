import re
from datetime import datetime
from logger import logger


class DateParser:
    """Парсит дату графика и время изменения из текста сообщения."""

    def __init__(self):
        # паттерн: "Зміни на 11:24 14.11.2025 ..." или "Зміни на 14.11.2025"
        self.dt_pattern = re.compile(
            r'Зміни\s+на\s+(\d{1,2}:\d{2})\s+(\d{1,2})\.(\d{1,2})\.(\d{4})', re.IGNORECASE)
        self.date_pattern = re.compile(r'(\d{1,2})\.(\d{1,2})\.(\d{4})')

    def parse_date(self, text: str):
        """
        Возвращает кортеж (schedule_date: datetime.date, update_dt: datetime or None).
        update_dt — время изменения в сообщении (локальное), если найдено.
        """
        # сначала пытаемся найти полный timestamp изменения
        m = self.dt_pattern.search(text)
        if m:
            time_part, day, month, year = m.group(
                1), m.group(2), m.group(3), m.group(4)
            try:
                update_dt = datetime.strptime(
                    f"{day}.{month}.{year} {time_part}", "%d.%m.%Y %H:%M")
                schedule_date = update_dt.date()
                logger.info(
                    f"Найдена дата графика {schedule_date} с временем обновления {update_dt}")
                return schedule_date, update_dt
            except Exception as e:
                logger.debug(f"Не удалось распарсить update_dt: {e}")

        # fallback: найти просто дату
        m2 = self.date_pattern.search(text)
        if m2:
            day, month, year = int(m2.group(1)), int(
                m2.group(2)), int(m2.group(3))
            try:
                schedule_date = datetime(year, month, day).date()
                logger.info(
                    f"Найдена дата графика {schedule_date} (без времени обновления)")
                return schedule_date, None
            except Exception as e:
                logger.debug(f"Ошибка парсинга даты: {e}")

        # если нечего найти — вернуть текущую дату
        logger.warning("Дата графика не найдена, используется текущая дата")
        return datetime.now().date(), None

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
