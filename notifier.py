"""
notifier.py — Notifications Telegram pour le pipeline OA.

Config dans .env :
  TELEGRAM_BOT_TOKEN=<token du bot>
  TELEGRAM_CHAT_ID=<ton chat_id personnel>
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def send_telegram(message: str) -> bool:
    """Envoie un message Telegram. Retourne True si succès."""
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("[Notifier] Telegram non configuré (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID manquants dans .env)")
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.status_code == 200:
            return True
        print(f"[Notifier] Telegram HTTP {r.status_code} : {r.text}")
        return False
    except Exception as e:
        print(f"[Notifier] Erreur Telegram : {e}")
        return False
