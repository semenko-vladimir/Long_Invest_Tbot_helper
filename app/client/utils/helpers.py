from pandas import DataFrame
from tinkoff.invest import HistoricCandle
import pytz

def calculate_profit(average_position_price, current_price_one, brokerFee=0.3):

    """
    Рассчитывает прибыль в %

    :param average_position_price: Средняя цена позиции
    :param current_price_one: Текущая цена одного лота
    :param brokerFee: Комиссия брокера (%), default=0.3
    :return: Прибыль в %
    """
    
    comission = ((average_position_price + current_price_one) * brokerFee) / 100

    profit = current_price_one - average_position_price - comission

    current_profit = (100 * profit) / average_position_price

    return current_profit

def to_quotation(value: float) -> dict:
    """
    Преобразует вещественное число в формат, пригодный для отправки
    в Tinkoff Invest API (quotation).

    :param value: вещественное число
    :return: кортеж из двух целых чисел
             (sign * units, sign * nano),
             где:
             - units - целая часть значения (целое число)
             - nano - дробная часть (в нанoe) (целое число)

    """
    sign = -1 if value < 0 else 1
    abs_value = abs(value)
    units = int(abs_value)
    nano = round((abs_value - units) * 1e9)

    return sign * units, sign * nano


def to_money_value(value):

    """
    Преобразует вещественное число в MoneyValue, пригодный для 
    отправки в Tinkoff Invest API

    :param value: вещественное число
    :return: MoneyValue (кортеж из двух целых чисел)
             (units, nano),
             где:
             - units - целая часть значения (целое число)
             - nano - дробная часть (в нанoe) (целое число)

    """
    units, nano = to_quotation(value)

    return units, nano

def cast_money(v):
    """
    Преобразует MoneyValue в вещественное число.

    :param v: MoneyValue (кортеж из двух целых чисел)
             (units, nano),
             где:
             - units - целая часть значения (целое число)
             - nano - дробная часть (в нанoe) (целое число)

    :return: вещественное число
    """
    return v.units + v.nano / 1e9


def create_df(candles: [HistoricCandle]):
    """
    Создает DataFrame из списка исторических свечей.

    :param candles: Список объектов HistoricCandle, содержащих данные о свечах.
    :return: DataFrame с колонками 'time', 'volume', 'open', 'high', 'low', 'close',
             где 'time' - время свечи, 'volume' - объем, 'open' - цена открытия,
             'high' - максимальная цена, 'low' - минимальная цена, 'close' - цена закрытия.
    """

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
    
    """
    Переводит время в UTC в локальное время по Московскому часовому поясу
    и форматирует его в строку в формате "DD-MM-YYYY HH:MM".

    :param utc_date: Timezone-naive datetime object in UTC timezone
    :return: String, formatted as "DD-MM-YYYY HH:MM"
    """
    local_timezone = pytz.timezone("Europe/Moscow")
    local_time = utc_date.astimezone(local_timezone)
    
    return local_time.strftime("%d-%m-%Y %H:%M")
            




     



        





