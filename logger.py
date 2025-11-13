import logging
import sys
import io


def setup_logger(name: str, level=logging.INFO) -> logging.Logger:
    """Настраивает логгер с форматированием и UTF-8 кодировкой."""

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers = []  # Очищаем старые handlers

    # Формат логов
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # === Вывод в консоль с UTF-8 ===
    try:
        # Пытаемся переконфигурировать stdout в UTF-8
        if sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # === Вывод в файл логов с UTF-8 ===
    try:
        file_handler = logging.FileHandler(
            'logs/power_alert.log', encoding='utf-8', mode='a')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"[WARNING] Не удалось создать файловый handler: {e}")

    return logger


logger = setup_logger('power_alert')
