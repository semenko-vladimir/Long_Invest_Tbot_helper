from pandas import DataFrame
from tinkoff.invest import Client, RequestError, InstrumentStatus, PositionsResponse
from tinkoff.invest.services import InstrumentsService
from tinkoff.invest import PortfolioResponse
from datetime import datetime, timedelta
import credentials
from utils.helpers import cast_money, create_df, format_date
from tinkoff.invest import InstrumentIdType


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
    

def get_current_price(figi: str, client, type_op: str):
        
    if type_op == "best":

        book = client.market_data.get_order_book(figi=figi, depth=50)

        # Быстрая цена
        #fast_price_sell, fast_price_buy = book.asks[0], book.bids[0]

        # Лучшая цена
        #best_price_sell, best_price_buy = book.asks[-1], book.bids[-1]

        return book.asks[-1].price, book.bids[-1].price

    else:

        book = client.market_data.get_order_book(figi=figi, depth=50)

        # Быстрая цена
        #fast_price_sell, fast_price_buy = book.asks[0], book.bids[0]

        # Лучшая цена
        #best_price_sell, best_price_buy = book.asks[-1], book.bids[-1]

        return book.asks[0].price, book.bids[0].price



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
    
def get_ticker_by_figi(figi: str, instrument_type: str):
    with Client(credentials.TOKEN) as client:
        instruments: InstrumentsService = client.instruments

        # Карта методов для различных типов инструментов
        method_map = {
            "share": instruments.shares,
            "bond": instruments.bonds,
            "etf": instruments.etfs,
            "currency": instruments.currencies,
            "future": instruments.futures,
        }

        # Получаем метод в зависимости от типа инструмента
        method = method_map.get(instrument_type.lower())
        
        if method is not None:
            # Получаем инструменты только нужного типа
            data = method().instruments

            # Ищем тикер по FIGI
            ticker = next((instrument.ticker for instrument in data if instrument.figi == figi), None)
            return ticker
        
        return None

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

        position_ticker = get_ticker_by_figi(position.figi, position.instrument_type)

        if position_ticker is None:
            position_ticker = "Нет информации"
        #position_info = get_info_by_figi(position.figi)

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
            #"name": position_info['name'].values[0:1][0] if position_info is not None else "Нет информации",
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

from tinkoff.invest.services import SandboxService

def get_sandbox_portfolio(token: str):

    portfolio = None

    with Client(token) as client:
        sb: SandboxService = client.sandbox

        accounts = sb.get_sandbox_accounts()
        account_id = accounts.accounts[0].id
        portfolio: PortfolioResponse = sb.get_sandbox_portfolio(account_id=account_id)


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

        position_ticker = get_ticker_by_figi(position.figi, position.instrument_type)

        if position_ticker is None:
            position_ticker = "Нет информации"

        #position_info = get_info_by_figi(position.figi)

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
            #"name": position_info['name'].values[0:1][0] if position_info is not None else "Нет информации",
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

def get_instrument_from_portfolio_by_ticker(token: str, figi: str, ticker: str, sandbox_method):

    portfolio = None

    if sandbox_method:
        with Client(token) as client:
            sb: SandboxService = client.sandbox
            accounts = sb.get_sandbox_accounts()
            account_id = accounts.accounts[0].id
            portfolio: PortfolioResponse = sb.get_sandbox_portfolio(account_id=account_id)
    else:
        with Client(token) as client:
            accounts = client.users.get_accounts()
            account_id = accounts.accounts[0].id
            portfolio: PortfolioResponse = client.operations.get_portfolio(account_id=account_id)


    for position in portfolio.positions:

        if position.figi == figi:
            #position_info = get_info_by_figi(position.figi)

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
                #"name": position_info['name'].values[0:1][0] if position_info is not None else "Нет информации",
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
            

def get_dividends_data(token: str, period, figi):

    with Client(token) as client:

        instruments_service: InstrumentsService = client.instruments

        data = instruments_service.get_dividends(figi=figi, from_=datetime.now(), to=datetime.now() + timedelta(days=period)).dividends

        if len(data) > 0:
            return {
                'dividend_net': cast_money(data[0].dividend_net),
                'payment_date': format_date(data[0].payment_date),
                'declared_date': format_date(data[0].declared_date),
                'last_buy_date': format_date(data[0].last_buy_date),
                'record_date': format_date(data[0].record_date),
                'yield_value': cast_money(data[0].yield_value)
            }


def get_balance(token: str, client, sandbox_method):

    positions = None

    if sandbox_method:
        with Client(token) as client:
            sb: SandboxService = client.sandbox
            accounts = sb.get_sandbox_accounts()
            account_id = accounts.accounts[0].id
            positions: PositionsResponse = sb.get_sandbox_positions(account_id=account_id)
    else:
        with Client(token) as client:
            accounts = client.users.get_accounts()
            account_id = accounts.accounts[0].id
            positions: PositionsResponse = client.operations.get_positions(account_id=account_id)

    print(positions)

    # Поиск суммы в рублях
    rub_balance = None
    for money in positions.money:
        if money.currency == 'rub':
            rub_balance = cast_money(money)
            break

    if rub_balance is not None:
        print(f"Баланс в рублях: {rub_balance} RUB")
        return rub_balance
    else:
        print("Баланс в рублях не найден.")


def get_available_qty(token: str, figi: str, client, sandbox_method):

        positions = None

        if sandbox_method:
            with Client(token) as client:
                sb: SandboxService = client.sandbox
                accounts = sb.get_sandbox_accounts()
                account_id = accounts.accounts[0].id
                positions: PositionsResponse = sb.get_sandbox_positions(account_id=account_id)
        else:
            with Client(token) as client:
                accounts = client.users.get_accounts()
                account_id = accounts.accounts[0].id
                positions: PositionsResponse = client.operations.get_positions(account_id=account_id)


        # Поиск ценной бумаги с указанным figi
        item = next((security for security in positions.securities if security.figi == figi), None)

        if item:
            print(f"Доступное количество для {figi}: {item.balance}")
            return item.balance
        else:
            print(f"Ценная бумага с figi {figi} не найдена.")
            return 0
        

def get_lotSize(token: str, figi: str, client):

        instruments: InstrumentsService = client.instruments

        ins = instruments.get_instrument_by(id=figi, id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI)

        if ins.instrument.lot:
            return ins.instrument.lot
        else: 
            return 0

def calc_avaliable_lots(token, figi, client, sandbox_method):

    availableQty = get_available_qty(token, figi, client, sandbox_method)
    lotSize = get_lotSize(token, figi, client)
    return round(availableQty / lotSize)


def check_enough_currency(token: str, figi: str, client, buy_price, quantity, sandbox_method):
     
    brokerFee = 0.3

    price = cast_money(buy_price)

    order_price = price * quantity * get_lotSize(token, figi, client)

    order_price_with_comission = order_price * (1 + brokerFee / 100)

    balance = get_balance(token, client, sandbox_method)

    if(order_price_with_comission > balance):
         print("Недостаточно средств для покупки")
         return False
    
    return True

