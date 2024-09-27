from pandas import DataFrame
from tinkoff.invest import Client, RequestError, HistoricCandle, InstrumentStatus
from tinkoff.invest.services import InstrumentsService, MarketDataService
from tinkoff.invest import PortfolioResponse

import credentials
from config import Config

config = Config("MONTH")


def get_price_change_in_current_interval(figi, start_time, end_time, candle_interval):

    try:

        data = get_historic_candles(figi, start_time, end_time, candle_interval)

        df = create_df(data.candles)

        # Проверяем, есть ли данные в DataFrame
        if df.empty:
            print("Нет данных за указанный период")
            return None

        # Получаем цену открытия и цену закрытия
        open_price = df['open'].iloc[0]
        close_price = df['close'].iloc[-1]

        max_price = df['high'].max()
        min_price = df['low'].min()

        # Рассчитываем изменение цены
        price_change = close_price - open_price

        # Рассчитываем процентное изменение цены
        price_change_percent = (price_change / open_price) * 100

        # Выводим результат
        print(f"Изменение цены за период: {price_change:.2f} ({price_change_percent:.2f}%)")
        print(f"Максимальная цена: {max_price:.2f}\n Минимальная цена: {min_price:.2f}")

        # Возвращаем результат
        return price_change, price_change_percent, max_price, min_price, close_price

    except RequestError as e:
        print(str(e))
        return None


def get_historic_candles(figi: str, start_time, end_time, interval):
    with Client(credentials.TOKEN) as client:
        market_data = client.market_data

        data = market_data.get_candles(
            figi=figi,
            from_=start_time,
            to=end_time,
            interval=interval
        )

        return data
    


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

def get_figi_by_ticker(ticker: str):
    with Client(credentials.TOKEN) as client:
        instruments: InstrumentsService = client.instruments

        for method in ["shares", "bonds", "etfs", "currencies", "futures"]:
            data = getattr(instruments, method)().instruments
            figi = next((instrument.figi for instrument in data if instrument.ticker == ticker and instrument.figi.startswith("BBG")), None)
            if figi is None:
                figi = next((instrument.figi for instrument in data if instrument.ticker == ticker), None)
            if figi is not None:
                return figi

        return None

def get_share_figi_by_ticker(ticker: str):
    with Client(credentials.TOKEN) as client:
        instruments: InstrumentsService = client.instruments

        data = instruments.shares(instrument_status=InstrumentStatus.INSTRUMENT_STATUS_ALL).instruments

        figi = next((instrument.figi for instrument in data if
                     instrument.ticker == ticker and instrument.figi.startswith("BBG")), None)

        if figi is None:
            figi = next((instrument.figi for instrument in data if instrument.ticker == ticker and instrument), None)

        if figi is None:
            print("Тикер не найден")
            return

        return figi
    
def get_share_ticker_by_figi(figi: str):
    with Client(credentials.TOKEN) as client:
        instruments: InstrumentsService = client.instruments

        data = instruments.shares(instrument_status=InstrumentStatus.INSTRUMENT_STATUS_ALL).instruments

        ticker = next((instrument.ticker for instrument in data if instrument.figi == figi and instrument.figi.startswith("BBG")), None)

        if ticker is None:
            ticker = next((instrument.ticker for instrument in data if instrument.figi == figi), None)

        if ticker is None:
            print("Тикер не найден")
            return

        return ticker

def get_currency_ticker_by_figi(figi: str):
    with Client(credentials.TOKEN) as client:
        instruments: InstrumentsService = client.instruments

        data = instruments.currencies(instrument_status=InstrumentStatus.INSTRUMENT_STATUS_ALL).instruments

        ticker = next((instrument.ticker for instrument in data if instrument.figi == figi and instrument.figi.startswith("BBG")), None)

        if ticker is None:
            ticker = next((instrument.ticker for instrument in data if instrument.figi == figi), None)

        if ticker is None:
            print("Тикер не найден")
            return

        return ticker
    
def get_etf_ticker_by_figi(figi: str):
    with Client(credentials.TOKEN) as client:
        instruments: InstrumentsService = client.instruments

        data = instruments.etfs(instrument_status=InstrumentStatus.INSTRUMENT_STATUS_ALL).instruments

        ticker = next((instrument.ticker for instrument in data if instrument.figi == figi and instrument.figi.startswith("BBG")), None)

        if ticker is None:
            ticker = next((instrument.ticker for instrument in data if instrument.figi == figi), None)

        if ticker is None:
            print("Тикер не найден")
            return

        return ticker
    

def get_bond_ticker_by_figi(figi: str):
    with Client(credentials.TOKEN) as client:
        instruments: InstrumentsService = client.instruments

        data = instruments.bonds(instrument_status=InstrumentStatus.INSTRUMENT_STATUS_ALL).instruments

        ticker = next((instrument.ticker for instrument in data if instrument.figi == figi and instrument.figi.startswith("BBG")), None)

        if ticker is None:
            ticker = next((instrument.ticker for instrument in data if instrument.figi == figi), None)

        if ticker is None:
            print("Тикер не найден")
            return

        return ticker
    
def get_future_ticker_by_figi(figi: str):
    with Client(credentials.TOKEN) as client:
        instruments: InstrumentsService = client.instruments

        data = instruments.futures(instrument_status=InstrumentStatus.INSTRUMENT_STATUS_ALL).instruments

        ticker = next((instrument.ticker for instrument in data if instrument.figi == figi and instrument.figi.startswith("BBG")), None)

        if ticker is None:
            ticker = next((instrument.ticker for instrument in data if instrument.figi == figi), None)

        if ticker is None:
            print("Тикер не найден")
            return

        return ticker

# def get_last_average_price(figi: str):
#     with Client(creds.TOKEN) as client:
#
#         last_price_response = client.market_data.get_last_prices(figi=figi)
#
#         # Извлекаем список цен
#         last_prices = last_price_response.last_prices
#
#         # Инициализируем сумму цен
#         total_price = 0
#
#         # Итерируемся по списку цен
#         for price in last_prices:
#             # Извлекаем значение цены
#             price_value = price.price.units + price.price.nano / 1e9
#
#             # Добавляем цену к сумме
#             total_price += price_value
#
#         # Вычисляем среднюю цену
#         average_price = total_price / len(last_prices)
#
#         return average_price


def get_share_info_by_ticker(ticker: str):
    with Client(credentials.TOKEN) as client:
        instruments: InstrumentsService = client.instruments

        data = DataFrame(instruments.shares(instrument_status=InstrumentStatus.INSTRUMENT_STATUS_ALL).instruments,

                         columns=['name', 'figi', 'ticker', 'class_code'])

        return data[data['ticker'] == ticker].iloc[0]


def get_info_by_ticker(ticker: str):
    with Client(credentials.TOKEN) as client:
        instruments: InstrumentsService = client.instruments

        l = []

        for method in ["shares", "bonds", "etfs", "currencies", "futures"]:   
            for item in getattr(instruments, method)().instruments:
                l.append({
                    "name": item.name,
                    "figi": item.figi,
                    "ticker": item.ticker,
                    "type": method
                })

        df = DataFrame(l)

        df = df[df['ticker'] == ticker]

        if df.empty:
            print("Тикер не найден")
            return

        return df
    
def get_info_by_figi(figi: str):
    with Client(credentials.TOKEN) as client:
        instruments: InstrumentsService = client.instruments

        l = []

        for method in ["shares", "bonds", "etfs", "currencies", "futures"]:   
            for item in getattr(instruments, method)().instruments:
                l.append({
                    "name": item.name,
                    "figi": item.figi,
                    "ticker": item.ticker,
                    "type": method
                })

        df = DataFrame(l)

        df = df[df['figi'] == figi]

        if df.empty:
            print("Фиги не найден")
            return

        return df


def get_portfolio(token: str):
    with Client(token) as client:
        accounts = client.users.get_accounts()
        account_id = accounts.accounts[0].id
        portfolio: PortfolioResponse = client.operations.get_portfolio(account_id=account_id)


    # Общая стоимость акций
    total_amount_shares = cast_money(portfolio.total_amount_shares)
    # Общая стоимость облигаций
    total_amount_bonds = cast_money(portfolio.total_amount_bonds)
    # Общая стоимость фондов
    total_amount_etf = cast_money(portfolio.total_amount_etf)
    # Общая стоимость валют
    total_amount_currencies = cast_money(portfolio.total_amount_currencies)
    # Ожидаемый доход
    expected_yield = cast_money(portfolio.expected_yield)
    # Общая стоимость портфеля
    total_amount_portfolio = cast_money(portfolio.total_amount_portfolio)

    positions = []

    for position in portfolio.positions:

        if position.instrument_type == "share":
            position_ticker = get_share_ticker_by_figi(position.figi)
        elif position.instrument_type == "bond":
            position_ticker = get_bond_ticker_by_figi(position.figi)
        elif position.instrument_type == "etf":
            position_ticker = get_etf_ticker_by_figi(position.figi)
        elif position.instrument_type == "currency":
            position_ticker = get_currency_ticker_by_figi(position.figi)
        elif position.instrument_type == "future":
            position_ticker = get_future_ticker_by_figi(position.figi)

        position_info = get_info_by_figi(position.figi)

        position_type = ""
        

        if position.instrument_type == "share":
            position_type = "Акция"
        elif position.instrument_type == "bond":
            position_type = "Облигация"
        elif position.instrument_type == "etf":
            position_type = "Фонд"
        elif position.instrument_type == "currency":
            position_type = "Валюта"
        elif position.instrument_type == "future":
            position_type = "Фьючерс"

        is_blocked = ""

        if position.blocked:
            is_blocked = "Заблокирована"
        else:
            is_blocked = "Активна"

        data = {
            "name": position_info['name'].values[0:1][0] if position_info is not None else "Нет информации",
            "ticker": position_ticker,
            "type": position_type,
            "figi": position.figi,

            "quantity": cast_money(position.quantity),
            "average_position_price": cast_money(position.average_position_price),
            "expected_yield": cast_money(position.expected_yield),

            "current_price": round(cast_money(position.current_price) * cast_money(position.quantity), 2),
            "current_price_one": cast_money(position.current_price),
            "blocked": is_blocked
        }

        positions.append(data)

    return {
        'total_amount_shares': total_amount_shares,
        'total_amount_bonds': total_amount_bonds,
        'total_amount_etf': total_amount_etf,
        'total_amount_currencies': total_amount_currencies,
        'expected_yield': expected_yield,
        'total_amount_portfolio': total_amount_portfolio,
        'positions': positions
    }

def get_instrument_from_portfolio_by_ticker(token: str, figi: str, ticker: str):

    with Client(token) as client:
        accounts = client.users.get_accounts()
        account_id = accounts.accounts[0].id
        portfolio: PortfolioResponse = client.operations.get_portfolio(account_id=account_id)

    for position in portfolio.positions:

        if position.figi == figi:
            position_info = get_info_by_figi(position.figi)

            position_type = ""
            

            if position.instrument_type == "share":
                position_type = "Акция"
            elif position.instrument_type == "bond":
                position_type = "Облигация"
            elif position.instrument_type == "etf":
                position_type = "Фонд"
            elif position.instrument_type == "currency":
                position_type = "Валюта"
            elif position.instrument_type == "future":
                position_type = "Фьючерс"

            is_blocked = ""

            if position.blocked:
                is_blocked = "Заблокирована"
            else:
                is_blocked = "Активна"

            data = {
                "name": position_info['name'].values[0:1][0] if position_info is not None else "Нет информации",
                "ticker": ticker,
                "type": position_type,
                "figi": position.figi,

                "quantity": cast_money(position.quantity),
                "average_position_price": cast_money(position.average_position_price),
                "expected_yield": cast_money(position.expected_yield),

                "current_price": round(cast_money(position.current_price) * cast_money(position.quantity), 2),
                "current_price_one": cast_money(position.current_price),
                "blocked": is_blocked
            }

            return data

    return None
            


# from tinkoff.invest import CandleInterval
# from datetime import datetime, timedelta
# figi = get_figi_by_ticker("GAZP")
# data = get_historic_candles(figi, datetime.utcnow() - timedelta(days=30), datetime.utcnow(), CandleInterval.CANDLE_INTERVAL_WEEK)
# print(data)