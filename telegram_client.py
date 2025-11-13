from telethon import TelegramClient
from config import TelegramConfig
from logger import logger
import constants


class TelegramClientWrapper:
    """Обертка над Telethon для удобства."""

    def __init__(self, config: TelegramConfig):
        self.config = config
        self.client = TelegramClient(
            config.session_name, config.api_id, config.api_hash)

    async def connect(self) -> None:
        """Подключается к аккаунту."""
        await self.client.start()
        logger.info("✓ Подключено к Telegram")

    async def get_channel(self):
        """Получает сущность канала."""
        try:
            return await self.client.get_entity(self.config.channel_username)
        except Exception as e:
            logger.error(constants.ERROR_CHANNEL_NOT_FOUND.format(
                self.config.channel_username))
            raise

    async def get_recent_messages(self, channel, limit: int = constants.MAX_HISTORY_LIMIT):
        """Получает последние сообщения из канала."""
        return await self.client.get_messages(channel, limit=limit)

    async def disconnect(self) -> None:
        """Отключается от Telegram."""
        await self.client.disconnect()
        logger.info("✓ Отключено от Telegram")
