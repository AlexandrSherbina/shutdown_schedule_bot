import asyncio
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BotController:
    """
    Простой контроллер для управления приложением через Telegram Bot API (polling).
    Команды (только от admin_chat_id):
      /help
      /status
      /set_queue <queue>
      /set_off <minutes>
      /set_on <minutes>
      /planned
      /cancel_date DD.MM.YYYY
      /reload
    """

    def __init__(self, bot_token: str, admin_chat_id: str,
                 parser, alert_manager, alert_config, last_schedule_updates: dict):
        self.api_base = f"https://api.telegram.org/bot{bot_token}"
        self.admin_chat_id = int(admin_chat_id)
        self.parser = parser
        self.alert_manager = alert_manager
        self.alert_config = alert_config
        self.last_schedule_updates = last_schedule_updates
        self.offset = None
        self.running = True

    def _send(self, chat_id: int, text: str):
        """Отправляет сообщение, логирует ошибку тела ответа и при ошибке ретраит без parse_mode."""
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            r = requests.post(f"{self.api_base}/sendMessage",
                              data=payload, timeout=10)
            r.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            # логируем тело ответа (Telegram даёт описание ошибки)
            try:
                logger.error(f"Bot send error: {e} - response: {r.text}")
            except Exception:
                logger.error(f"Bot send error: {e}")
            # повторная попытка — без parse_mode (без Markdown)
            try:
                payload = {"chat_id": chat_id, "text": text}
                r2 = requests.post(
                    f"{self.api_base}/sendMessage", data=payload, timeout=10)
                r2.raise_for_status()
                logger.info("Bot send retry without parse_mode succeeded")
                return True
            except Exception as e2:
                logger.error(f"Bot send retry failed: {e2}")
                return False
        except Exception as e:
            logger.error(f"Bot send error: {e}")
            return False

    def _is_admin(self, upd) -> bool:
        """Более надёжная проверка администратора по разным типам апдейтов."""
        try:
            # поддерживаем разные структуры апдейта
            msg = upd.get('message') or upd.get('edited_message') or upd.get(
                'callback_query', {}).get('message')
            from_id = None
            chat_id = None
            if msg:
                from_id = (msg.get('from') or {}).get('id')
                chat_id = (msg.get('chat') or {}).get('id')
            # fallback: callback_query.from
            if from_id is None and upd.get('callback_query'):
                from_id = (upd['callback_query'].get('from') or {}).get('id')
            if from_id is None:
                return False
            return int(from_id) == self.admin_chat_id or (chat_id is not None and int(chat_id) == self.admin_chat_id)
        except Exception:
            return False

    def _format_status(self) -> str:
        return (
            f"*Статус приложения*\n\n"
            f"Очередь: `{self.alert_config.target_queue}`\n"
            f"Оповещение до ОТКЛЮЧЕНИЯ: `{self.alert_config.alert_minutes_before_off}` мин\n"
            f"Оповещение до ВКЛЮЧЕНИЯ: `{self.alert_config.alert_minutes_before_on}` мин\n"
            f"Интервал проверки: `{self.alert_config.check_interval_seconds}` сек\n"
            f"Запланировано оповещений: `{len(self.alert_manager.planned_alerts)}`"
        )

    def _format_planned(self) -> str:
        if not self.alert_manager.planned_alerts:
            return "Нет запланированных оповещений."
        lines = ["Запланированные ключи:"]
        for k in sorted(self.alert_manager.planned_alerts):
            lines.append(f"- {k}")
        return "\n".join(lines)

    def _handle_command(self, upd):
        try:
            # извлекаем message безопасно
            msg = upd.get('message') or upd.get('edited_message') or {}
            if not self._is_admin(upd):
                logger.debug("Отказано: команда не от администратора")
                return

            chat_id = (msg.get('chat') or {}).get(
                'id') or (msg.get('from') or {}).get('id')
            if not chat_id:
                logger.debug("Не удалось определить chat_id для ответа")
                return

            text = msg.get('text', '').strip()
            if not text:
                return
            parts = text.split()
            cmd = parts[0].lower()

            if cmd == '/help':
                self._send(chat_id, (
                    "/help — помощь\n"
                    "/status — показать текущие настройки\n"
                    "/set_queue <queue> — установить очередь\n"
                    "/set_off <minutes> — минуты до отключения\n"
                    "/set_on <minutes> — минуты до включения\n"
                    "/planned — показать запланированные оповещения\n"
                    "/cancel_date DD.MM.YYYY — отменить планы для даты\n"
                    "/reload — отменить все планы и очистить кеш"
                ))
                return

            if cmd == '/status':
                self._send(chat_id, self._format_status())
                return

            if cmd == '/set_queue' and len(parts) >= 2:
                new_q = parts[1]
                # меняем в parser и в конфиг
                try:
                    self.parser.target_queue = new_q
                except Exception:
                    pass
                self.alert_config.target_queue = new_q
                self._send(chat_id, f"Очередь установлена: `{new_q}`")
                return

            if cmd == '/set_off' and len(parts) >= 2:
                try:
                    val = int(parts[1])
                    self.alert_config.alert_minutes_before_off = val
                    self._send(chat_id, f"Апдейт: ALERT_OFF_MINUTES = `{val}`")
                except ValueError:
                    self._send(
                        chat_id, "Неверный формат. Используйте целое число минут.")
                return

            if cmd == '/set_on' and len(parts) >= 2:
                try:
                    val = int(parts[1])
                    self.alert_config.alert_minutes_before_on = val
                    self._send(chat_id, f"Апдейт: ALERT_ON_MINUTES = `{val}`")
                except ValueError:
                    self._send(
                        chat_id, "Неверный формат. Используйте целое число минут.")
                return

            if cmd == '/planned':
                self._send(chat_id, self._format_planned())
                return

            if cmd == '/cancel_date' and len(parts) >= 2:
                date_key = parts[1]
                # Ожидаем формат DD.MM.YYYY
                try:
                    datetime.strptime(date_key, "%d.%m.%Y")
                except Exception:
                    self._send(
                        chat_id, "Неверный формат даты. Используйте DD.MM.YYYY")
                    return
                self.alert_manager.cancel_planned_for_date(date_key)
                # удаляем запись last_schedule_updates
                self.last_schedule_updates.pop(date_key, None)
                self._send(
                    chat_id, f"Отменены планы и очищены ключи для {date_key}")
                return

            if cmd == '/reload':
                # Отменяем все, очищаем кешы
                try:
                    self.alert_manager.cancel_all_planned()
                except Exception:
                    # fallback: отменить по каждой дате в planned
                    for k in list(self.alert_manager.planned_alerts):
                        # попытка извлечь дату_key из ключа
                        # ключи форматов: OFF_dd.mm.YYYY_..., ON_..., CURRENT_OFFLINE_dd.mm.YYYY_...
                        parts_k = k.split('_')
                        if len(parts_k) >= 2:
                            date_key = parts_k[1]
                            self.alert_manager.cancel_planned_for_date(
                                date_key)
                self.alert_manager.clear_daily_cache()
                self.last_schedule_updates.clear()
                self._send(
                    chat_id, "Перезагрузка: отменены все планы, очищен кеш.")
                return

            # неизвестная команда
            self._send(chat_id, "Неизвестная команда. /help для списка.")
        except Exception as e:
            logger.exception(f"Ошибка обработки команды: {e}")

    def _get_updates(self, timeout=30):
        params = {"timeout": timeout}
        if self.offset:
            params["offset"] = self.offset
        try:
            r = requests.get(f"{self.api_base}/getUpdates",
                             params=params, timeout=timeout + 5)
            r.raise_for_status()
            data = r.json()
            if not data.get('ok'):
                return []
            return data.get('result', [])
        except Exception as e:
            logger.debug(f"getUpdates error: {e}")
            return []

    async def run(self):
        logger.info("BotController запущен (polling).")
        while self.running:
            updates = self._get_updates(timeout=30)
            for upd in updates:
                try:
                    self.offset = max(self.offset or 0, upd['update_id'] + 1)
                    self._handle_command(upd)
                except Exception as e:
                    logger.exception(f"Ошибка обработки обновления: {e}")
            await asyncio.sleep(1)

    def stop(self):
        self.running = False
