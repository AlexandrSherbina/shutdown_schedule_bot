# Форматы времени
TIME_FORMAT = "%H:%M:%S"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Регулярные выражения
QUEUE_PATTERN_FORMAT = r'^\s*(?:Черга\s*)?' + \
    '{}' + r'\s*[:]\s*(.*?)(?=\n\s*(?:Черга|\Z))'
TIME_PAIRS_PATTERN = r'(\d{2})-(\d{2})'

# Сообщения об ошибках
ERROR_ENV_VARS_MISSING = "Ошибка: Не установлены все необходимые переменные окружения (TG_API_ID, TG_API_HASH, TG_BOT_TOKEN, TG_CHAT_ID)."
ERROR_CHANNEL_NOT_FOUND = "Ошибка: Не удалось получить сущность канала @{}"
ERROR_SCHEDULE_PARSE = "Ошибка при парсинге расписания: {}"

# Ограничения
MAX_HISTORY_LIMIT = 10
MIN_ALERT_DELAY = 60  # секунды
