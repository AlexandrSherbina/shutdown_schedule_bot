import asyncio
import os
from telethon import TelegramClient

from config import TelegramConfig
from logger import logger
import constants


class TelegramClientWrapper:
    """Обертка над Telethon для удобства."""

    def __init__(self, config: TelegramConfig):
        self.config = config
        self.session_file = f"{config.session_name}.session"
        self.client = TelegramClient(
            config.session_name, config.api_id, config.api_hash)

    async def connect(self) -> None:
        """Подключается к аккаунту (с проверкой существующей сессии)."""

        # Проверяем, существует ли файл сессии
        if not os.path.exists(self.session_file):
            logger.error(f"❌ Файл сессии не найден: {self.session_file}")
            logger.error(
                "ПЕРВЫЙ ЗАПУСК: запустите telethon_auth.py для авторизации")
            raise FileNotFoundError(
                f"Session file not found: {self.session_file}")

        try:
            logger.info(f"Подключаюсь, используя сессию: {self.session_file}")
            # ← ДОБАВЛЕНЫ ПАРАМЕТРЫ для стабильности
            await asyncio.wait_for(
                self.client.connect(),
                timeout=30  # ← УВЕЛИЧЕН ТАЙМАУТ до 30 сек
            )

            # Проверяем авторизацию
            is_user_authorized = await self.client.is_user_authorized()
            if not is_user_authorized:
                logger.error(
                    "❌ Пользователь не авторизован. Запустите telethon_auth.py")
                raise RuntimeError("User not authorized")

            logger.info("✓ Подключено к Telegram")
        except asyncio.TimeoutError:
            logger.error("❌ Таймаут подключения к Telegram (30 сек)")
            logger.warning("Попробуйте:")
            logger.warning("1. Проверьте интернет соединение")
            logger.warning(
                "2. Удалите файл сессии и запустите telethon_auth.py заново")
            logger.warning("3. Используйте proxy если Telegram заблокирован")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка подключения: {e}")
            raise

    async def get_channel(self):
        """Получает сущность канала."""
        try:
            entity = await self.client.get_entity(self.config.channel_username)
            logger.info(f"✓ Получен канал: {self.config.channel_username}")
            return entity
        except Exception as e:
            logger.error(constants.ERROR_CHANNEL_NOT_FOUND.format(
                self.config.channel_username))
            raise

    async def get_recent_messages(self, channel, limit: int = constants.MAX_HISTORY_LIMIT):
        """Получает последние сообщения из канала."""
        try:
            return await self.client.get_messages(channel, limit=limit)
        except Exception as e:
            logger.error(f"Ошибка получения сообщений: {e}")
            return []

    async def disconnect(self) -> None:
        """Отключается от Telegram."""
        try:
            await self.client.disconnect()
            logger.info("✓ Отключено от Telegram")
        except Exception as e:
            logger.error(f"Ошибка отключения: {e}")
