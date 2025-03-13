from app.client.store.store import market_scheduler

def stop_scheduler():
    """Останавливает планировщик уведомлений о рынке"""
    global market_scheduler
    if market_scheduler:
        market_scheduler.shutdown()
        market_scheduler = None
        
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
