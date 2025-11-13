REM filepath: c:\Users\Alexandr\Documents\LearnPython\TelegrAlert\pc_power_alert\stop_alert.bat

@echo off
chcp 65001 > nul

echo.
echo ============================================
echo   ОСТАНОВКА ПАРСЕРА TELEGRAM СВЕТА
echo ============================================
echo.

REM Ищем процесс python, содержащий main.py
tasklist /fi "IMAGENAME eq python.exe" | find /I "python.exe" > nul

if errorlevel 1 (
    echo [ОШИБКА] Процесс python не найден
    pause
    exit /b 1
)

echo [INFO] Найдены процессы Python. Остановка...

REM Останавливаем все процессы python (используйте аккуратнее!)
REM Для более точной остановки используйте PID
taskkill /IM python.exe /F

echo [OK] Процесс остановлен
echo.
pause