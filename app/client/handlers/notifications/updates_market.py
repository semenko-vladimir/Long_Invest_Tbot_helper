from app.client.api.config_client import ConfigApiClient
from app.client.api.instruments_client import InstrumentsApiClient
from app.client.bot.bot import bot
from telebot import types
from app.client.config.schedulers_config import configure_market_scheduler
from app.client.handlers.notifications.utils.utils import stop_scheduler, get_interval_from_callback
from app.client.handlers.utils.message_utils import send_or_edit_message
import requests

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
        try:
            config = config_client.get_config()
            
            # Если конфигурация существует и обновления уже включены
            if config and config.get('market_updates', False):
                send_or_edit_message(chat_id, '📊 *Подписка на уведомления*\n\nВы уже подписаны на обновления рынка')
                return
            
            send_or_edit_message(chat_id, '🔄 *Изменение подписки*\n\nВы автоматически будете отписаны от обновлений падений рынка')
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Если конфигурация не найдена, создаем новую
                pass
            else:
                # Если другая ошибка, сообщаем о ней пользователю
                send_or_edit_message(chat_id, f"❌ *Ошибка при получении конфигурации*\n\n`{str(e)}`")
                return
        except Exception as e:
            send_or_edit_message(chat_id, f"❌ *Ошибка при получении конфигурации*\n\n`{str(e)}`")
            return
        
        # Получаем список всех инструментов
        instruments = instruments_client.get_all_instruments()
        
        if not instruments:
            send_or_edit_message(chat_id, '❌ *Ошибка подписки*\n\nУ вас нет активных инструментов')
        else:
            inline_keyboard = types.InlineKeyboardMarkup()
            buttons = [types.InlineKeyboardButton(text=t, callback_data=f'uinterval_{t}') for t in ['10 минут', 'пол часа', 'час']]
            
            for button in buttons:
                inline_keyboard.add(button)
            
            send_or_edit_message(
                chat_id, 
                '⏱️ *Выбор интервала*\n\nВыберите интервал для получения обновлений рынка:', 
                reply_markup=inline_keyboard
            )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при подписке на обновления*\n\n`{str(e)}`")


@bot.callback_query_handler(func=lambda call: call.data.startswith('uinterval_'))
def update_interval_handler(call):
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
        
        # Проверяем, существует ли конфигурация
        try:
            config = config_client.get_config()
            # Обновляем существующую конфигурацию
            config_client.update_config(
                "0",            # collapse_updates_time
                False,          # collapse_updates
                time_str,       # market_updates_time
                True            # market_updates
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Если конфигурации нет, создаем новую
                config_client.create_config(
                    "0",            # collapse_updates_time
                    False,          # collapse_updates
                    time_str,       # market_updates_time
                    True            # market_updates
                )
            else:
                # Если другая ошибка, вызываем исключение
                raise
        
        print("РАБОТАЮТ ОБНОВЛЕНИЯ РЫНКА")
        configure_market_scheduler()
        
        send_or_edit_message(
            chat_id, 
            f'✅ *Успешно*\n\nВы подписались на обновления рынка с интервалом {time_str}'
        )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при настройке интервала*\n\n`{str(e)}`")


@bot.callback_query_handler(func=lambda call: call.data == 'remove_market_updates')
def remove_market_updates_handler(call):
    """
    Обработчик для отписки от обновлений рынка.
    
    Отключает обновления и останавливает планировщик.
    """
    chat_id = call.message.chat.id
    
    try:
        # Обновляем настройки конфигурации через API-клиент
        config_client.update_config(
            "0",            # collapse_updates_time
            False,          # collapse_updates
            "0",            # market_updates_time
            False           # market_updates
        )
        
        # Останавливаем планировщик
        stop_scheduler()
        
        send_or_edit_message(chat_id, '🔕 *Отписка от уведомлений*\n\nВы отписались от обновлений рынка')
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при отписке от обновлений*\n\n`{str(e)}`")
