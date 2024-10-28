from pandas import DataFrame
from tinkoff.invest import HistoricCandle
import pytz

def calculate_profit(average_position_price, current_price_one, brokerFee=0.3):

    comission = ((average_position_price + current_price_one) * brokerFee) / 100

    profit = current_price_one - average_position_price - comission

    current_profit = (100 * profit) / average_position_price

    return current_profit

def to_quotation(value: float) -> dict:
    sign = -1 if value < 0 else 1
    abs_value = abs(value)
    units = int(abs_value)
    nano = round((abs_value - units) * 1e9)

    return sign * units, sign * nano


def to_money_value(value):

    units, nano = to_quotation(value)

    return units, nano

def cast_money(v):
    return v.units + v.nano / 1e9


def create_df(candles: [HistoricCandle]):
    df = DataFrame([{
        'time': c.time,
        'volume': c.volume,
        'open': cast_money(c.open),
        'high': cast_money(c.high),
        'low': cast_money(c.low),
        'close': cast_money(c.close)
    } for c in candles])

    return df


def format_date(utc_date):
    
    local_timezone = pytz.timezone("Europe/Moscow")
    local_time = utc_date.astimezone(local_timezone)
    
    return local_time.strftime("%d-%m-%Y %H:%M")
            




     



        





