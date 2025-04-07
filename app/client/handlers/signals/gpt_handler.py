from telebot import types
from app.client.api.signals_client import SignalsApiClient
from app.client.bot.bot import bot
from app.client.handlers.utils.message_utils import send_or_edit_message

signals_client = SignalsApiClient()


@bot.callback_query_handler(func=lambda call: call.data == 'signal_gpt')
def gpt_handler(call):
    """
    Обработчик для настройки сигнала GPT.
    
    Запрашивает у пользователя промпт для GPT.
    """
    chat_id = call.message.chat.id
    
    # Получаем текущие настройки GPT
    current_settings = signals_client.get_signal_gpt()
    
    if current_settings:
        text = current_settings.get('text', '')
        
        # Удаляем предварительные условия для отображения
        display_text = text.replace("\n A PREREQUISITE. Based on your reasoning, an answer should be given consisting of one word: buy, sell or hold.".upper(), "")
        
        send_or_edit_message(
            chat_id, 
            f'🤖 *Текущий промпт GPT*\n\n```\n{display_text}\n```'
        )
    
    # Запрашиваем промпт
    msg = send_or_edit_message(chat_id, "🤖 *Настройка GPT*\n\nВведите промпт для GPT:")
    bot.register_next_step_handler(msg, get_gpt_text)


def get_gpt_text(message):
    """
    Обработчик для получения промпта GPT.
    
    Сохраняет промпт и обновляет настройки сигнала GPT.
    """
    chat_id = message.chat.id
    gpt_text = message.text
    
    # Добавляем предварительные условия
    gpt_text += "\n A PREREQUISITE. Based on your reasoning, an answer should be given consisting of one word: buy, sell or hold.".upper()
    gpt_text += "\n A PREREQUISITE. Based on your reasoning, an answer should be given consisting of one word: buy, sell or hold.".upper()
    
    try:
        # Обновляем параметры через API-клиент
        result = signals_client.update_signal_gpt(gpt_text)
        
        # Отображаем промпт без предварительных условий для лучшей читаемости
        display_text = gpt_text.replace("\n A PREREQUISITE. Based on your reasoning, an answer should be given consisting of one word: buy, sell or hold.".upper(), "")
        
        send_or_edit_message(
            chat_id, 
            f'✅ *GPT успешно настроен*\n\n```\n{display_text}\n```\n\n_(Добавлено условие для получения ответа buy/sell/hold)_'
        )
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при обновлении настроек GPT*\n\n`{str(e)}`")
