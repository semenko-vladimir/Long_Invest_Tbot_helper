from datetime import datetime
import uuid
from tinkoff.invest import Client, RequestError, OrderDirection, OrderType, GetOrdersResponse
from tinkoff.invest.services import SandboxService
from db.db import delete_order, get_orders, new_buy, new_margin, new_order
from log.logger import setup_logger
from utils.methods import calc_avaliable_lots, check_enough_currency, get_current_price
from utils.helpers import cast_money, format_date

logger = setup_logger(__name__)
from bot.bot import bot

def place_order(token: str, figi: str, quantity: str, operation: str, sandbox_method: str, ticker, bm_value, signal, chat_id):
    """
    Метод для выставления заявки на покупку или продажу актива.

    :param token: токен для доступа к API
    :param figi: уникальный идентификатор финансового инструмента (FIGI)
    :param quantity: количество лотов
    :param operation: тип операции ("buy" или "sell")
    :param sandbox_method: флаг, указывающий режим работы:
        - True: Песочница (sandbox).
        - False: Реальный рынок.
    :param ticker: тикер актива
    :param bm_value: значение бенчмарка
    :param signal: значение сигнала
    :param chat_id: id чата в телеграмме

    :return: None
    """

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
                        return 
                    
                    # best or fast
                    price_sell, price_buy = get_current_price(figi, client, 'fast')

                    if check_enough_currency(token, figi, client, price_buy, quantity, sandbox_method):
                        
                        order_id = str(uuid.uuid4())

                        r = sb.post_sandbox_order(
                            figi=figi,
                            quantity=quantity,
                            price=price_buy,
                            account_id=account_id,
                            order_id=order_id,
                            direction=OrderDirection.ORDER_DIRECTION_BUY,
                            order_type=OrderType.ORDER_TYPE_LIMIT,
                        )

                        new_order(order_id, ticker, signal, cast_money(price_buy), operation, chat_id)
                        logger.info(r)
                        logger.info(f"Создаем заявку на покупку по цене {cast_money(price_buy)}")
                    #     return True, cast_money(price_buy)
                    
                    # else:
                    #     return False, 0

            except RequestError as e:
                logger.error(str(e))

        if operation == "sell":
            try:
                with Client(token) as client:

                    sb: SandboxService = client.sandbox
                    accounts = sb.get_sandbox_accounts()
                    account_id = accounts.accounts[0].id

                    avaliable_lots = calc_avaliable_lots(token, figi, client, sandbox_method)

                    if (avaliable_lots == 0):
                        print(f"Позиции {figi} в портфеле нет. Ждем сигнала к покупке...")
                        return 
                    
                    
                    # best or fast
                    price_sell, price_buy = get_current_price(figi, client, 'fast')

                    order_id = str(uuid.uuid4())

                    r = sb.post_sandbox_order(
                        order_id=order_id,
                        figi=figi,
                        price=price_sell,
                        quantity=quantity,
                        account_id=account_id,
                        direction=OrderDirection.ORDER_DIRECTION_SELL,
                        order_type=OrderType.ORDER_TYPE_LIMIT,
                    )

                    new_order(order_id, ticker, signal, bm_value, operation, chat_id)

                    logger.info(r)
                    logger.info(f"Создаем заявку на продажу по цене {cast_money(price_sell)}")
                    # return True, cast_money(price_sell)

            except RequestError as e:
                logger.error(str(e))

        
    else:
        if operation == "buy":
            try:
                with Client(token) as client:
                    accounts = client.users.get_accounts()
                    account_id = accounts.accounts[0].id

                    avaliable_lots = calc_avaliable_lots(token, figi, client, False)

                    if (avaliable_lots > 0):
                        logger.info(f"Позиция {figi} уже в портфеле, ждем сигнала к продаже...")
                        return 
                    
                    price_sell, price_buy = get_current_price(figi, client, 'stock')

                    if check_enough_currency(token, figi, client, price_buy, quantity, False):
                        
                        order_id = str(uuid.uuid4())

                        r = client.orders.post_order(
                            order_id=order_id,
                            figi=figi,
                            price=price_buy,
                            quantity=quantity,
                            account_id=account_id,
                            direction=OrderDirection.ORDER_DIRECTION_BUY,
                            order_type=OrderType.ORDER_TYPE_LIMIT,
                            #str(datetime.utcnow().timestamp())
                        )

                        new_order(order_id, ticker, signal, cast_money(price_buy), operation, chat_id)

                        logger.info(r)
                        logger.info(f"Покупаем по цене {cast_money(price_buy)}")
                    #     return True, cast_money(price_buy)
                    
                    # else:
                    #     return False, 0

            except RequestError as e:
                logger.error(str(e))

        if operation == "sell":
            try:
                with Client(token) as client:
                    accounts = client.users.get_accounts()
                    account_id = accounts.accounts[0].id

                    avaliable_lots = calc_avaliable_lots(token, figi, client, False)

                    if (avaliable_lots == 0):
                        logger.info(f"Позиции {figi} в портфеле нет. Ждем сигнала к покупке...")
                        return 
                    
                    
                    # best or fast
                    price_sell, price_buy = get_current_price(figi, client, 'fast')
                    
                    order_id = str(uuid.uuid4())

                    r = client.orders.post_order(
                        order_id=order_id,
                        figi=figi,
                        price=price_sell,
                        quantity=quantity,
                        account_id=account_id,
                        direction=OrderDirection.ORDER_DIRECTION_SELL,
                        order_type=OrderType.ORDER_TYPE_LIMIT,
                        #str(datetime.utcnow().timestamp())
                    )

                    new_order(order_id, ticker, signal, bm_value, operation, chat_id)

                    logger.info(r)
                    logger.info(f"Продаем по цене {cast_money(price_sell)}")
                    # return True, cast_money(price_sell)

            except RequestError as e:
                logger.error(str(e))


def cancel_existing_order(token: str, figi: str, sandbox_method: bool):
    """
    Отменяет существующие заявки на инструмент с указанным figi в режиме песочницы или на реальном рынке.

    :param token: Токен для доступа к API Tinkoff Invest.
    :param figi: Уникальный идентификатор финансового инструмента (FIGI).
    :param sandbox_method: Флаг, указывающий режим работы:
        - True: Песочница (sandbox).
        - False: Реальный рынок.

    :return: None
    """
    
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
            logger.info("Нет активных заявок.")
            return

        # Находим заявки по figi
        existing_orders = [order for order in orders.orders if order.figi == figi]

        if not existing_orders:
            logger.info(f"Нет активных заявок для инструмента с figi: {figi}")
            return

        # Отменяем каждую заявку
        for order in existing_orders:
            logger.warning(f"Отмена заявки: {order.order_id}, цена {cast_money(order.initial_order_price)}")
            try:
                if sandbox_method:
                    sb.cancel_sandbox_order(account_id=account_id, order_id=order.order_id)
                else:
                    client.orders.cancel_order(account_id=account_id, order_id=order.order_id)
                
                logger.info(f"Заявка {order.order_id} успешно отменена.")
            except Exception as e:
                logger.error(f"Ошибка при отмене заявки {order.order_id}: {e}")


def get_order_by_figi(token: str, figi: str, sandbox_method: str):

    """
    Проверяет, есть ли активные заявки на инструмент с указанным figi в режиме песочницы или на реальном рынке.

    :param token: Токен для доступа к API Tinkoff Invest.
    :param figi: Уникальный идентификатор финансового инструмента (FIGI).
    :param sandbox_method: Флаг, указывающий режим работы:
        - True: Песочница (sandbox).
        - False: Реальный рынок.

    :return: True, если заявок на инструмент с указанным figi нет, иначе False.
    """
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
            return True

        # Находим заявки по figi
        existing_orders = [order for order in orders.orders if order.figi == figi]

        if not existing_orders:
            return True

        return False
    

def check_orders(token: str, chat_id, sandbox_method: bool):

    """
    Проверяет, есть ли активные заявки на инструмент с указанным figi в режиме песочницы или на реальном рынке.

    :param token: Токен для доступа к API Tinkoff Invest.
    :param figi: Уникальный идентификатор финансового инструмента (FIGI).
    :param sandbox_method: Флаг, указывающий режим работы:
        - True: Песочница (sandbox).
        - False: Реальный рынок.

    :return: None
    """
    orders = None

    local_time = datetime.now()

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
            return
        

    orders_db = get_orders(chat_id)

    if len(orders_db) == 0:
        return

    for row in orders_db:
        _id = row[0]
        order_id = row[1]
        ticker = row[2]
        signal = row[3]
        bm_value = row[4]
        operation_type = row[5]

        # Находим заявку по order_id
        existing_order = [order for order in orders.orders if order.order_id == order_id]

        if not existing_order:

            delete_order(order_id)

            if operation_type == "buy":
                new_buy(bm_value, ticker, signal, format_date(local_time), chat_id)
                bot.send_message(chat_id, f"Автоматическая торговля. Покупка {ticker} по сигналу {signal}")
                logger.info(f"Automatic trading. Purchase {ticker} on the signal {signal}. Sale price: {bm_value}")

            elif operation_type == "sell":
                new_margin(bm_value, ticker, signal, format_date(local_time), chat_id)
                bot.send_message(chat_id, f"Продаем {ticker} по сигналу {signal}")
                logger.info(f"Automatic trading. Selling {ticker} on the signal {signal}. Estimated margin: {bm_value}")
