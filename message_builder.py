from datetime import datetime


class MessageBuilder:
    """Построитель сообщений оповещений."""

    def __init__(self, target_queue: str, alert_off_minutes: int, alert_on_minutes: int):
        self.target_queue = target_queue
        self.alert_off_minutes = alert_off_minutes
        self.alert_on_minutes = alert_on_minutes

    def current_offline_message(self, period_start: str, period_end: str) -> str:
        """Сообщение о текущем отключении (прямо сейчас)."""
        return (
            f"🚨 *ВНИМАНИЕ! СЕЙЧАС ОТКЛЮЧЕНЫ!* 🚨\n\n"
            f"Ваша очередь **{self.target_queue}** отключена прямо сейчас.\n"
            f"⏰ Включение в *{period_end}* (осталось ~ {self._get_time_until(period_end)} мин)"
        )

    def initial_off_message(self, period_start: str, period_end: str, alert_time: str) -> str:
        """Начальное сообщение об отключении."""
        return (
            f"🚨 *ОБНОВЛЕНИЕ ГРАФИКА! ОТКЛЮЧЕНИЕ:* 🚨\n\n"
            f"Ваша очередь **{self.target_queue}** будет отключена в *{period_start}* (до *{period_end}*).\n"
            f"⏰ Напоминание сработает в {alert_time}."
        )

    def final_off_message(self, period_start: str, period_end: str) -> str:
        """Финальное сообщение об отключении."""
        return (
            f"⚡️ *СВЕТ ОТКЛЮЧАТ ЧЕРЕЗ {self.alert_off_minutes} МИНУТ!* 📢\n\n"
            f"Плановое *отключение* в {period_start} до {period_end} для очереди {self.target_queue}."
        )

    def initial_on_message(self, period_end: str, alert_time: str) -> str:
        """Начальное сообщение о включении."""
        return (
            f"💡 *ОБНОВЛЕНИЕ ГРАФИКА! ВКЛЮЧЕНИЕ:* 💡\n\n"
            f"Ваша очередь **{self.target_queue}** будет включена в *{period_end}*.\n"
            f"⏰ Напоминание сработает в {alert_time}."
        )

    def final_on_message(self, period_end: str) -> str:
        """Финальное сообщение о включении."""
        return (
            f"💡 *СВЕТ ВКЛЮЧАТ ЧЕРЕЗ {self.alert_on_minutes} МИНУТ!* 🎉\n\n"
            f"Плановое *включение* в {period_end} для очереди {self.target_queue}."
        )

    def _get_time_until(self, end_time: str) -> int:
        """Вспомогательный метод для расчета минут до конца интервала."""
        from datetime import datetime

        end_hour, end_minute = map(int, end_time.split(':'))
        end_datetime = datetime.now().replace(hour=end_hour, minute=end_minute, second=0)

        # Если время уже прошло — добавляем 24 часа
        if end_datetime < datetime.now():
            from datetime import timedelta
            end_datetime += timedelta(days=1)

        delta = (end_datetime - datetime.now()).total_seconds() / 60
        return int(delta)
