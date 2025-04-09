from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
from tinkoff.invest import Client, RequestError, OrderDirection, OrderType, GetOrdersResponse
from tinkoff.invest.services import SandboxService
from app.client.api.trading_client import TradingApiClient
from app.client.log.logger import setup_logger
from app.client.utils.methods import calc_avaliable_lots, check_enough_currency, get_current_price
from app.client.utils.helpers import cast_money, format_date
from app.client.bot.bot import bot



trading_client = TradingApiClient()
logger = setup_logger(__name__)

def place_order(token: str, figi: str, quantity: str, operation: str, sandbox_method: str, ticker, bm_value, signal):
    """
    Метод для выставления заявки на покупку или продажу актива.

    Args:
        token: токен для доступа к API
        figi: уникальный идентификатор финансового инструмента (FIGI)
        quantity: количество лотов
        operation: тип операции ("buy" или "sell")
        sandbox_method: флаг, указывающий режим работы:
            - True: Песочница (sandbox).
            - False: Реальный рынок.
        ticker: тикер актива
        bm_value: значение бенчмарка
        signal: значение сигнала

    Returns:
        None
    """

    if sandbox_method:
        if operation == "buy":
            try:
                with Client(token) as client:
                    sb: SandboxService = client.sandbox
                    accounts = sb.get_sandbox_accounts()
                    account_id = accounts.accounts[0].id

                    avaliable_lots, lotSize = calc_avaliable_lots(token, figi, client, sandbox_method)

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

                        # Создаем новый ордер через API клиент
                        trading_client.add_order({
                            "order_id": order_id,
                            "ticker": ticker,
                            "signal": signal,
                            "bm_value": cast_money(price_buy) * lotSize * quantity,
                            "operation_type": operation
                        })

                        logger.info(r)
                        logger.info(f"Создаем заявку на покупку по цене {cast_money(price_buy)}")

            except RequestError as e:
                logger.error(str(e))

        if operation == "sell":
            try:
                with Client(token) as client:
                    sb: SandboxService = client.sandbox
                    accounts = sb.get_sandbox_accounts()
                    account_id = accounts.accounts[0].id

                    avaliable_lots, _ = calc_avaliable_lots(token, figi, client, sandbox_method)

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

                    # Создаем новый ордер через API клиент
                    trading_client.add_order({
                        "order_id": order_id,
                        "ticker": ticker,
                        "signal": signal,
                        "bm_value": bm_value,
                        "operation_type": operation
                    })

                    logger.info(r)
                    logger.info(f"Создаем заявку на продажу по цене {cast_money(price_sell)}")

            except RequestError as e:
                logger.error(str(e))
    else:
        if operation == "buy":
            try:
                with Client(token) as client:
                    accounts = client.users.get_accounts()
                    account_id = accounts.accounts[0].id

                    avaliable_lots, lotSize = calc_avaliable_lots(token, figi, client, False)

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
                        )

                        # Создаем новый ордер через API клиент
                        trading_client.add_order({
                            "order_id": order_id,
                            "ticker": ticker,
                            "signal": signal,
                            "bm_value": cast_money(price_buy) * lotSize * quantity,
                            "operation_type": operation
                        })

                        logger.info(r)
                        logger.info(f"Покупаем по цене {cast_money(price_buy)}")

            except RequestError as e:
                logger.error(str(e))

        if operation == "sell":
            try:
                with Client(token) as client:
                    accounts = client.users.get_accounts()
                    account_id = accounts.accounts[0].id

                    avaliable_lots, _ = calc_avaliable_lots(token, figi, client, False)

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
                    )

                    # Создаем новый ордер через API клиент
                    trading_client.add_order({
                        "order_id": order_id,
                        "ticker": ticker,
                        "signal": signal,
                        "bm_value": bm_value,
                        "operation_type": operation
                    })

                    logger.info(r)
                    logger.info(f"Продаем по цене {cast_money(price_sell)}")

            except RequestError as e:
                logger.error(str(e))


def cancel_existing_order(token: str, figi: str, sandbox_method: bool):
    """
    Отменяет существующие заявки на инструмент с указанным figi в режиме песочницы или на реальном рынке.

    Args:
        token: Токен для доступа к API Tinkoff Invest.
        figi: Уникальный идентификатор финансового инструмента (FIGI).
        sandbox_method: Флаг, указывающий режим работы:
            - True: Песочница (sandbox).
            - False: Реальный рынок.

    Returns:
        None
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

    Args:
        token: Токен для доступа к API Tinkoff Invest.
        figi: Уникальный идентификатор финансового инструмента (FIGI).
        sandbox_method: Флаг, указывающий режим работы:
            - True: Песочница (sandbox).
            - False: Реальный рынок.

    Returns:
        True, если заявок на инструмент с указанным figi нет, иначе False.
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
    

def check_orders(token: str, chat_id=None, sandbox_method: bool=False):
    """
    Проверяет, есть ли активные заявки на инструмент с указанным figi в режиме песочницы или на реальном рынке.

    Args:
        token: Токен для доступа к API Tinkoff Invest.
        chat_id: ID чата в Telegram (опционально).
        sandbox_method: Флаг, указывающий режим работы:
            - True: Песочница (sandbox).
            - False: Реальный рынок.

    Returns:
        None
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
        
    # Получаем все ордеры через API клиент
    orders_db = trading_client.get_all_orders()

    if not orders_db or len(orders_db) == 0:
        return

    for order in orders_db:
        order_id = order.get('order_id')
        ticker = order.get('ticker')
        signal = order.get('signal')
        bm_value = order.get('bm_value')
        operation_type = order.get('operation_type')

        # Находим заявку по order_id
        existing_order = [o for o in orders.orders if str(o.order_id) == order_id]

        if not existing_order:
            # Удаляем ордер через API клиент, используя улучшенный метод
            trading_client.delete_order(order_id)

            if operation_type == "buy":
                # Создаем новую покупку через API клиент
                trading_client.add_buy(
                    price=float(bm_value),
                    ticker=str(ticker),
                    signal=str(signal),
                    time=format_date(local_time)
                )
                
                # Получаем ID чата из переменных окружения
                load_dotenv()
                chat_id = os.getenv('CHAT_ID')
                
                if chat_id:
                    bot.send_message(chat_id, f"Автоматическая торговля. Покупка {ticker} по сигналу {signal}")
                
                logger.info(f"Automatic trading. Purchase {ticker} on the signal {signal}. Sale price: {bm_value}")

            elif operation_type == "sell":
                # Создаем новую маржу через API клиент
                trading_client.add_margin(
                    margin=float(bm_value),
                    ticker=str(ticker),
                    signal=str(signal),
                    time=format_date(local_time)
                )
                
                # Получаем ID чата из переменных окружения
                load_dotenv()
                chat_id = os.getenv('CHAT_ID')
                
                if chat_id:
                    bot.send_message(chat_id, f"Продаем {ticker} по сигналу {signal}")
                
                logger.info(f"Automatic trading. Selling {ticker} on the signal {signal}. Estimated margin: {bm_value}")
