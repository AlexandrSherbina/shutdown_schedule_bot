@REM start /min python C:\Users\Alexandr\Documents\LearnPython\TelegrAlert\pc_power_alert\power_alert.py

@REM set TG_API_ID=38642593 && set TG_API_HASH=3455e166b9dfcee8f883e8ab4ae52ee6 && set TG_BOT_TOKEN=8333707550:AAEExWqLWk5LZrqOP7jhV7Ywo05ubc27dfs && set TG_CHAT_ID=484908554 && python power_alert.py

@echo off
chcp 65001
REM --- Настройки переменных окружения ---
REM Ваши личные данные, полученные на my.telegram.org:
set TG_API_ID=38642593 
set TG_API_HASH=3455e166b9dfcee8f883e8ab4ae52ee6 

REM Настройки вашего бота, полученные через BotFather и @userinfobot:
set TG_BOT_TOKEN=8333707550:AAEExWqLWk5LZrqOP7jhV7Ywo05ubc27dfs
set TG_CHAT_ID=484908554 

REM Настройки логики (можно оставить по умолчанию, если подходят):
set TARGET_QUEUE=1.2
set ALERT_OFF_MINUTES=15
set ALERT_ON_MINUTES=10
set CHECK_INTERVAL_SECONDS=300

REM --- Запуск скрипта в фоновом режиме ---
REM /min - запускает окно свернутым.
REM python - может потребоваться python.exe, если PATH настроен иначе.
echo Запуск парсера Telegram Света...

start "Наблюдатель Света" /min "C:\Python311\python.exe" "C:\Users\Alexandr\Documents\LearnPython\TelegrAlert\pc_power_alert\power_alert.py"
@REM  "C:\Python311\python.exe" "C:\Users\Alexandr\Documents\LearnPython\TelegrAlert\pc_power_alert\power_alert.py"

@REM echo.
echo Проверьте свернутое окно на панели задач.
pause