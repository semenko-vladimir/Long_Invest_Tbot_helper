from datetime import datetime
import uuid
from tinkoff.invest import Client, RequestError, OrderDirection, OrderType, GetOrdersResponse
from tinkoff.invest.services import SandboxService
from utils.methods import calc_avaliable_lots, check_enough_currency, get_current_price
from utils.helpers import cast_money


def place_order(token: str, figi: str, quantity: str, operation: str, sandbox_method: str):

    if sandbox_method:

        if operation == "buy":
            try:
                with Client(token) as client:

                    sb: SandboxService = client.sandbox
                    accounts = sb.get_sandbox_accounts()
                    account_id = accounts.accounts[0].id

                    avaliable_lots = calc_avaliable_lots(token, figi, client, sandbox_method)

                    if (avaliable_lots > 0):
                        print(f"Позиция {figi} уже в портфеле, ждем сигнала к продаже...")
                        return False, 0
                    
                    # best or fast
                    price_sell, price_buy = get_current_price(figi, client, 'fast')

                    if check_enough_currency(token, figi, client, price_buy, quantity, sandbox_method):

                        r = sb.post_sandbox_order(
                            figi=figi,
                            quantity=quantity,
                            price=price_buy,
                            account_id=account_id,
                            order_id=str(uuid.uuid4()),
                            direction=OrderDirection.ORDER_DIRECTION_BUY,
                            order_type=OrderType.ORDER_TYPE_LIMIT,
                        )

                        print(r)
                        print(f"Покупаем по цене {cast_money(price_buy)}")
                        return True, cast_money(price_buy)
                    
                    else:
                        return False, 0

            except RequestError as e:
                print("Сработало в buy sandbox")
                print(str(e))

        if operation == "sell":
            try:
                with Client(token) as client:

                    sb: SandboxService = client.sandbox
                    accounts = sb.get_sandbox_accounts()
                    account_id = accounts.accounts[0].id

                    avaliable_lots = calc_avaliable_lots(token, figi, client, sandbox_method)

                    if (avaliable_lots == 0):
                        print(f"Позиции {figi} в портфеле нет. Ждем сигнала к покупке...")
                        return False, 0
                    
                    
                    # best or fast
                    price_sell, price_buy = get_current_price(figi, client, 'fast')


                    r = sb.post_sandbox_order(
                        order_id=str(uuid.uuid4()),
                        figi=figi,
                        price=price_sell,
                        quantity=quantity,
                        account_id=account_id,
                        direction=OrderDirection.ORDER_DIRECTION_SELL,
                        order_type=OrderType.ORDER_TYPE_LIMIT,
                    )

                    print(r)
                    print(f"Продаем по цене {cast_money(price_sell)}")
                    return True, cast_money(price_sell)

            except RequestError as e:
                print("Сработало в sell sandbox")
                print(str(e))

        
    else:
        if operation == "buy":
            try:
                with Client(token) as client:
                    accounts = client.users.get_accounts()
                    account_id = accounts.accounts[0].id

                    avaliable_lots = calc_avaliable_lots(token, figi, client, False)

                    if (avaliable_lots > 0):
                        print(f"Позиция {figi} уже в портфеле, ждем сигнала к продаже...")
                        return False, 0
                    
                    price_sell, price_buy = get_current_price(figi, client, 'stock')

                    if check_enough_currency(token, figi, client, price_buy, quantity, False):

                        r = client.orders.post_order(
                            order_id=str(datetime.utcnow().timestamp()),
                            figi=figi,
                            price=price_buy,
                            quantity=quantity,
                            account_id=account_id,
                            direction=OrderDirection.ORDER_DIRECTION_BUY,
                            order_type=OrderType.ORDER_TYPE_LIMIT,
                        )

                        print(r)
                        print(f"Покупаем по цене {cast_money(price_buy)}")
                        return True, cast_money(price_buy)
                    
                    else:
                        return False, 0

            except RequestError as e:
                print(str(e))

        if operation == "sell":
            try:
                with Client(token) as client:
                    accounts = client.users.get_accounts()
                    account_id = accounts.accounts[0].id

                    avaliable_lots = calc_avaliable_lots(token, figi, client, False)

                    if (avaliable_lots == 0):
                        print(f"Позиции {figi} в портфеле нет. Ждем сигнала к покупке...")
                        return False, 0
                    
                    
                    # best or fast
                    price_sell, price_buy = get_current_price(figi, client, 'fast')


                    r = client.orders.post_order(
                        order_id=str(datetime.utcnow().timestamp()),
                        figi=figi,
                        price=price_sell,
                        quantity=quantity,
                        account_id=account_id,
                        direction=OrderDirection.ORDER_DIRECTION_SELL,
                        order_type=OrderType.ORDER_TYPE_LIMIT,
                    )

                    print(r)
                    print(f"Продаем по цене {cast_money(price_sell)}")
                    return True, cast_money(price_sell)

            except RequestError as e:
                print(str(e))


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