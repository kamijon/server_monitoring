import requests
import json
from typing import List, Optional
from pathlib import Path

TELEGRAM_TOKEN = "7667485819:AAH_LB_fOhac1v47Az1pgH3tfAZw0QSPDrk"
CONFIG_FILE = "telegram_config.json"

def load_chat_ids() -> List[str]:
    """Load chat IDs from config file."""
    try:
        if Path(CONFIG_FILE).exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('chat_ids', ["920449061"])  # Default to original chat ID if none found
        return ["920449061"]  # Default chat ID
    except Exception as e:
        print(f"Error loading chat IDs: {e}")
        return ["920449061"]  # Default chat ID

def save_chat_ids(chat_ids: List[str]):
    """Save chat IDs to config file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({'chat_ids': chat_ids}, f)
    except Exception as e:
        print(f"Error saving chat IDs: {e}")

def add_chat_id(chat_id: str) -> bool:
    """Add a new chat ID to the configuration."""
    try:
        chat_ids = load_chat_ids()
        if chat_id not in chat_ids:
            chat_ids.append(chat_id)
            save_chat_ids(chat_ids)
            return True
        return False
    except Exception as e:
        print(f"Error adding chat ID: {e}")
        return False

def remove_chat_id(chat_id: str) -> bool:
    """Remove a chat ID from the configuration."""
    try:
        chat_ids = load_chat_ids()
        if chat_id in chat_ids and len(chat_ids) > 1:  # Prevent removing the last chat ID
            chat_ids.remove(chat_id)
            save_chat_ids(chat_ids)
            return True
        return False
    except Exception as e:
        print(f"Error removing chat ID: {e}")
        return False

def send_telegram_message(message: str, chat_id: Optional[str] = None):
    """Send message to all configured chat IDs or a specific chat ID."""
    try:
        chat_ids = [chat_id] if chat_id else load_chat_ids()
        success = True
        
        for cid in chat_ids:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {
                "chat_id": cid,
                "text": message,
                "parse_mode": "Markdown"
            }
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
        return success
    except Exception as e:
        print(f"Telegram alert error: {e}")
        return False

def write_log(message: str):
    """Write message to log file with timestamp."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    with open("server.log", "a") as f:
        f.write(log_line)