from datetime import datetime

from tinkoff.invest import Client, RequestError, OrderDirection, OrderType

from helpers import calc_avaliable_lots, check_enough_currency, get_balance
from methods import cast_money, get_current_price

def place_order(token: str, figi: str, quantity: str, operation: str, type_order='limit'):

    if operation == "buy":
        try:
            with Client(token) as client:
                accounts = client.users.get_accounts()
                account_id = accounts.accounts[0].id

                avaliable_lots = calc_avaliable_lots(token, figi, client)

                if (avaliable_lots > 0):
                    print(f"Позиция {figi} уже в портфеле, ждем сигнала к продаже...")
                    return
                
                if type_order == 'market':
                    
                    r = client.orders.post_order(
                        order_id=str(datetime.utcnow().timestamp()),
                        figi=figi,
                        quantity=quantity,
                        account_id=account_id,
                        direction=OrderDirection.ORDER_DIRECTION_BUY,
                        order_type=OrderType.ORDER_TYPE_MARKET,
                    )

                    print(r)
                    
                elif type_order == 'limit':

                    price_sell, price_buy = get_current_price(figi, client, 'stock')

                    if check_enough_currency(token, figi, client, price_buy, quantity):

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

        except RequestError as e:
            print(str(e))

    if operation == "sell":
        try:
            with Client(token) as client:
                accounts = client.users.get_accounts()
                account_id = accounts.accounts[0].id

                avaliable_lots = calc_avaliable_lots(token, figi, client)

                if (avaliable_lots == 0):
                    print(f"Позиции {figi} в портфеле нет. Ждем сигнала к покупке...")
                    return
                
                
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


                


        except RequestError as e:
            print(str(e))




