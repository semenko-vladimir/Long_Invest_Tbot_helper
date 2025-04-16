from app.client.bot.bot import bot

# Словарь для хранения ID последних сообщений для каждого чата
last_messages = {}

def send_or_edit_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    """
    Отправляет новое сообщение или редактирует существующее в зависимости от наличия ID последнего сообщения.
    
    Args:
        chat_id: ID чата
        text: Текст сообщения
        reply_markup: Клавиатура для сообщения (опционально)
        parse_mode: Режим форматирования текста (опционально)
    
    Returns:
        None
    """
    try:
        # Проверяем, есть ли ID последнего сообщения для данного чата
        if chat_id in last_messages:
            try:
                # Пробуем обновить существующее сообщение
                msg = bot.edit_message_text(
                    text=text,
                    chat_id=chat_id,
                    message_id=last_messages[chat_id],
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                return msg
            except Exception as e:
                # Если произошла ошибка (например, сообщение уже удалено), отправляем новое
                print(f"Error editing message: {e}")
        
        # Отправляем новое сообщение
        msg = bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        # Сохраняем ID нового сообщения
        last_messages[chat_id] = msg.message_id

        return msg
    except Exception as e:
        print(f"Error sending message: {e}")
