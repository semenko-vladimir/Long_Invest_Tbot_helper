import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(ROOT_DIR))

from app.client.utils.methods import get_price_change_in_current_interval
from app.client.api.config_client import ConfigApiClient

config_client = ConfigApiClient()

def send_price_change_notification(figi, start_time, end_time, candle_interval, bot, chat_id, name, type_of, ticker, collapse=False):
    config = config_client.get_config()
    
    active_settings = [
        config.get('collapse_updates', False),
        config.get('market_updates', False)
    ]
    if not any(active_settings):
        return

    price_change, price_change_percent, max_price, min_price, close_price = get_price_change_in_current_interval(figi, start_time, end_time, candle_interval)
    
    change_emoji = "📈" if price_change_percent > 0 else "📉"

    message = (
        f'{change_emoji} *Информация о {ticker}*\n\n'
        f'📌 Название: `{name}`\n'
        f'📋 Тип: `{type_of}`\n'
        f'🏷️ Тикер: `{ticker}`\n'
        f'📊 Изменение цены: `{round(price_change_percent, 2)}%`\n'
        f'💰 Цена закрытия последней свечи: `{close_price}`\n'
        f'⬆️ Максимальная цена: `{max_price}`\n'
        f'⬇️ Минимальная цена: `{min_price}`\n'
    )
    
    if collapse and price_change_percent < -0.001:
        bot.send_message(chat_id, message, parse_mode='Markdown')
    elif not collapse:
        bot.send_message(chat_id, message, parse_mode='Markdown')
