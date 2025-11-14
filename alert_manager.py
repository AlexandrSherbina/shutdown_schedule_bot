import asyncio
import hashlib
import requests
from logger import logger
from datetime import datetime


class AlertManager:
    """Управляет отправкой оповещений и их отслеживанием."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.sent_hashes = set()  # Хеши отправленных сообщений
        self.sent_keys = set()    # ← НОВОЕ: ключи отправленных сообщений
        self.planned_alerts = set()
        self.scheduled_tasks = {}  # alert_key -> asyncio.Task

    def _get_message_hash(self, message_text: str) -> str:
        """Генерирует хеш сообщения."""
        return hashlib.md5(message_text.encode()).hexdigest()

    def _is_duplicate_sent_today(self, message_text: str) -> bool:
        """Проверяет, было ли это сообщение отправлено сегодня."""
        msg_hash = self._get_message_hash(message_text)

        if msg_hash in self.sent_hashes:
            logger.debug(
                f"Сообщение уже было отправлено. Пропускаем дубликат.")
            return True

        return False

    def send_alert(self, message_text: str, force: bool = False, alert_key: str = None) -> bool:
        """
        Отправляет сообщение (с проверкой на дубликаты).

        Args:
            message_text: Текст сообщения
            force: Если True — отправить, несмотря на дубликаты
            alert_key: Уникальный ключ сообщения (для отслеживания)
        """

        # ← НОВОЕ: Проверка по ключу (более надежная)
        if alert_key and alert_key in self.sent_keys:
            logger.debug(f"Сообщение {alert_key} уже отправлено. Пропускаем.")
            return False

        # Проверка на дубликаты (если не force)
        if not force and self._is_duplicate_sent_today(message_text):
            return False

        try:
            payload = {
                'chat_id': self.chat_id,
                'text': message_text,
                'disable_notification': False,
                'parse_mode': 'Markdown'
            }
            response = requests.post(self.api_url, data=payload, timeout=10)
            response.raise_for_status()

            # Добавляем в набор отправленных
            msg_hash = self._get_message_hash(message_text)
            self.sent_hashes.add(msg_hash)

            # ← НОВОЕ: Добавляем ключ
            if alert_key:
                self.sent_keys.add(alert_key)

            logger.info("✓ Уведомление отправлено")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка отправки: {e}")
            return False

    def clear_daily_cache(self):
        """Очищает кеш отправленных сообщений (вызывать раз в день)."""
        self.sent_hashes.clear()
        self.sent_keys.clear()
        logger.info("✓ Кеш отправленных сообщений очищен")

    async def schedule_delayed_alert(self, alert_type: str, delay_seconds: float,
                                     message: str, alert_key: str) -> None:
        """
        Этот корутин должен запускаться через asyncio.create_task(...).
        Он регистрирует себя в scheduled_tasks по alert_key, выполняет sleep и отправляет.
        """

        # регистрируем задачу
        self.scheduled_tasks[alert_key] = asyncio.current_task()
        try:
            logger.info(
                f"Планирование {alert_type} '{alert_key}' через {int(delay_seconds // 60)} мин")
            await asyncio.sleep(delay_seconds)
            self.send_alert(message, force=True, alert_key=alert_key)
            self.planned_alerts.discard(alert_key)
            self.scheduled_tasks.pop(alert_key, None)

        except asyncio.CancelledError:
            logger.warning(f"Задача {alert_key} отменена")
            self.scheduled_tasks.pop(alert_key, None)
            self.planned_alerts.discard(alert_key)
        except Exception as e:
            logger.error(f"Ошибка в schedule_delayed_alert: {e}")
            self.scheduled_tasks.pop(alert_key, None)
            self.planned_alerts.discard(alert_key)

    def cancel_planned_for_date(self, date_key: str):
        """
        Отменяет все запланированные оповещения и удаляет ключи отправленных сообщений,
        содержащие date_key (строка вида 'dd.mm.YYYY').
        """
        logger.info(f"Отмена запланированных оповещений для {date_key}")
        # отменяем задачи и удаляем ключи planned_alerts
        for key in list(self.planned_alerts):
            if date_key in key:
                task = self.scheduled_tasks.pop(key, None)
                if task and not task.done():
                    task.cancel()
                self.planned_alerts.discard(key)
        # очищаем sent_keys связанные с этой датой (чтобы новые сообщения после изменения могли отправиться)
        for k in list(self.sent_keys):
            if date_key in k:
                self.sent_keys.discard(k)
        logger.info(f"Отмена завершена для {date_key}")
