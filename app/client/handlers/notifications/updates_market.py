from app.client.api.config_client import ConfigApiClient
from app.client.api.instruments_client import InstrumentsApiClient
from app.client.bot.bot import bot
from telebot import types
from app.client.config.schedulers_config import configure_market_scheduler
from app.client.handlers.notifications.utils.utils import stop_scheduler, get_interval_from_callback

config_client = ConfigApiClient()
instruments_client = InstrumentsApiClient()

@bot.callback_query_handler(func=lambda call: call.data == 'user_add_market_updates')
def add_market_updates_handler(call):
    """
    Обработчик для подписки на обновления рынка.
    
    Проверяет, подписан ли пользователь уже, и если нет, предлагает выбрать интервал.
    """
    chat_id = call.message.chat.id
    
    try:
        # Получаем текущие настройки конфигурации
        config = config_client.get_config()
        
        if config and config.get('market_updates', False):
            bot.send_message(chat_id, 'Вы уже подписаны на обновления рынка')
            return
        
        bot.send_message(chat_id, 'Вы автоматически будете отписаны от обновлений падений рынка')
        
        # Получаем список всех инструментов
        instruments = instruments_client.get_all_instruments()
        
        if not instruments:
            bot.send_message(chat_id, 'У вас нет активных инструментов')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [types.InlineKeyboardButton(text=t, callback_data=f'uinterval_{t}') for t in ['10 минут', 'пол часа', 'час']]
            
            for button in buttons:
                inline_keyboard.add(button)
            
            bot.send_message(chat_id, 'Выберите интервал для получения обновлений', reply_markup=inline_keyboard)
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при подписке на обновления: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('uinterval_'))
def market_interval_handler(call):
    """
    Обработчик для выбора интервала обновлений рынка.
    
    Устанавливает выбранный интервал и включает обновления.
    """
    chat_id = call.message.chat.id
    
    try:
        # Останавливаем текущий планировщик
        stop_scheduler()
        
        # Получаем интервал из callback-данных
        time_value = get_interval_from_callback(call.data)
        
        # Преобразуем время в строку
        time_str = str(time_value)
        
        # Обновляем настройки конфигурации через API-клиент
        config_client.update_config_collapse(
            "0",            # collapse_updates_time
            False,          # collapse_updates
            time_str,       # market_updates_time
            True            # market_updates
        )
        
        print("РАБОТАЮТ ОБНОВЛЕНИЯ РЫНКА")
        configure_market_scheduler()
        
        bot.send_message(chat_id, f'Вы подписались на обновления рынка с интервалом {time_str}')
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при настройке интервала: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data == 'remove_market_updates')
def remove_market_updates_handler(call):
    """
    Обработчик для отписки от обновлений рынка.
    
    Отключает обновления и останавливает планировщик.
    """
    chat_id = call.message.chat.id
    
    try:
        # Обновляем настройки конфигурации через API-клиент
        config_client.update_config_collapse(
            "0",            # collapse_updates_time
            False,          # collapse_updates
            "0",            # market_updates_time
            False           # market_updates
        )
        
        # Останавливаем планировщик
        stop_scheduler()
        
        bot.send_message(chat_id, 'Вы отписались от обновлений рынка')
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при отписке от обновлений: {str(e)}")
