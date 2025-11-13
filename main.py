import asyncio
import time
from config import load_config
from logger import logger
from telegram_client import TelegramClientWrapper
from schedule_parser import ScheduleParser
from date_parser import DateParser
from message_builder import MessageBuilder
from alert_manager import AlertManager
import constants


async def main():
    """Главный цикл приложения."""

    try:
        # Загружаем конфигурацию
        tg_config, alert_config = load_config()
        logger.info("✓ Конфигурация загружена")
    except ValueError as e:
        logger.error(f"{constants.ERROR_ENV_VARS_MISSING}\n{e}")
        return

    # Инициализируем компоненты
    tg_client = TelegramClientWrapper(tg_config)
    parser = ScheduleParser(alert_config.target_queue)
    date_parser = DateParser()  # ← НОВОЕ
    builder = MessageBuilder(
        alert_config.target_queue,
        alert_config.alert_minutes_before_off,
        alert_config.alert_minutes_before_on
    )
    alert_manager = AlertManager(tg_config.bot_token, tg_config.chat_id)

    try:
        await tg_client.connect()
        channel = await tg_client.get_channel()
        logger.info(f"Отслеживается очередь: {alert_config.target_queue}")

        while True:
            try:
                messages = await tg_client.get_recent_messages(channel)

                for message in messages:
                    if not message.message:
                        continue

                    # ← НОВОЕ: Парсим дату из сообщения
                    schedule_date = date_parser.parse_date(message.message)

                    # Проверяем, не устарел ли график
                    if not date_parser.is_schedule_valid(schedule_date):
                        logger.info(
                            f"Пропускаем устаревший график (сообщение ID: {message.id})")
                        continue

                    # Устанавливаем дату в парсер
                    parser.set_schedule_date(schedule_date)

                    periods = parser.parse(message.message)

                    if not periods:
                        continue

                    logger.info(
                        f"Найден график на {schedule_date.strftime('%d.%m.%Y')} (ID: {message.id})")

                    for period_start, period_end, apply_date in periods:
                        await process_period(
                            alert_manager, builder, alert_config,
                            period_start, period_end, apply_date
                        )

                logger.info(f"Запланировано: {len(alert_manager.planned_alerts)} оповещений. "
                            f"Спящий режим {alert_config.check_interval_seconds // 60} мин")

                await asyncio.sleep(alert_config.check_interval_seconds)

            except Exception as e:
                logger.error(f"Ошибка в цикле: {e}")
                await asyncio.sleep(60)

    finally:
        await tg_client.disconnect()


async def process_period(alert_manager, builder, alert_config, period_start, period_end, schedule_date):
    """Обрабатывает один период отключения/включения с учетом даты."""

    now_ts = time.time()

    # ← ВАЖНО: Используем дату из графика, а не текущую дату!
    start_ts = time.mktime(time.strptime(
        f"{schedule_date.year}-{schedule_date.month:02d}-{schedule_date.day:02d} {period_start}:00",
        "%Y-%m-%d %H:%M:%S"
    ))

    # Если время уже прошло — пропускаем
    if start_ts < now_ts:
        logger.debug(
            f"Время {period_start} уже прошло для даты {schedule_date.strftime('%d.%m.%Y')}")
        return

    # Отключение (OFF)
    off_alert_ts = start_ts - (alert_config.alert_minutes_before_off * 60)
    if off_alert_ts > now_ts + constants.MIN_ALERT_DELAY:
        off_key = f"OFF_{schedule_date.strftime('%d.%m.%Y')}_{period_start}_{period_end}"
        if off_key not in alert_manager.planned_alerts:
            off_time = time.strftime('%H:%M', time.localtime(off_alert_ts))
            msg = builder.initial_off_message(
                period_start, period_end, off_time)
            alert_manager.send_alert(msg)
            alert_manager.planned_alerts.add(off_key)

            final_msg = builder.final_off_message(period_start, period_end)
            delay = off_alert_ts - now_ts
            asyncio.create_task(
                alert_manager.schedule_delayed_alert(
                    'OFF', delay, final_msg, off_key)
            )

    # Включение (ON)
    end_ts = time.mktime(time.strptime(
        f"{schedule_date.year}-{schedule_date.month:02d}-{schedule_date.day:02d} {period_end}:00",
        "%Y-%m-%d %H:%M:%S"
    ))

    on_alert_ts = end_ts - (alert_config.alert_minutes_before_on * 60)
    if on_alert_ts > now_ts + constants.MIN_ALERT_DELAY:
        on_key = f"ON_{schedule_date.strftime('%d.%m.%Y')}_{period_start}_{period_end}"
        if on_key not in alert_manager.planned_alerts:
            on_time = time.strftime('%H:%M', time.localtime(on_alert_ts))
            msg = builder.initial_on_message(period_end, on_time)
            alert_manager.send_alert(msg)
            alert_manager.planned_alerts.add(on_key)

            final_msg = builder.final_on_message(period_end)
            delay = on_alert_ts - now_ts
            asyncio.create_task(
                alert_manager.schedule_delayed_alert(
                    'ON', delay, final_msg, on_key)
            )


if __name__ == '__main__':
    asyncio.run(main())
