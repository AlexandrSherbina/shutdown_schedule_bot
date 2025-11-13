# power_alert.py
import time
import re
import requests
import asyncio
from telethon import TelegramClient

# --- 1. ПАРАМЕТРЫ ДЛЯ АВТОРИЗАЦИИ (Ваш аккаунт для чтения) ---
# Получены на my.telegram.org
API_ID = 38642593  # <-- ЗАМЕНИТЕ на ваш API_ID
API_HASH = '3455e166b9dfcee8f883e8ab4ae52ee6'  # <-- ЗАМЕНИТЕ на ваш API_HASH
SESSION_NAME = 'power_alert_session'  # Имя файла сессии. Не меняйте.

# --- 2. ПАРАМЕТРЫ УВЕДОМЛЕНИЙ (Ваш бот для отправки) ---
# <-- ЗАМЕНИТЕ на токен вашего бота
BOT_TOKEN = '8333707550:AAEExWqLWk5LZrqOP7jhV7Ywo05ubc27dfs'
# <-- ЗАМЕНИТЕ на ваш личный Chat ID (получен через @userinfobot)
CHAT_ID = 484908554

# --- 3. ПАРАМЕТРЫ ПОИСКА И ЛОГИКА ---
CHANNEL_USERNAME = 'SvitloSvitlovodskohoRaionu'
# ВАША ОЧЕРЕДЬ, которую ищем в тексте
TARGET_QUEUE = '1.2'
# Сколько минут до отключения нужно отправить уведомление
ALERT_MINUTES_BEFORE = 15
# Интервал проверки канала в секундах (5 минут)
CHECK_INTERVAL_SECONDS = 300

# Переменная для хранения ID последнего обработанного сообщения
LAST_PROCESSED_MESSAGE_ID = 0

# URL для отправки уведомлений через бота
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# --- ФУНКЦИИ ---


def send_alert(message_text):
    """Отправляет сообщение через Telegram-бота с принудительным звуком."""
    payload = {
        'chat_id': CHAT_ID,
        'text': message_text,
        # disable_notification=False гарантирует, что уведомление будет со звуком
        'disable_notification': False,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(TELEGRAM_URL, data=payload, timeout=10)
        response.raise_for_status()
        print(
            f"[{time.strftime('%H:%M:%S')}] Уведомление успешно отправлено.")
    except requests.exceptions.RequestException as e:
        print(f"[{time.strftime('%H:%M:%S')}] Ошибка при отправке уведомления: {e}")


def parse_schedule(text, target_queue):
    """Ищет в тексте время отключения для указанной очереди."""
    pattern = re.compile(
        r'(' + re.escape(target_queue) +
        r')\s*[:\-]?\s*(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})',
        re.IGNORECASE
    )

    matches = pattern.findall(text)

    periods = []
    if not matches:
        return periods

    for match in matches:
        start_time_str = match[1]
        end_time_str = match[2]
        # Нормализуем форматы Ч:М -> ЧЧ:ММ
        start_time_str = ':'.join(part.zfill(2)
                                  for part in start_time_str.split(':'))
        end_time_str = ':'.join(part.zfill(2)
                                for part in end_time_str.split(':'))
        periods.append((start_time_str, end_time_str))

    return periods


async def main():
    global LAST_PROCESSED_MESSAGE_ID

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    print("--- Парсер Telegram Света Запущен ---")
    print(f"[{time.strftime('%H:%M:%S')}] Ожидание новых сообщений в канале: @{CHANNEL_USERNAME}")
    print(f"[{time.strftime('%H:%M:%S')}] Отслеживаемая очередь: {TARGET_QUEUE}")

    # --- ВРЕМЕННЫЙ КОД ДЛЯ ТЕСТА СВЯЗИ С БОТОМ ---
    # print(f"[{time.strftime('%H:%M:%S')}] Тестовый вызов функции send_alert...")
    # test_message = f"✅ *ТЕСТ УСПЕШЕН!* Ваш бот и Chat ID работают правильно. Сообщение пришло со звуком. [{time.strftime('%H:%M:%S')}]"
    # send_alert(test_message)
    # print(
    #     f"[{time.strftime('%H:%M:%S')}] Тест завершен. Скрипт остановится через 10 секунд.")
    # await client.disconnect()  # Отключаемся от Telethon
    # time.sleep(10)
    # return  # Завершаем работу скрипта после теста
    # -----------------------------------------------

    try:
        channel_entity = await client.get_entity(CHANNEL_USERNAME)
    except Exception as e:
        print(
            f"[{time.strftime('%H:%M:%S')}] Не удалось получить сущность канала @{CHANNEL_USERNAME}: {e}")
        return

    # Устанавливаем последний обработанный ID как последний доступный, чтобы не обрабатывать старые сообщения при старте
    try:
        last_msgs = await client.get_messages(channel_entity, limit=1)
        if last_msgs:
            LAST_PROCESSED_MESSAGE_ID = last_msgs[0].id
            print(
                f"[{time.strftime('%H:%M:%S')}] Установлен LAST_PROCESSED_MESSAGE_ID = {LAST_PROCESSED_MESSAGE_ID}")
    except Exception as e:
        print(
            f"[{time.strftime('%H:%M:%S')}] Ошибка при получении последних сообщений: {e}")

    while True:
        try:
            messages = await client.get_messages(channel_entity, limit=5)
            new_messages = [m for m in messages if getattr(
                m, 'id', 0) > LAST_PROCESSED_MESSAGE_ID and getattr(m, 'message', None)]

            if new_messages:
                # messages приходят от нового к старому, сохраняем максимальный id
                LAST_PROCESSED_MESSAGE_ID = max(
                    m.id for m in new_messages if getattr(m, 'id', None) is not None)
                print(
                    f"[{time.strftime('%H:%M:%S')}] Найдено {len(new_messages)} новых сообщений.")

                for message in reversed(new_messages):
                    text = message.message or ""
                    periods = parse_schedule(text, TARGET_QUEUE)

                    if periods:
                        print(
                            f"[{time.strftime('%H:%M:%S')}] В сообщении ID {message.id} найден график для очереди {TARGET_QUEUE}.")

                        for start_time_str, end_time_str in periods:
                            now = time.localtime()
                            full_start_time_str = f"{now.tm_year}-{now.tm_mon:02d}-{now.tm_mday:02d} {start_time_str}:00"

                            try:
                                start_timestamp = time.mktime(time.strptime(
                                    full_start_time_str, "%Y-%m-%d %H:%M:%S"))
                                alert_timestamp = start_timestamp - \
                                    (ALERT_MINUTES_BEFORE * 60)
                                time_to_alert = alert_timestamp - time.time()

                                if time_to_alert > 0:
                                    alert_datetime_str = time.strftime(
                                        '%H:%M', time.localtime(alert_timestamp))

                                    alert_message = (
                                        f"🚨 *ВНИМАНИЕ! ОТКЛЮЧЕНИЕ СВЕТА!* 🚨\n\n"
                                        f"Ваша очередь **{TARGET_QUEUE}** будет отключена в *{start_time_str}* (до *{end_time_str}*).\n"
                                        f"⏰ *УВЕДОМЛЕНИЕ:* Сработает в *{alert_datetime_str}* (за {ALERT_MINUTES_BEFORE} мин.)."
                                    )

                                    # Отправляем в отдельном потоке, чтобы не блокировать цикл событий
                                    await asyncio.to_thread(send_alert, alert_message)

                                    print(
                                        f"[{time.strftime('%H:%M:%S')}] Ожидание {int(time_to_alert // 60)} мин. до звукового уведомления...")
                                    # Ждем до времени оповещения (не блокирует event loop)
                                    await asyncio.sleep(time_to_alert)

                                    final_message = f"⚡️ *СВЕТ ОТКЛЮЧАТ ЧЕРЕЗ {ALERT_MINUTES_BEFORE} МИНУТ!* 📢\n\n(Плановое отключение в {start_time_str} до {end_time_str} для очереди {TARGET_QUEUE})"
                                    await asyncio.to_thread(send_alert, final_message)

                                else:
                                    print(
                                        f"[{time.strftime('%H:%M:%S')}] Отключение в {start_time_str} уже в прошлом или вот-вот начнется. Пропускаем.")

                            except ValueError as ve:
                                print(
                                    f"[{time.strftime('%H:%M:%S')}] Ошибка обработки времени: {ve}. Проверьте формат времени в канале.")

                    else:
                        print(
                            f"[{time.strftime('%H:%M:%S')}] Сообщение ID {message.id} не содержит графика для очереди {TARGET_QUEUE}.")

            else:
                print(
                    f"[{time.strftime('%H:%M:%S')}] Новых сообщений нет. Спящий режим на {CHECK_INTERVAL_SECONDS // 60} мин.")

        except Exception as e:
            print(
                f"[{time.strftime('%H:%M:%S')}] Произошла непредвиденная ошибка: {e}")
            # Небольшая пауза при ошибке, чтобы не входить в горячий цикл
            await asyncio.sleep(60)

        # Ждем перед следующей проверкой (не блокирует event loop)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


# Запускаем асинхронную функцию
if __name__ == '__main__':
    asyncio.run(main())
