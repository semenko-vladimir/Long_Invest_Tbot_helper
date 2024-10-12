
def calculate_profit(average_position_price, current_price_one, brokerFee=0.3):

    comission = ((average_position_price + current_price_one) * brokerFee) / 100

    profit = current_price_one - average_position_price - comission

    current_profit = (100 * profit) / average_position_price

    return current_profit




from tinkoff.invest import Client, PositionsResponse, InstrumentIdType, GetOrdersResponse
from tinkoff.invest.services import InstrumentsService, SandboxService
from methods import cast_money
from datetime import datetime, timedelta
import pytz

def format_date(utc_date):
    
    local_timezone = pytz.timezone("Europe/Moscow")
    local_time = utc_date.astimezone(local_timezone)
    
    return local_time.strftime("%d-%m-%Y %H:%M")

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

def cancel_existing_order(token: str, figi: str, sandbox_method: bool):
    with Client(token) as client:
        if sandbox_method:
            # Для режима песочницы
            sb: SandboxService = client.sandbox
            accounts = sb.get_sandbox_accounts()
            account_id = accounts.accounts[0].id
            orders: GetOrdersResponse = sb.get_sandbox_orders(account_id=account_id)
        else:
            # Для реальных торгов
            accounts = client.users.get_accounts()
            account_id = accounts.accounts[0].id
            orders: GetOrdersResponse = client.orders.get_orders(account_id=account_id)
        
        # Проверяем, есть ли активные заявки
        if len(orders.orders) == 0:
            print("Нет активных заявок.")
            return

        # Находим заявки по figi
        existing_orders = [order for order in orders.orders if order.figi == figi]

        if not existing_orders:
            print(f"Нет активных заявок для инструмента с figi: {figi}")
            return

        # Отменяем каждую заявку
        for order in existing_orders:
            print(f"Отмена заявки: {order.order_id}, цена {cast_money(order.initial_order_price)}")
            try:
                if sandbox_method:
                    sb.cancel_sandbox_order(account_id=account_id, order_id=order.order_id)
                else:
                    client.orders.cancel_order(account_id=account_id, order_id=order.order_id)
                
                print(f"Заявка {order.order_id} успешно отменена.")
            except Exception as e:
                print(f"Ошибка при отмене заявки {order.order_id}: {e}")



     



        





