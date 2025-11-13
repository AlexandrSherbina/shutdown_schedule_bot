@echo off
chcp 65001 > nul

REM === УСТАНОВКА UTF-8 КОДИРОВКИ ===
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

REM --- ПЕРЕМЕННЫЕ СКРИПТА ---
setlocal enabledelayedexpansion

REM Получаем путь до директории скрипта
set SCRIPT_DIR=%~dp0
set LOG_DIR=%SCRIPT_DIR%logs
set PID_FILE=%SCRIPT_DIR%power_alert.pid
set LOG_FILE=%LOG_DIR%\power_alert.log
set ENV_FILE=%SCRIPT_DIR%env.env

REM Абсолютные пути
set PYTHON_SCRIPT=%SCRIPT_DIR%main.py
set PYTHON_EXE=python

REM --- ПРОВЕРКИ ---

REM 1. Проверяем, установлен ли Python
%PYTHON_EXE% --version > nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден в PATH
    echo Пожалуйста, установите Python или добавьте его в PATH
    echo Сайт: https://www.python.org/
    pause
    exit /b 1
)

REM 2. Проверяем, существует ли скрипт
if not exist "%PYTHON_SCRIPT%" (
    echo [ОШИБКА] Скрипт не найден: %PYTHON_SCRIPT%
    pause
    exit /b 1
)

REM 3. Проверяем, существует ли env.env файл
if not exist "%ENV_FILE%" (
    echo [ПРЕДУПРЕЖДЕНИЕ] env.env файл не найден: %ENV_FILE%
    echo Создаю шаблон env.env файла...
    call :create_env_template
)

REM 4. Создаем директорию логов
if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
    echo [INFO] Директория логов создана: %LOG_DIR%
)

REM --- ЗАГРУЗКА КОНФИГУРАЦИИ ---

if exist "%ENV_FILE%" (
    echo [INFO] Загрузка конфигурации из env.env...
    for /f "usebackq tokens=* delims=" %%A in ("%ENV_FILE%") do (
        set "line=%%A"
        if not "!line!"=="" (
            if not "!line:~0,1!"=="#" (
                set "!line!"
            )
        )
    )
) else (
    echo [ОШИБКА] env.env файл не существует
    pause
    exit /b 1
)

REM Проверяем критические переменные
if "!TG_API_ID!"=="" (
    echo [ОШИБКА] TG_API_ID не установлен
    pause
    exit /b 1
)

REM --- ПРОВЕРКА ЗАВИСИМОСТЕЙ ---

echo [INFO] Проверка зависимостей Python...
%PYTHON_EXE% -c "import telethon; import requests" > nul 2>&1
if errorlevel 1 (
    echo [INFO] Установка зависимостей...
    %PYTHON_EXE% -m pip install telethon requests
)

REM --- ЗАПУСК СКРИПТА В ОКНЕ (видимый режим) ---

echo.
echo ============================================
echo   ПАРСЕР TELEGRAM СВЕТА
echo ============================================
echo.
echo [INFO] Запуск скрипта...
echo [INFO] Логи также сохраняются в: %LOG_FILE%
echo [INFO] Время запуска: %date% %time%
echo.

REM Запускаем Python скрипт БЕЗ /min — окно будет видимо
REM и вывод будет показан в реальном времени
%PYTHON_EXE% "%PYTHON_SCRIPT%"

pause
exit /b 0

:create_env_template
(
    echo # ===== Telegram API =====
    echo TG_API_ID=ВАШ_API_ID
    echo TG_API_HASH=ВАШ_API_HASH
    echo.
    echo # ===== Telegram Bot =====
    echo TG_BOT_TOKEN=ВАШ_BOT_TOKEN
    echo TG_CHAT_ID=ВАШ_CHAT_ID
    echo.
    echo # ===== Параметры =====
    echo TG_CHANNEL_USERNAME=SvitloSvitlovodskohoRaionu
    echo TARGET_QUEUE=1.2
    echo ALERT_OFF_MINUTES=15
    echo ALERT_ON_MINUTES=10
    echo CHECK_INTERVAL_SECONDS=300
) > "%ENV_FILE%"

echo [OK] Создан: %ENV_FILE%
exit /b 0