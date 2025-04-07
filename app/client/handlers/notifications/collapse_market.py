from app.client.api.config_client import ConfigApiClient
from app.client.api.instruments_client import InstrumentsApiClient
from app.client.bot.bot import bot
from telebot import types
from app.client.config.schedulers_config import configure_market_scheduler
from app.client.handlers.notifications.utils.utils import stop_scheduler, get_interval_from_callback
from app.client.handlers.utils.message_utils import send_or_edit_message

config_client = ConfigApiClient()
instruments_client = InstrumentsApiClient()


@bot.callback_query_handler(func=lambda call: call.data == 'user_update_collapse_market')
def add_collapse_market_handler(call):
    """
    Обработчик для подписки на обновления о падениях рынка.
    
    Проверяет, подписан ли пользователь уже, и если нет, предлагает выбрать интервал.
    """
    chat_id = call.message.chat.id
    
    try:
        # Получаем текущие настройки конфигурации
        config = config_client.get_config()
        
        if config and config.get('collapse_updates', False):
            send_or_edit_message(chat_id, '📊 *Подписка на уведомления*\n\nВы уже подписаны на обновления падений рынка')
            return
        
        send_or_edit_message(chat_id, '🔄 *Изменение подписки*\n\nВы автоматически будете отписаны от обновлений рынка')
        
        # Получаем список всех инструментов
        instruments = instruments_client.get_all_instruments()
        
        if not instruments:
            send_or_edit_message(chat_id, '❌ *Ошибка подписки*\n\nУ вас нет активных инструментов')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [types.InlineKeyboardButton(text=t, callback_data=f'ucinterval_{t}') for t in ['10 минут', 'пол часа', 'час']]
            
            for button in buttons:
                inline_keyboard.add(button)
            
            send_or_edit_message(
                chat_id, 
                '⏱️ *Выбор интервала*\n\nВыберите интервал для получения обновлений о падениях рынка:', 
                reply_markup=inline_keyboard
            )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при подписке на обновления*\n\n`{str(e)}`")


@bot.callback_query_handler(func=lambda call: call.data.startswith('ucinterval_'))
def collapse_interval_handler(call):
    """
    Обработчик для выбора интервала обновлений о падениях рынка.
    
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
            time_str,       # collapse_updates_time
            True,           # collapse_updates
            "0",            # market_updates_time
            False           # market_updates
        )
        
        print("РАБОТАЮТ ПАДЕНИЯ РЫНКА")
        configure_market_scheduler()
        
        send_or_edit_message(
            chat_id, 
            f'✅ *Успешно*\n\nВы подписались на обновления о падениях рынка с интервалом {time_str}'
        )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при настройке интервала*\n\n`{str(e)}`")


@bot.callback_query_handler(func=lambda call: call.data == 'remove_collapse_market')
def remove_collapse_market_handler(call):
    """
    Обработчик для отписки от обновлений о падениях рынка.
    
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
        
        send_or_edit_message(chat_id, '🔕 *Отписка от уведомлений*\n\nВы отписались от обновлений о падениях рынка')
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при отписке от обновлений*\n\n`{str(e)}`")
