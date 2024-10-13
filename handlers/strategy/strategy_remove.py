
from db.db import get_t_token, update_strategy
from bot.bot import bot
from store.store import strategy_shedulers, selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity, joint


@bot.callback_query_handler(func=lambda call: call.data == 'strategy_remove')
def remove_strategy_handler(call):
    global selected_signals, tpsl_trigger, rsi_trigger, sma_trigger, alligator_trigger, gpt_trigger, lstm_trigger, bollinger_trigger, macd_trigger, time, auto_market, quantity, joint
    chat_id = call.message.chat.id
    token = get_t_token(chat_id)
    if token is not None:

        if chat_id in strategy_shedulers:
            scheduler = strategy_shedulers[chat_id]
            scheduler.shutdown()
            del strategy_shedulers[chat_id]

        update_strategy(chat_id, 0, 0, 0, 0, 0, 0, 0, 0, 0, False, 0, 0)
        
        selected_signals = {}
        tpsl_trigger = False
        rsi_trigger = False
        sma_trigger = False
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