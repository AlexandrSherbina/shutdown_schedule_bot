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
        self.sent_hashes = set()
        self.planned_alerts = set()

    def send_alert(self, message_text: str) -> bool:
        """Отправляет сообщение (с проверкой на дубликаты)."""

        msg_hash = hashlib.md5(message_text.encode()).hexdigest()

        if msg_hash in self.sent_hashes:
            logger.debug("Сообщение уже было отправлено, пропускаем дубликат")
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

            self.sent_hashes.add(msg_hash)
            logger.info("✓ Уведомление отправлено")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка отправки: {e}")
            return False

    async def schedule_delayed_alert(self, alert_type: str, delay_seconds: float,
                                     message: str, alert_key: str) -> None:
        """Планирует отложенное оповещение."""

        try:
            logger.info(
                f"Планирование {alert_type} через {int(delay_seconds // 60)} мин")
            await asyncio.sleep(delay_seconds)
            self.send_alert(message)
            self.planned_alerts.discard(alert_key)

        except asyncio.CancelledError:
            logger.warning(f"Задача {alert_key} отменена")
        except Exception as e:
            logger.error(f"Ошибка в schedule_delayed_alert: {e}")
