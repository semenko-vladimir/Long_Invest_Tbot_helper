"""Verify Telegram bot token and proxy without logging the token."""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv('/opt/tbot/.env')
token = os.getenv('BOT_TOKEN', '').strip()
proxy = os.getenv('TELEGRAM_PROXY_URL', '').strip()
if not token or not proxy:
    print('BOT_TOKEN or TELEGRAM_PROXY_URL is missing')
    sys.exit(1)

session = requests.Session()
session.proxies = {'http': proxy, 'https': proxy}
session.trust_env = False
try:
    response = session.get(f'https://api.telegram.org/bot{token}/getMe', timeout=15)
    result = response.json()
    if response.status_code != 200 or not result.get('ok'):
        print('Telegram getMe failed: HTTP', response.status_code)
        sys.exit(1)
    print('Telegram getMe succeeded; bot username:', result['result'].get('username'))
    response = session.get(f'https://api.telegram.org/bot{token}/getWebhookInfo', timeout=15)
    result = response.json()
    if response.status_code != 200 or not result.get('ok'):
        print('Telegram getWebhookInfo failed: HTTP', response.status_code)
        sys.exit(1)
    webhook_active = bool(result['result'].get('url'))
    print('Webhook active:', webhook_active)
    if webhook_active:
        sys.exit(1)
except (requests.RequestException, ValueError, KeyError) as error:
    print('Telegram verification failed:', type(error).__name__)
    sys.exit(1)
