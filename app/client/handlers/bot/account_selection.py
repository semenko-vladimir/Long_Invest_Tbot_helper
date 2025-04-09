from telebot import types
from app.client.api.config_client import ConfigApiClient
from app.client.bot.bot import bot
from tinkoff.invest import Client
from tinkoff.invest.services import SandboxService
from dotenv import load_dotenv
import os
from app.client.handlers.utils.message_utils import send_or_edit_message

config_client = ConfigApiClient()

# Функция для получения токенов из переменных окружения
def get_tokens():
    """
    Получает токены из переменных окружения.
    
    Returns:
        dict: Словарь с токенами
    """
    load_dotenv()
    return {
        "token": os.getenv('TOKEN'),
        "sandbox_token": os.getenv('SANDBOX_TOKEN')
    }


@bot.callback_query_handler(func=lambda call: call.data == 'account_selection')
def get_account_handler(call):
    """
    Обработчик для выбора типа счета.
    
    Отображает меню с выбором между боевым счетом и песочницей.
    """
    chat_id = call.message.chat.id
    
    inline_keyboard = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text='💹 Боевой счет', callback_data='real_account'),
        types.InlineKeyboardButton(text='🏝️ Песочница', callback_data='sandbox_account'),
    ]
    
    for button in buttons:
        inline_keyboard.add(button)
    
    send_or_edit_message(
        chat_id, 
        '💼 *Выбор счета*\n\nВыберите тип счета для торговли:', 
        reply_markup=inline_keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data == 'real_account')
def real_account(call):
    """
    Обработчик для выбора боевого счета.
    
    Устанавливает флаг sandbox_trigger в False.
    """
    chat_id = call.message.chat.id
    
    try:
        # Отправляем сообщение о начале обработки
        send_or_edit_message(chat_id, "⏳ *Обработка запроса*\n\nНастраиваем боевой счет...")
        
        try:
            # Используем API-клиент для установки флага sandbox_trigger
            config_client.set_sandbox_trigger(False)
            send_or_edit_message(chat_id, "✅ *Успешно*\n\nВы выбрали боевой счет")
        except Exception as e:
            if hasattr(e, 'response') and e.response.status_code == 404:
                send_or_edit_message(chat_id, "❌ *Ошибка*\n\nНастройки стратегии не найдены. Сначала настройте стратегию.")
            else:
                raise
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при выборе боевого счета*\n\n`{str(e)}`")


@bot.callback_query_handler(func=lambda call: call.data == 'sandbox_account')
def sandbox_account(call):
    """
    Обработчик для выбора песочницы.
    
    Устанавливает флаг sandbox_trigger в True и проверяет/создает счет в песочнице.
    """
    chat_id = call.message.chat.id
    tokens = get_tokens()
    
    try:
        # Отправляем сообщение о начале обработки
        send_or_edit_message(chat_id, "⏳ *Обработка запроса*\n\nНастраиваем режим песочницы...")
        
        try:
            # Используем API-клиент для установки флага sandbox_trigger
            config_client.set_sandbox_trigger(True)
        except Exception as e:
            if hasattr(e, 'response') and e.response.status_code == 404:
                send_or_edit_message(chat_id, "❌ *Ошибка*\n\nНастройки стратегии не найдены. Сначала настройте стратегию.")
                return
            else:
                raise

        # Работа с песочницей Tinkoff API
        with Client(tokens["sandbox_token"]) as client:
            sb: SandboxService = client.sandbox

            r = sb.get_sandbox_accounts().accounts

            if len(r) > 0:
                send_or_edit_message(chat_id, "✅ *Успешно*\n\nВы выбрали режим песочницы")
            else:
                sb.open_sandbox_account()
                send_or_edit_message(chat_id, "✅ *Успешно*\n\nСоздан новый счет в песочнице. Выбран режим песочницы.")
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при выборе песочницы*\n\n`{str(e)}`")
