import time
from datetime import datetime
from logger import logger


class IntervalChecker:
    """Проверяет, находимся ли мы в текущем интервале отключения."""

    def __init__(self):
        pass

    def get_current_time_minutes(self) -> int:
        """Возвращает текущее время в минутах от начала дня."""
        now = datetime.now()
        return now.hour * 60 + now.minute

    def time_str_to_minutes(self, time_str: str) -> int:
        """Преобразует '14:00' в минуты от начала дня."""
        hour, minute = map(int, time_str.split(':'))
        return hour * 60 + minute

    def is_in_interval(self, period_start: str, period_end: str) -> bool:
        """Проверяет, находимся ли мы сейчас в интервале отключения."""

        current_minutes = self.get_current_time_minutes()
        start_minutes = self.time_str_to_minutes(period_start)
        end_minutes = self.time_str_to_minutes(period_end)

        # Обработка случая, когда интервал переходит через полночь (22-24 -> 00-02)
        if end_minutes <= start_minutes:  # переход через полночь
            return current_minutes >= start_minutes or current_minutes < end_minutes
        else:
            return start_minutes <= current_minutes < end_minutes

    def get_next_interval(self, periods: list[tuple[str, str]]) -> tuple[str, str, int] | None:
        """
        Возвращает следующий интервал отключения.
        Возвращает (период_начало, период_конец, минут_до_отключения) или None.
        """

        current_minutes = self.get_current_time_minutes()

        for period_start, period_end in periods:
            start_minutes = self.time_str_to_minutes(period_start)

            # Интервал в будущем
            if start_minutes > current_minutes:
                minutes_until = start_minutes - current_minutes
                return period_start, period_end, minutes_until

        # Если нет интервалов в будущем сегодня — возвращаем первый завтра
        if periods:
            first_start, first_end = periods[0]
            # До конца дня 1440 минут
            minutes_until = (1440 - current_minutes) + \
                self.time_str_to_minutes(first_start)
            return first_start, first_end, minutes_until

        return None

    def is_currently_offline(self, periods: list[tuple[str, str]]) -> bool:
        """Проверяет, отключены ли мы прямо сейчас."""

        for period_start, period_end in periods:
            if self.is_in_interval(period_start, period_end):
                return True

        return False

    def get_current_offline_period(self, periods: list[tuple[str, str]]) -> tuple[str, str] | None:
        """Возвращает текущий интервал отключения, если мы в нём."""

        for period_start, period_end in periods:
            if self.is_in_interval(period_start, period_end):
                return period_start, period_end

        return None
