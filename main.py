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
        logger.info("Загружаю конфигурацию...")
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

    last_day = None
    last_schedule_updates = {}

    # Запуск контроллера бота (async task)
    try:
        logger.info("Инициализирую BotController...")
        from bot_controller import BotController
        bot_ctrl = BotController(tg_config.bot_token, tg_config.chat_id,
                                 parser, alert_manager, alert_config, last_schedule_updates)
        bot_task = asyncio.create_task(bot_ctrl.run())
        logger.info("✓ BotController запущен в фоне")
    except Exception as e:
        logger.error(f"Ошибка инициализации BotController: {e}")
        bot_task = None

    try:
        logger.info("Подключаюсь к Telegram...")
        await asyncio.wait_for(tg_client.connect(), timeout=10)
        logger.info("✓ Подключено к Telegram")
    except asyncio.TimeoutError:
        logger.error("Таймаут подключения к Telegram (10 сек)")
        return
    except Exception as e:
        logger.error(f"Ошибка подключения к Telegram: {e}")
        return

    try:
        logger.info("Получаю канал...")
        channel = await asyncio.wait_for(tg_client.get_channel(), timeout=10)
        logger.info(f"✓ Отслеживается очередь: {alert_config.target_queue}")
    except asyncio.TimeoutError:
        logger.error("Таймаут получения канала (10 сек)")
        await tg_client.disconnect()
        return
    except Exception as e:
        logger.error(f"Ошибка получения канала: {e}")
        await tg_client.disconnect()
        return

    try:
        while True:
            try:
                # очистка кеша в полночь
                current_day = datetime.now().day
                if last_day is not None and last_day != current_day:
                    alert_manager.clear_daily_cache()
                    last_schedule_updates.clear()
                last_day = current_day

                logger.debug("Получаю последние сообщения...")
                messages = await asyncio.wait_for(tg_client.get_recent_messages(channel), timeout=15)
                logger.debug(f"Получено {len(messages)} сообщений")

                for message in messages:
                    if not message.message:
                        continue

                    schedule_date, update_dt = date_parser.parse_date(
                        message.message)
                    date_key = schedule_date.strftime('%d.%m.%Y')

                    prev_update = last_schedule_updates.get(date_key)

                    if update_dt is None and prev_update is not None:
                        logger.debug(
                            f"Пропускаю сообщение без времени обновления для {date_key}")
                        continue

                    if update_dt is not None and prev_update is not None and update_dt <= prev_update:
                        logger.debug(
                            f"Пропускаю старое обновление для {date_key}")
                        continue

                    if prev_update is not None and (update_dt is None or update_dt > prev_update):
                        logger.info(
                            f"Новое обновление графика для {date_key}. Отменяю старые планы.")
                        alert_manager.cancel_planned_for_date(date_key)

                    last_schedule_updates[date_key] = update_dt or datetime.now(
                    )

                    parser.set_schedule_date(schedule_date)
                    periods = parser.parse(message.message)

                    if not periods:
                        continue

                    logger.info(
                        f"Найден график на {date_key} (ID: {message.id})")

                    is_currently_offline = interval_checker.is_currently_offline(
                        periods)

                    if is_currently_offline:
                        current_period = interval_checker.get_current_offline_period(
                            periods)
                        if current_period:
                            period_start, period_end, apply_date = current_period
                            apply_date_key = apply_date.strftime('%d.%m.%Y') if hasattr(
                                apply_date, 'strftime') else str(apply_date)

                            current_offline_key = f"CURRENT_OFFLINE_{apply_date_key}_{period_start}_{period_end}"
                            msg = builder.current_offline_message(
                                period_start, period_end)

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

            except asyncio.TimeoutError:
                logger.warning(
                    "Таймаут при получении сообщений (15 сек), продолжаю...")
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Ошибка в цикле: {e}")
                await asyncio.sleep(60)

    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания (Ctrl+C)")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        logger.info("Отключаюсь от Telegram...")
        await tg_client.disconnect()
        if bot_task:
            bot_task.cancel()
        logger.info("✓ Приложение остановлено")


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
        period_start, period_end, schedule_date)

    if is_in_current_interval:
        logger.info(
            f"Мы находимся в интервале отключения {period_start}-{period_end} на {schedule_date.strftime('%d.%m.%Y')}")
        return

    # ОТКЛЮЧЕНИЕ (OFF)
    off_alert_ts = start_ts - (alert_config.alert_minutes_before_off * 60)
    if off_alert_ts > now_ts + constants.MIN_ALERT_DELAY:
        off_key = f"OFF_{schedule_date.strftime('%d.%m.%Y')}_{period_start}_{period_end}"
        if off_key not in alert_manager.planned_alerts:
            off_time = time.strftime('%H:%M', time.localtime(off_alert_ts))
            msg = builder.initial_off_message(
                period_start, period_end, off_time)

            if alert_manager.send_alert(msg, alert_key=off_key):
                alert_manager.planned_alerts.add(off_key)

                final_msg = builder.final_off_message(
                    period_start, period_end)
                delay = off_alert_ts - now_ts
                asyncio.create_task(
                    alert_manager.schedule_delayed_alert(
                        'OFF', delay, final_msg, off_key)
                )

    # ВКЛЮЧЕНИЕ (ON)
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
