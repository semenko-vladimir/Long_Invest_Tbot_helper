from db.db import get_t_token, update_signal_gpt
from bot.bot import bot

@bot.callback_query_handler(func=lambda call: call.data == 'signal_gpt')
def gpt_handler(call):
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    
    if token is not None:
        msg = bot.send_message(chat_id, "Введите промпт для GPT:")
        bot.register_next_step_handler(msg, get_gpt_text)

def get_gpt_text(message):
    chat_id = message.chat.id
    gpt_text = message.text
    
    gpt_text += "\n A PREREQUISITE. Based on your reasoning, an answer should be given consisting of one word: buy, sell or hold.".upper()
    gpt_text += "\n A PREREQUISITE. Based on your reasoning, an answer should be given consisting of one word: buy, sell or hold.".upper()


    update_signal_gpt(chat_id, gpt_text)

    bot.send_message(chat_id, 'GPT настроен с параметром:\n' + gpt_text)