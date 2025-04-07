from app.client.bot.bot import bot

# Словарь для хранения ID последних сообщений для каждого чата
last_messages = {}

def send_or_edit_message(chat_id, text, reply_markup=None):
    """
    Отправляет новое сообщение или редактирует последнее отправленное.
    
    Args:
        chat_id: ID чата
        text: Текст сообщения
        reply_markup: Разметка клавиатуры (опционально)
        
    Returns:
        Message: Объект сообщения
    """
    global last_messages
    
    # Если для данного чата уже есть сообщение, редактируем его
    if chat_id in last_messages:
        try:
            # Пытаемся отредактировать последнее сообщение
            return bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=last_messages[chat_id],
                parse_mode='Markdown',
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        except Exception:
            # Если не удалось отредактировать (например, сообщение слишком старое),
            # отправляем новое
            msg = bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='Markdown',
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            last_messages[chat_id] = msg.message_id
            return msg
    else:
        # Если сообщений еще не было, отправляем новое
        msg = bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode='Markdown',
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        last_messages[chat_id] = msg.message_id
        return msg
