from app.client.bot.bot import bot
from telebot import types

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_knowledge_base')
def back_to_knowledge_base(call):
    """
    Обработчик для возврата в основное меню базы знаний.
    """
    from app.client.handlers.knowledge_base.knowledge_base_handler import knowledge_base_handler
    
    # Эмулируем сообщение для вызова knowledge_base_handler
    class EmulatedMessage:
        def __init__(self, chat_id, text):
            self.chat = types.User(id=chat_id, first_name='', is_bot=False)
            self.text = text
    
    emulated_message = EmulatedMessage(call.message.chat.id, 'База знаний')
    knowledge_base_handler(emulated_message)
