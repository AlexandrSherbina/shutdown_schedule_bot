import asyncio
import time
from datetime import datetime
from config import load_config
from logger import logger
from telegram_client import TelegramClientWrapper
from schedule_parser import ScheduleParser
from date_parser import DateParser
from interval_checker import IntervalChecker
from message_builder import MessageBuilder
from alert_manager import AlertManager
import constants


async def main():
    """Главный цикл приложения."""

    try:
        tg_config, alert_config = load_config()
        logger.info("✓ Конфигурация загружена")
    except ValueError as e:
        logger.error(f"{constants.ERROR_ENV_VARS_MISSING}\n{e}")
        return

    tg_client = TelegramClientWrapper(tg_config)
    parser = ScheduleParser(alert_config.target_queue)
    date_parser = DateParser()
    interval_checker = IntervalChecker()
    builder = MessageBuilder(
        alert_config.target_queue,
        alert_config.alert_minutes_before_off,
        alert_config.alert_minutes_before_on
    )
    alert_manager = AlertManager(tg_config.bot_token, tg_config.chat_id)

    last_day = None  # Отслеживаем день для очистки кеша
    # ключ: 'dd.mm.YYYY' -> datetime последнего обработанного обновления
    last_schedule_updates = {}

    try:
        await tg_client.connect()
        channel = await tg_client.get_channel()
        logger.info(f"Отслеживается очередь: {alert_config.target_queue}")

        while True:
            try:
                # очистка кеша в полночь
                current_day = datetime.now().day
                if last_day is not None and last_day != current_day:
                    alert_manager.clear_daily_cache()
                    last_schedule_updates.clear()
                last_day = current_day

                messages = await tg_client.get_recent_messages(channel)

                for message in messages:
                    if not message.message:
                        continue

                    # parse_date теперь возвращает (schedule_date, update_dt)
                    schedule_date, update_dt = date_parser.parse_date(
                        message.message)
                    date_key = schedule_date.strftime('%d.%m.%Y')

                    # если уже есть сохранённое время обновления — сравниваем
                    prev_update = last_schedule_updates.get(date_key)

                    # если в сообщении нет времени обновления, считаем его "ненулевым" — обрабатываем только если нет prev_update
                    if update_dt is None and prev_update is not None:
                        # уже обработана более точная версия — пропускаем
                        logger.debug(
                            f"Пропускаем сообщение без времени обновления для {date_key} (уже есть обновление)")
                        continue

                    # если есть предыдущее и текущее update_dt <= prev_update — пропускаем (старое сообщение)
                    if update_dt is not None and prev_update is not None and update_dt <= prev_update:
                        logger.debug(
                            f"Пропускаем старое обновление для {date_key} ({update_dt} <= {prev_update})")
                        continue

                    # если пришло новое обновление (update_dt > prev_update) — нужно отменить старые планы для этой даты
                    if prev_update is not None and (update_dt is None or update_dt > prev_update):
                        logger.info(
                            f"Найдено новое обновление графика для {date_key}. Отменяю старые планы.")
                        alert_manager.cancel_planned_for_date(date_key)

                    # сохраняем время последней обработки (если есть) - если нет, помечаем текущим временем
                    last_schedule_updates[date_key] = update_dt or datetime.now(
                    )

                    # далее логика парсинга периодов и планирования (как раньше)
                    parser.set_schedule_date(schedule_date)
                    periods = parser.parse(message.message)
                    if not periods:
                        continue

                    logger.info(
                        f"Найден график на {date_key} (ID: {message.id})")

                    # проверка текущего оффлай статуса и отправка одного сообщения
                    is_currently_offline = interval_checker.is_currently_offline(
                        [(p[0], p[1]) for p in periods]
                    )
                    if is_currently_offline:
                        current_period = interval_checker.get_current_offline_period(
                            [(p[0], p[1]) for p in periods]
                        )
                        if current_period:
                            current_offline_key = f"CURRENT_OFFLINE_{date_key}_{current_period[0]}_{current_period[1]}"
                            msg = builder.current_offline_message(
                                current_period[0], current_period[1])
                            if alert_manager.send_alert(msg, alert_key=current_offline_key):
                                logger.info(
                                    "Сообщение о текущем отключении отправлено")
                            else:
                                logger.debug(
                                    "Сообщение уже было отправлено ранее")

                    for period_start, period_end, apply_date in periods:
                        await process_period(
                            alert_manager, builder, alert_config, interval_checker,
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


async def process_period(alert_manager, builder, alert_config, interval_checker,
                         period_start, period_end, schedule_date):
    """Обрабатывает один период отключения/включения с учетом даты."""

    now_ts = time.time()

    start_ts = time.mktime(time.strptime(
        f"{schedule_date.year}-{schedule_date.month:02d}-{schedule_date.day:02d} {period_start}:00",
        "%Y-%m-%d %H:%M:%S"
    ))

    if start_ts < now_ts:
        logger.debug(
            f"Время {period_start} уже прошло для даты {schedule_date.strftime('%d.%m.%Y')}")
        return

    is_in_current_interval = interval_checker.is_in_interval(
        period_start, period_end)

    if is_in_current_interval:
        logger.info(
            f"Мы находимся в интервале отключения {period_start}-{period_end}")
    else:
        # ← ОТКЛЮЧЕНИЕ (OFF)
        off_alert_ts = start_ts - (alert_config.alert_minutes_before_off * 60)
        if off_alert_ts > now_ts + constants.MIN_ALERT_DELAY:
            off_key = f"OFF_{schedule_date.strftime('%d.%m.%Y')}_{period_start}_{period_end}"
            if off_key not in alert_manager.planned_alerts:
                off_time = time.strftime('%H:%M', time.localtime(off_alert_ts))
                msg = builder.initial_off_message(
                    period_start, period_end, off_time)

                # ← ПРОВЕРКА НА ДУБЛИКАТ с ключом
                if alert_manager.send_alert(msg, alert_key=off_key):
                    alert_manager.planned_alerts.add(off_key)

                    final_msg = builder.final_off_message(
                        period_start, period_end)
                    delay = off_alert_ts - now_ts
                    asyncio.create_task(
                        alert_manager.schedule_delayed_alert(
                            'OFF', delay, final_msg, off_key)
                    )

    # ← ВКЛЮЧЕНИЕ (ON)
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

            # ← ПРОВЕРКА НА ДУБЛИКАТ с ключом
            if alert_manager.send_alert(msg, alert_key=on_key):
                alert_manager.planned_alerts.add(on_key)

                final_msg = builder.final_on_message(period_end)
                delay = on_alert_ts - now_ts

                logger.info(f"Запланировано напоминание о включении в {period_end} "
                            f"(через {int(delay / 60)} мин)")

                asyncio.create_task(
                    alert_manager.schedule_delayed_alert(
                        'ON', delay, final_msg, on_key)
                )
    else:
        logger.debug(f"Напоминание о включении {period_end} уже прошло")


if __name__ == '__main__':
    asyncio.run(main())
