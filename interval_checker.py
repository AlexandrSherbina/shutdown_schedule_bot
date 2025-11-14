import time
from datetime import datetime, timedelta
from logger import logger


class IntervalChecker:
    """Проверяет, находимся ли мы в текущем интервале отключения с учётом даты."""

    def __init__(self):
        pass

    @staticmethod
    def _parse_time_str(time_str: str) -> tuple[int, int]:
        """Преобразует '14:00' или '14' в (hour, minute)."""
        if ':' in time_str:
            h, m = time_str.split(':', 1)
            return int(h), int(m)
        return int(time_str), 0

    def is_in_interval(self, period_start: str, period_end: str, schedule_date) -> bool:
        """
        Проверяет, находимся ли мы СЕЙЧАС в интервале [start, end) на конкретную дату.

        Args:
            period_start: '14:00' или '14'
            period_end: '16:00' или '16' или '24' (24:00 = 00:00 следующего дня)
            schedule_date: datetime.date или datetime.datetime (дата графика)

        Returns:
            True если текущее время попадает в интервал НА ЭТУ ДАТУ
        """
        # Преобразуем schedule_date к date
        if isinstance(schedule_date, datetime):
            sched_date = schedule_date.date()
        else:
            sched_date = schedule_date

        now = datetime.now()
        now_date = now.date()

        # Парсим времена
        sh, sm = self._parse_time_str(period_start)
        eh, em = self._parse_time_str(period_end)

        # Создаём datetime для начала интервала (на дату графика)
        try:
            start_dt = datetime.combine(
                sched_date, datetime.min.time()).replace(hour=sh, minute=sm)
        except Exception as e:
            logger.debug(f"Ошибка при создании start_dt: {e}")
            return False

        # Обрабатываем 24:00 как полночь следующего дня
        if eh == 24 and em == 0:
            end_dt = datetime.combine(
                sched_date, datetime.min.time()) + timedelta(days=1)
        else:
            try:
                end_dt = datetime.combine(
                    sched_date, datetime.min.time()).replace(hour=eh, minute=em)
            except Exception as e:
                logger.debug(f"Ошибка при создании end_dt: {e}")
                return False

        # Если end_dt <= start_dt, интервал переходит на следующий день (например, 22:00-02:00)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        # Проверяем, попадает ли текущее время в [start_dt, end_dt)
        result = start_dt <= now < end_dt

        if result:
            logger.debug(
                f"✓ Текущее время {now} попадает в интервал {start_dt} - {end_dt}")

        return result

    def is_currently_offline(self, periods: list[tuple[str, str, object]]) -> bool:
        """
        Проверяет, отключены ли мы прямо сейчас.

        Args:
            periods: list of (period_start, period_end, apply_date)

        Returns:
            True если текущее время попадает в любой из периодов с учётом его даты
        """
        for period_start, period_end, apply_date in periods:
            try:
                if self.is_in_interval(period_start, period_end, apply_date):
                    return True
            except Exception as e:
                logger.debug(
                    f"Ошибка при проверке интервала {period_start}-{period_end}: {e}")
                continue

        return False

    def get_current_offline_period(self, periods: list[tuple[str, str, object]]) -> tuple[str, str, object] | None:
        """
        Возвращает текущий интервал отключения, если мы в нём.

        Args:
            periods: list of (period_start, period_end, apply_date)

        Returns:
            (period_start, period_end, apply_date) или None
        """
        for period_start, period_end, apply_date in periods:
            try:
                if self.is_in_interval(period_start, period_end, apply_date):
                    return period_start, period_end, apply_date
            except Exception as e:
                logger.debug(
                    f"Ошибка при проверке интервала {period_start}-{period_end}: {e}")
                continue

        return None

    def get_current_time_minutes(self) -> int:
        """Возвращает текущее время в минутах от начала дня."""
        now = datetime.now()
        return now.hour * 60 + now.minute

    def time_str_to_minutes(self, time_str: str) -> int:
        """Преобразует '14:00' в минуты от начала дня."""
        hour, minute = self._parse_time_str(time_str)
        return hour * 60 + minute

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
