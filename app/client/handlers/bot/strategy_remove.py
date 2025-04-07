from app.client.api.strategy_client import StrategyApiClient
from app.client.bot.bot import bot
from app.client.store.store import strategy_scheduler, selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, ema_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity, joint
from app.client.handlers.utils.message_utils import send_or_edit_message

strategy_client = StrategyApiClient()

@bot.callback_query_handler(func=lambda call: call.data == 'strategy_remove')
def remove_strategy_handler(call):
    """
    Обработчик для отключения стратегии.
    
    Отключает стратегию и сбрасывает все параметры.
    """
    global selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, ema_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity, joint
    chat_id = call.message.chat.id
    
    try:
        # Отправляем сообщение о начале обработки
        send_or_edit_message(chat_id, "⏳ *Обработка запроса*\n\nОтключаем текущую стратегию...")
        
        # Останавливаем планировщик, если он существует
        global strategy_scheduler
        if strategy_scheduler:
            strategy_scheduler.shutdown()
            strategy_scheduler = None
        
        # Обновляем настройки стратегии через API-клиент
        strategy_client.update_strategy_signals(
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
        
        strategy_client.update_strategy_settings(
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
        
        send_or_edit_message(chat_id, "🛑 *Стратегия отключена*\n\nВсе параметры стратегии сброшены.")
    
    except Exception as e:
        send_or_edit_message(chat_id, f"❌ *Ошибка при отключении стратегии*\n\n`{str(e)}`")
