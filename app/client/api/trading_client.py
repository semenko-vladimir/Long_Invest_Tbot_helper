from typing import List, Dict, Any, Optional
from app.client.api.base_client import BaseApiClient


class TradingApiClient(BaseApiClient):
    """
    Клиент API для работы с торговыми операциями.
    """
    
    # Margins methods
    def get_margins(self) -> List[Dict[str, Any]]:
        """
        Получает список всех маржинальных позиций.
        
        Returns:
            List[Dict[str, Any]]: Список маржинальных позиций
        """
        return self._get("trading/margin/")
    
    def add_margin(self, margin: float, ticker: str, signal: str, time: Optional[str] = None) -> Dict[str, Any]:
        """
        Добавляет новую маржинальную позицию.
        
        Args:
            margin: Маржа
            ticker: Тикер
            signal: Сигнал
            time: Время (опционально)
            
        Returns:
            Dict[str, Any]: Добавленная маржинальная позиция
        """
        data = {"margin": margin, "ticker": ticker, "signal": signal}
        if time:
            data["time"] = time
        return self._post("trading/margin/", data)
    
    # Buys methods
    def get_buys(self) -> List[Dict[str, Any]]:
        """
        Получает список всех покупок.
        
        Returns:
            List[Dict[str, Any]]: Список покупок
        """
        return self._get("trading/buy/")
    
    def add_buy(self, price: float, ticker: str, signal: str, time: Optional[str] = None) -> Dict[str, Any]:
        """
        Добавляет новую покупку.
        
        Args:
            price: Цена
            ticker: Тикер
            signal: Сигнал
            time: Время (опционально)
            
        Returns:
            Dict[str, Any]: Добавленная покупка
        """
        data = {"price": price, "ticker": ticker, "signal": signal}
        if time:
            data["time"] = time
        return self._post("trading/buy/", data)
    
    # Orders methods
    def get_orders(self) -> List[Dict[str, Any]]:
        """
        Получает список всех заказов.
        
        Returns:
            List[Dict[str, Any]]: Список заказов
        """
        return self._get("trading/orders/")
    
    def get_all_orders(self) -> List[Dict[str, Any]]:
        """
        Получает список всех заказов (алиас для get_orders).
        
        Returns:
            List[Dict[str, Any]]: Список заказов
        """
        return self.get_orders()
    
    def add_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Добавляет новый заказ.
        
        Args:
            data: Словарь с данными заказа, содержащий:
                - order_id: ID заказа
                - ticker: Тикер
                - signal: Сигнал
                - bm_value: Значение BM
                - operation_type: Тип операции
            
        Returns:
            Dict[str, Any]: Добавленный заказ
        """
        return self._post("trading/orders/", data)
    
    def delete_order(self, order_id: str) -> Dict[str, Any]:
        """
        Удаляет заказ по order_id.
        
        Args:
            order_id: ID заказа
            
        Returns:
            Dict[str, Any]: Удаленный заказ
        """
        return self._delete(f"trading/orders/{order_id}")
