# power_alert.py - Версия с переменными окружения
import time
import re
import requests
import asyncio
import os  # <-- Добавлен модуль для работы с окружением
from telethon import TelegramClient

# --- 1. ПАРАМЕТРЫ ДЛЯ АВТОРИЗАЦИИ И УВЕДОМЛЕНИЙ ---
# Если переменная не установлена, программа выдаст ошибку, чтобы вы не забыли ее задать.

# Имя файла сессии Telethon (нужно для входа). Не является секретом.
SESSION_NAME = 'power_alert_session'

API_ID = int(os.getenv('TG_API_ID', '0'))  # Должно быть число
API_HASH = os.getenv('TG_API_HASH')
BOT_TOKEN = os.getenv('TG_BOT_TOKEN')
CHAT_ID = os.getenv('TG_CHAT_ID')  # Может быть строкой, если Channel ID

# --- 2. ПАРАМЕТРЫ ПОИСКА И ЛОГИКА ---
CHANNEL_USERNAME = os.getenv(
    'TG_CHANNEL_USERNAME', 'SvitloSvitlovodskohoRaionu')
TARGET_QUEUE = os.getenv('TARGET_QUEUE', '1.2')
ALERT_MINUTES_BEFORE_OFF = int(os.getenv('ALERT_OFF_MINUTES', '15'))
ALERT_MINUTES_BEFORE_ON = int(os.getenv('ALERT_ON_MINUTES', '10'))
CHECK_INTERVAL_SECONDS = int(os.getenv('CHECK_INTERVAL_SECONDS', '300'))

# Проверка, что все необходимые переменные установлены
if not all([API_ID, API_HASH, BOT_TOKEN, CHAT_ID]):
    print("Ошибка: Не установлены все необходимые переменные окружения (TG_API_ID, TG_API_HASH, TG_BOT_TOKEN, TG_CHAT_ID).")
    exit(1)

# Глобальные переменные состояния
PLANNED_ALERTS = set()
SENT_MESSAGES_HASHES = set()  # <-- НОВЫЙ SET для отслеживания уникальности текста

# URL для отправки уведомлений через бота
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# --- ФУНКЦИИ ---


def send_alert(message_text):
    """Отправляет сообщение через Telegram-бота с принудительным звуком."""

    # Создаем уникальный хеш текста для проверки
    message_hash = hash(message_text)

    if message_hash in SENT_MESSAGES_HASHES:
        # Если такой же текст был отправлен недавно, игнорируем
        return

    SENT_MESSAGES_HASHES.add(message_hash)

    payload = {
        'chat_id': CHAT_ID,
        'text': message_text,
        'disable_notification': False,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(TELEGRAM_URL, data=payload)
        response.raise_for_status()
        # Убрал вывод message_text, чтобы не печатать секретный текст в логах
        print(f"[{time.strftime('%H:%M:%S')}] Уведомление успешно отправлено.")
    except requests.exceptions.RequestException as e:
        print(f"[{time.strftime('%H:%M:%S')}] Ошибка при отправке уведомления: {e}")


# ... (Остальной код и импорты остаются без изменений) ...

# power_alert.py (ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ PARSE_SCHEDULE)

def parse_schedule(text, target_queue):
    # ... (комментарии) ...

    # Новый, ультра-агрессивный паттерн:
    # Ищем строго начало строки (^) с нашей очередью,
    # и захватываем все (.*?) до СЛЕДУЮЩЕЙ очереди (Черга \d) или конца текста (\Z).
    queue_pattern = re.compile(
        r'^\s*(?:Черга\s*)?' + re.escape(target_queue) +
        r'\s*[:]\s*(.*?)(?=\n\s*(?:Черга|\Z))',
        re.MULTILINE | re.IGNORECASE
    )

    match = queue_pattern.search(text)

    if not match:
        return []

    # match.group(1) - это текст с расписанием: "02-04, 06-08, 10-12, 13-16, 18-20"
    schedule_text = match.group(1).strip()

    # Шаг 2: Ищем все пары ЧЧ-ЧЧ
    time_pairs_pattern = re.compile(r'(\d{2})-(\d{2})')

    time_pairs = time_pairs_pattern.findall(schedule_text)

    periods = []
    for start_hour, end_hour in time_pairs:
        # Шаг 3: Преобразуем формат "02-04" в "02:00 - 04:00"
        periods.append((f"{start_hour}:00", f"{end_hour}:00"))

    return periods


# ... (Остальной код остается без изменений) ...


async def delayed_alert_task(alert_type, delay_seconds, period_start, period_end):
    """Асинхронная задача, которая ждет и отправляет финальное уведомление."""

    print(f"[{time.strftime('%H:%M:%S')}] Планирование {alert_type} через {int(delay_seconds // 60)} минут.")
    await asyncio.sleep(delay_seconds)

    if alert_type == 'OFF':
        final_msg = (
            f"⚡️ *СВЕТ ОТКЛЮЧАТ ЧЕРЕЗ {ALERT_MINUTES_BEFORE_OFF} МИНУТ!* 📢\n\n"
            f"Плановое *отключение* в {period_start} до {period_end} для очереди {TARGET_QUEUE}."
        )
    else:  # ON
        final_msg = (
            f"💡 *СВЕТ ВКЛЮЧАТ ЧЕРЕЗ {ALERT_MINUTES_BEFORE_ON} МИНУТ!* 🎉\n\n"
            f"Плановое *включение* в {period_end} для очереди {TARGET_QUEUE}."
        )

    send_alert(final_msg)
    PLANNED_ALERTS.discard(f"{alert_type}_{period_start}_{period_end}")


async def main():

    # Подключение к аккаунту
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    print("--- Парсер Telegram Света Запущен ---")
    print(f"[{time.strftime('%H:%M:%S')}] Ожидание новых/актуальных сообщений в канале: @{CHANNEL_USERNAME}")

    channel_entity = await client.get_entity(CHANNEL_USERNAME)

    while True:
        try:
            # --- 1. ОБРАБАТЫВАЕМ ВСЕ НАЙДЕННЫЕ ГРАФИКИ В ПОСЛЕДНИХ 10 СООБЩЕНИЯХ ---

            # Скрипт проверяет последние 10 сообщений, чтобы не пропустить актуальный график
            messages = await client.get_messages(channel_entity, limit=10)

            # --- 1. ОБРАБАТЫВАЕМ ВСЕ НАЙДЕННЫЕ ГРАФИКИ В ПОСЛЕДНИХ 10 СООБЩЕНИЯХ ---
            for message in messages:
                if not message.message:
                    continue

                periods = parse_schedule(message.message, TARGET_QUEUE)

                if periods:
                    print(
                        f"[{time.strftime('%H:%M:%S')}] В сообщении ID {message.id} найден график. Анализируем...")

                    for period_start, period_end in periods:
                        # --- ОБРАБОТКА 24:00 ---
                        if period_end == '24:00':
                            period_end = '00:00'
                        # -----------------------

                        # --- А. ПЛАНИРУЕМ ОТКЛЮЧЕНИЕ (OFF) ---
                        now_ts = time.time()
                        now_date = time.localtime()
                        start_time_ts = time.mktime(time.strptime(
                            f"{now_date.tm_year}-{now_date.tm_mon:02d}-{now_date.tm_mday:02d} {period_start}:00",
                            "%Y-%m-%d %H:%M:%S"
                        ))
                        off_alert_ts = start_time_ts - \
                            (ALERT_MINUTES_BEFORE_OFF * 60)

                        if off_alert_ts > now_ts + 60:
                            off_alert_key = f"OFF_{period_start}_{period_end}"

                            if off_alert_key not in PLANNED_ALERTS:

                                # ВОССТАНОВЛЕН ПОЛНЫЙ ТЕКСТ СООБЩЕНИЯ
                                initial_msg_off = (
                                    f"🚨 *ОБНОВЛЕНИЕ ГРАФИКА! ОТКЛЮЧЕНИЕ:* 🚨\n\n"
                                    f"Ваша очередь **{TARGET_QUEUE}** будет отключена в *{period_start}* (до *{period_end}*).\n"
                                    f"⏰ Напоминание сработает в {time.strftime('%H:%M', time.localtime(off_alert_ts))}."
                                )
                                send_alert(initial_msg_off)

                                PLANNED_ALERTS.add(off_alert_key)

                                delay_seconds = off_alert_ts - now_ts
                                asyncio.create_task(delayed_alert_task(
                                    'OFF', delay_seconds, period_start, period_end))

                        # --- Б. ПЛАНИРУЕМ ВКЛЮЧЕНИЕ (ON) ---

                        end_time_ts = time.mktime(time.strptime(
                            f"{now_date.tm_year}-{now_date.tm_mon:02d}-{now_date.tm_mday:02d} {period_end}:00",
                            "%Y-%m-%d %H:%M:%S"
                        ))
                        on_alert_ts = end_time_ts - \
                            (ALERT_MINUTES_BEFORE_ON * 60)

                        if on_alert_ts > now_ts + 60:
                            on_alert_key = f"ON_{period_start}_{period_end}"

                            if on_alert_key not in PLANNED_ALERTS:

                                # ВОССТАНОВЛЕН ПОЛНЫЙ ТЕКСТ СООБЩЕНИЯ
                                initial_msg_on = (
                                    f"💡 *ОБНОВЛЕНИЕ ГРАФИКА! ВКЛЮЧЕНИЕ:* 💡\n\n"
                                    f"Ваша очередь **{TARGET_QUEUE}** будет включена в *{period_end}*.\n"
                                    f"⏰ Напоминание сработает в {time.strftime('%H:%M', time.localtime(on_alert_ts))}."
                                )
                                send_alert(initial_msg_on)

                                PLANNED_ALERTS.add(on_alert_key)

                                delay_seconds = on_alert_ts - now_ts
                                asyncio.create_task(delayed_alert_task(
                                    'ON', delay_seconds, period_start, period_end))

            print(f"[{time.strftime('%H:%M:%S')}] Сканирование завершено. Запланировано: {len(PLANNED_ALERTS)} оповещений. Спящий режим на {CHECK_INTERVAL_SECONDS // 60} мин.")

        except Exception as e:
            print(
                f"[{time.strftime('%H:%M:%S')}] Произошла непредвиденная ошибка: {e}")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

# Запускаем асинхронную функцию
if __name__ == '__main__':
    asyncio.run(main())
