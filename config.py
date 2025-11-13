import os
from dataclasses import dataclass


@dataclass
class TelegramConfig:
    """Параметры для Telegram API."""
    api_id: int
    api_hash: str
    bot_token: str
    chat_id: str
    channel_username: str
    session_name: str = 'power_alert_session'


@dataclass
class AlertConfig:
    """Параметры оповещений."""
    target_queue: str
    alert_minutes_before_off: int
    alert_minutes_before_on: int
    check_interval_seconds: int


def load_config() -> tuple[TelegramConfig, AlertConfig]:
    """Загружает конфигурацию из переменных окружения."""

    api_id = os.getenv('TG_API_ID', '0')
    api_hash = os.getenv('TG_API_HASH')
    bot_token = os.getenv('TG_BOT_TOKEN')
    chat_id = os.getenv('TG_CHAT_ID')

    if not all([api_id, api_hash, bot_token, chat_id]):
        raise ValueError("Не установлены необходимые переменные окружения")

    tg_config = TelegramConfig(
        api_id=int(api_id),
        api_hash=api_hash,
        bot_token=bot_token,
        chat_id=chat_id,
        channel_username=os.getenv(
            'TG_CHANNEL_USERNAME', 'SvitloSvitlovodskohoRaionu')
    )

    alert_config = AlertConfig(
        target_queue=os.getenv('TARGET_QUEUE', '1.2'),
        alert_minutes_before_off=int(os.getenv('ALERT_OFF_MINUTES', '15')),
        alert_minutes_before_on=int(os.getenv('ALERT_ON_MINUTES', '10')),
        check_interval_seconds=int(os.getenv('CHECK_INTERVAL_SECONDS', '300'))
    )

    return tg_config, alert_config
