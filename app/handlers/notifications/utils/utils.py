from store.store import chat_schedulers

def stop_scheduler(chat_id):
    """Останавливает и удаляет планировщик для указанного чата"""
    if chat_id in chat_schedulers:
        scheduler = chat_schedulers[chat_id]
        scheduler.shutdown()
        del chat_schedulers[chat_id]
        
def get_interval_from_callback(callback_data):
    """Извлекает интервал времени из callback_data"""
    data = callback_data.split('_')
    interval = data[1]
    if interval == '10 минут':
        return 10
    elif interval == 'пол часа':
        return 30
    elif interval == 'час':
        return 60
    return 0
