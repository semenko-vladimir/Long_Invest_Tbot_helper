#!/usr/bin/env python3
"""Check server bot configuration without printing secrets."""

import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
values = {}
for line in (root / '.env').read_text(encoding='utf-8').splitlines():
    match = re.match(r'^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$', line)
    if match:
        values[match.group(1)] = match.group(2).strip('"\'')

missing = []
token = values.get('BOT_TOKEN', '')
if not re.fullmatch(r'\d+:[A-Za-z0-9_-]{20,}', token):
    missing.append('.env: BOT_TOKEN')
mode = values.get('APP_MODE', 'sandbox').lower()
if mode not in {'sandbox', 'prod'}:
    missing.append('.env: APP_MODE должен быть sandbox или prod')
if values.get('ALLOW_PROD_TRADING', 'false').lower() != 'false':
    missing.append('.env: ALLOW_PROD_TRADING должен быть false')
if values.get('ALLOW_AUTO_INVESTING', 'false').lower() != 'false':
    missing.append('.env: ALLOW_AUTO_INVESTING должен быть false')
if values.get('ENABLE_STRATEGY_AUTO_EXECUTION', 'false').lower() != 'false':
    missing.append('.env: ENABLE_STRATEGY_AUTO_EXECUTION должен быть false')
if values.get('ALLOW_STRATEGY_AUTO_EXECUTION', 'false').lower() != 'false':
    missing.append('.env: ALLOW_STRATEGY_AUTO_EXECUTION должен быть false')
if values.get('SSL_TBANK_VERIFY', 'true').lower() != 'true':
    missing.append('.env: SSL_TBANK_VERIFY должен быть True')

try:
    users = json.loads((root / 'users.json').read_text(encoding='utf-8')).get('users', [])
    enabled = [user for user in users if user.get('enabled', True)]
    if not enabled:
        missing.append('users.json: хотя бы один включённый пользователь')
    for index, user in enumerate(enabled, 1):
        chat = str(user.get('telegram_chat_id', '')).strip()
        if not re.fullmatch(r'-?\d{5,}', chat):
            missing.append(f'users.json: telegram_chat_id пользователя {index}')
        field = 'token' if mode == 'prod' else 'sandbox_token'
        broker_token = str(user.get(field, '')).strip()
        if not broker_token or broker_token.startswith('your_'):
            missing.append(f'users.json: {field} пользователя {index}')
except (OSError, ValueError, TypeError, AttributeError):
    missing.append('users.json: корректный JSON')

if missing:
    print('Нужно заполнить:')
    for item in missing:
        print('-', item)
    sys.exit(1)
print('Конфигурация заполнена; значения секретов не выводились.')
