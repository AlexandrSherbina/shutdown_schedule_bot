import requests
import os
from dotenv import load_dotenv

load_dotenv('env.env')
bot_token = os.getenv('TG_BOT_TOKEN')

print(f"BOT_TOKEN: {bot_token[:10]}...")

try:
    r = requests.get(
        f"https://api.telegram.org/bot{bot_token}/getMe", timeout=5)
    print(f"Статус: {r.status_code}")
    print(f"Ответ: {r.json()}")
except Exception as e:
    print(f"Ошибка: {e}")
