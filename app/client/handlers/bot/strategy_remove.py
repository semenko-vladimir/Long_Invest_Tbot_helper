from app.client.bot.bot import bot
from app.backend.api_client import ApiClient
from app.client.store.store import strategy_scheduler, selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, ema_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity, joint

# Создаем экземпляр API-клиента
api_client = ApiClient()


@bot.callback_query_handler(func=lambda call: call.data == 'strategy_remove')
def remove_strategy_handler(call):
    """
    Обработчик для отключения стратегии.
    
    Отключает стратегию и сбрасывает все параметры.
    """
    global selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, ema_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity, joint
    chat_id = call.message.chat.id
    
    try:
        # Останавливаем планировщик, если он существует
        global strategy_scheduler
        if strategy_scheduler:
            strategy_scheduler.shutdown()
            strategy_scheduler = None
        
        # Обновляем настройки стратегии через API-клиент
        api_client.update_strategy_signals(
            False,  # tpsl_trigger
            False,  # rsi_trigger
            False,  # sma_trigger
            False,  # alligator_trigger
            False,  # gpt_trigger
            False,  # lstm_trigger
            False,  # bollinger_trigger
            False,  # macd_trigger
            False,  # ema_trigger
            False   # joint
        )
        
        api_client.update_strategy_settings(
            "0",    # time
            False,  # auto_market
            0       # quantity
        )
        
        # Сбрасываем все параметры стратегии
        selected_signals = {}
        tpsl_trigger = False
        rsi_trigger = False
        sma_trigger = False
        ema_trigger = False
        alligator_trigger = False
        gpt_trigger = False
        lstm_trigger = False
        bollinger_trigger = False
        macd_trigger = False
        time = None
        auto_market = None
        quantity = None
        joint = None
        
        bot.send_message(chat_id, "Стратегия отключена.")
    
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при отключении стратегии: {str(e)}")
