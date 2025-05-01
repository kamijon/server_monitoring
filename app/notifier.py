import requests

TELEGRAM_TOKEN = "7667485819:AAH_LB_fOhac1v47Az1pgH3tfAZw0QSPDrk"
TELEGRAM_CHAT_ID = "920449061"

def send_telegram_message(message: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Telegram alert error: {e}")
        return False
from datetime import datetime

def write_log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    with open("server.log", "a") as f:
        f.write(log_line)