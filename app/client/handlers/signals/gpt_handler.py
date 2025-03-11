from telebot import types
from app.client.bot.bot import bot
from app.backend.api_client import ApiClient

# Создаем экземпляр API-клиента
api_client = ApiClient()


@bot.callback_query_handler(func=lambda call: call.data == 'signal_gpt')
def gpt_handler(call):
    """
    Обработчик для настройки сигнала GPT.
    
    Запрашивает у пользователя промпт для GPT.
    """
    chat_id = call.message.chat.id
    
    # Получаем текущие настройки GPT
    current_settings = api_client.get_signal_gpt()
    
    if current_settings:
        text = current_settings.get('text', '')
        
        # Удаляем предварительные условия для отображения
        display_text = text.replace("\n A PREREQUISITE. Based on your reasoning, an answer should be given consisting of one word: buy, sell or hold.".upper(), "")
        
        bot.send_message(
            chat_id, 
            f'Текущий промпт GPT:\n{display_text}'
        )
    
    # Запрашиваем промпт
    msg = bot.send_message(chat_id, "Введите промпт для GPT:")
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
        result = api_client.update_signal_gpt(gpt_text)
        
        # Отображаем промпт без предварительных условий для лучшей читаемости
        display_text = gpt_text.replace("\n A PREREQUISITE. Based on your reasoning, an answer should be given consisting of one word: buy, sell or hold.".upper(), "")
        
        bot.send_message(
            chat_id, 
            f'GPT настроен с параметром:\n{display_text}\n\n(Добавлено условие для получения ответа buy/sell/hold)'
        )
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при обновлении настроек GPT: {str(e)}")
