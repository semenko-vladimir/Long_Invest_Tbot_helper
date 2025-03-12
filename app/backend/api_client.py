import requests
from typing import List, Dict, Any, Optional, Union
from datetime import datetime



class ApiClient:
    """
    Клиент для взаимодействия с API.
    Предоставляет методы для работы с различными ресурсами API.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Инициализирует клиент API.
        
        Args:
            base_url: Базовый URL API-сервера
        """
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
    
    # Config methods
    def get_config(self) -> Dict[str, Any]:
        """
        Получает общую конфигурацию.
        
        Returns:
            Dict[str, Any]: Конфигурация или значения по умолчанию
        """
        try:
            response = requests.get(f"{self.api_url}/config/")
            data = response.json()
            if data and len(data) > 0:
                return data[0]
            else:
                # Если конфигурация не найдена, получаем chat_id из переменных окружения
                from dotenv import load_dotenv
                import os
                
                load_dotenv()
                chat_id = os.getenv('CHAT_ID')
                
                # Создаем новую конфигурацию
                config = {
                    "chat_id": chat_id,
                    "collapse_updates": False,
                    "collapse_updates_time": "60",
                    "market_updates": False,
                    "market_updates_time": "60",
                    "sandbox_trigger": False
                }
                
                # Сохраняем конфигурацию в базе данных
                response = requests.post(f"{self.api_url}/config/", json=config)
                return response.json()
        except Exception as e:
            # В случае ошибки возвращаем значения по умолчанию
            from dotenv import load_dotenv
            import os
            
            load_dotenv()
            chat_id = os.getenv('CHAT_ID')
            
            return {
                "chat_id": chat_id,
                "collapse_updates": False,
                "collapse_updates_time": "60",
                "market_updates": False,
                "market_updates_time": "60",
                "sandbox_trigger": False
            }
    
    def get_sandbox_trigger(self) -> bool:
        """
        Получает значение флага sandbox_trigger.
        
        Returns:
            bool: Значение флага
        """
        response = requests.get(f"{self.api_url}/config/sandbox-trigger/")
        return response.json()
    
    def set_sandbox_trigger(self, value: bool) -> Dict[str, Any]:
        """
        Устанавливает значение флага sandbox_trigger.
        
        Args:
            value: Новое значение флага
            
        Returns:
            Dict[str, Any]: Обновленная конфигурация
        """
        response = requests.put(f"{self.api_url}/config/sandbox-trigger/", json={"value": value})
        return response.json()
    
    def update_config_collapse(
        self, 
        collapse_updates_time: str, 
        collapse_updates: bool, 
        market_updates_time: str, 
        market_updates: bool
    ) -> Dict[str, Any]:
        """
        Обновляет настройки уведомлений о падениях и обновлениях рынка.
        
        Args:
            collapse_updates_time: Время для уведомлений о падениях
            collapse_updates: Флаг включения уведомлений о падениях
            market_updates_time: Время для уведомлений об обновлениях
            market_updates: Флаг включения уведомлений об обновлениях
            
        Returns:
            Dict[str, Any]: Обновленная конфигурация
            
        Raises:
            requests.exceptions.HTTPError: Если произошла ошибка HTTP при обновлении конфигурации
        """
        try:
            response = requests.put(
                f"{self.api_url}/config/collapse-updates/", 
                json={
                    "collapse_updates_time": collapse_updates_time,
                    "collapse_updates": collapse_updates,
                    "market_updates_time": market_updates_time,
                    "market_updates": market_updates
                }
            )
            response.raise_for_status()  # Вызовет HTTPError при статусе 4XX/5XX
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            print(f"Response content: {e.response.content}")
            raise
    
    # Instruments methods
    def get_all_instruments(self) -> List[Dict[str, Any]]:
        """
        Получает список всех инструментов.
        
        Returns:
            List[Dict[str, Any]]: Список инструментов
        """
        response = requests.get(f"{self.api_url}/trading/instruments/")
        return response.json()
    
    def get_instrument_by_ticker(self, ticker: str) -> Dict[str, Any]:
        """
        Получает инструмент по тикеру.
        
        Args:
            ticker: Тикер инструмента
            
        Returns:
            Dict[str, Any]: Информация об инструменте
            
        Raises:
            requests.exceptions.HTTPError: Если инструмент не найден (404) или другая ошибка HTTP
        """
        response = requests.get(f"{self.api_url}/trading/instruments/ticker/{ticker}")
        response.raise_for_status()  # Вызовет HTTPError при статусе 4XX/5XX
        return response.json()
    
    def get_instrument_by_figi(self, figi: str) -> Dict[str, Any]:
        """
        Получает инструмент по FIGI.
        
        Args:
            figi: FIGI инструмента
            
        Returns:
            Dict[str, Any]: Информация об инструменте
            
        Raises:
            requests.exceptions.HTTPError: Если инструмент не найден (404) или другая ошибка HTTP
        """
        response = requests.get(f"{self.api_url}/trading/instruments/figi/{figi}")
        response.raise_for_status()  # Вызовет HTTPError при статусе 4XX/5XX
        return response.json()
    
    def add_instrument(self, ticker: str, figi: str) -> Dict[str, Any]:
        """
        Добавляет новый инструмент.
        
        Args:
            ticker: Тикер инструмента
            figi: FIGI инструмента
            
        Returns:
            Dict[str, Any]: Добавленный инструмент
            
        Raises:
            requests.exceptions.HTTPError: Если произошла ошибка HTTP при добавлении инструмента
        """
        response = requests.post(
            f"{self.api_url}/trading/instruments/", 
            json={"ticker": ticker, "figi": figi}
        )
        response.raise_for_status()  # Вызовет HTTPError при статусе 4XX/5XX
        return response.json()
    
    def delete_instrument(self, ticker: str) -> Dict[str, Any]:
        """
        Удаляет инструмент по тикеру.
        
        Args:
            ticker: Тикер инструмента
            
        Returns:
            Dict[str, Any]: Удаленный инструмент
        """
        response = requests.delete(f"{self.api_url}/trading/instruments/ticker/{ticker}")
        return response.json()
    
    def delete_all_instruments(self) -> Dict[str, int]:
        """
        Удаляет все инструменты.
        
        Returns:
            Dict[str, int]: Количество удаленных инструментов
        """
        response = requests.delete(f"{self.api_url}/trading/instruments/all")
        return response.json()
    
    # Signal methods
    def get_signal_tpsl(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала Take Profit/Stop Loss.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        response = requests.get(f"{self.api_url}/signals/tpsl/")
        data = response.json()
        return data[0] if data else None
    
    def update_signal_tpsl(self, take_profit: float, stop_loss: float) -> Dict[str, Any]:
        """
        Обновляет настройки сигнала Take Profit/Stop Loss.
        
        Args:
            take_profit: Значение Take Profit
            stop_loss: Значение Stop Loss
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигнала
        """
        existing = self.get_signal_tpsl()
        if existing:
            response = requests.put(
                f"{self.api_url}/signals/tpsl/{existing['id']}", 
                json={"take_profit": take_profit, "stop_loss": stop_loss}
            )
        else:
            response = requests.post(
                f"{self.api_url}/signals/tpsl/", 
                json={"take_profit": take_profit, "stop_loss": stop_loss}
            )
        return response.json()
    
    def get_signal_rsi(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала RSI.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        response = requests.get(f"{self.api_url}/signals/rsi/")
        data = response.json()
        return data[0] if data else None
    
    def update_signal_rsi(self, period: float, high_level: float, low_level: float) -> Dict[str, Any]:
        """
        Обновляет настройки сигнала RSI.
        
        Args:
            period: Период RSI
            high_level: Верхний уровень
            low_level: Нижний уровень
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигнала
        """
        existing = self.get_signal_rsi()
        if existing:
            response = requests.put(
                f"{self.api_url}/signals/rsi/{existing['id']}", 
                json={"period": period, "hightLevel": high_level, "lowLevel": low_level}
            )
        else:
            response = requests.post(
                f"{self.api_url}/signals/rsi/", 
                json={"period": period, "hightLevel": high_level, "lowLevel": low_level}
            )
        return response.json()
    
    def get_signal_sma(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала SMA.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        response = requests.get(f"{self.api_url}/signals/sma/")
        data = response.json()
        return data[0] if data else None
    
    def update_signal_sma(self, fast_length: int, slow_length: int) -> Dict[str, Any]:
        """
        Обновляет настройки сигнала SMA.
        
        Args:
            fast_length: Быстрая длина
            slow_length: Медленная длина
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигнала
        """
        existing = self.get_signal_sma()
        if existing:
            response = requests.put(
                f"{self.api_url}/signals/sma/{existing['id']}", 
                json={"fastLength": fast_length, "slowLength": slow_length}
            )
        else:
            response = requests.post(
                f"{self.api_url}/signals/sma/", 
                json={"fastLength": fast_length, "slowLength": slow_length}
            )
        return response.json()
    
    def get_signal_ema(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала EMA.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        response = requests.get(f"{self.api_url}/signals/ema/")
        data = response.json()
        return data[0] if data else None
    
    def update_signal_ema(self, fast_length: int, slow_length: int) -> Dict[str, Any]:
        """
        Обновляет настройки сигнала EMA.
        
        Args:
            fast_length: Быстрая длина
            slow_length: Медленная длина
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигнала
        """
        existing = self.get_signal_ema()
        if existing:
            response = requests.put(
                f"{self.api_url}/signals/ema/{existing['id']}", 
                json={"fastLength": fast_length, "slowLength": slow_length}
            )
        else:
            response = requests.post(
                f"{self.api_url}/signals/ema/", 
                json={"fastLength": fast_length, "slowLength": slow_length}
            )
        return response.json()
    
    def get_signal_bollinger(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала Bollinger.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        response = requests.get(f"{self.api_url}/signals/bollinger/")
        data = response.json()
        return data[0] if data else None
    
    def update_signal_bollinger(self, period: int, deviation: float, type_ma: str) -> Dict[str, Any]:
        """
        Обновляет настройки сигнала Bollinger.
        
        Args:
            period: Период
            deviation: Отклонение
            type_ma: Тип скользящей средней
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигнала
        """
        existing = self.get_signal_bollinger()
        if existing:
            response = requests.put(
                f"{self.api_url}/signals/bollinger/{existing['id']}", 
                json={"period": period, "deviation": deviation, "type_ma": type_ma}
            )
        else:
            response = requests.post(
                f"{self.api_url}/signals/bollinger/", 
                json={"period": period, "deviation": deviation, "type_ma": type_ma}
            )
        return response.json()
    
    def get_signal_macd(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала MACD.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        response = requests.get(f"{self.api_url}/signals/macd/")
        data = response.json()
        return data[0] if data else None
    
    def update_signal_macd(self, fast_length: int, slow_length: int, signal_length: int) -> Dict[str, Any]:
        """
        Обновляет настройки сигнала MACD.
        
        Args:
            fast_length: Быстрая длина
            slow_length: Медленная длина
            signal_length: Длина сигнала
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигнала
        """
        existing = self.get_signal_macd()
        if existing:
            response = requests.put(
                f"{self.api_url}/signals/macd/{existing['id']}", 
                json={
                    "fastLength": fast_length, 
                    "slowLength": slow_length, 
                    "signalLength": signal_length
                }
            )
        else:
            response = requests.post(
                f"{self.api_url}/signals/macd/", 
                json={
                    "fastLength": fast_length, 
                    "slowLength": slow_length, 
                    "signalLength": signal_length
                }
            )
        return response.json()
    
    def get_signal_alligator(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала Alligator.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        response = requests.get(f"{self.api_url}/signals/alligator/")
        data = response.json()
        return data[0] if data else None
    
    def update_signal_alligator(
        self, 
        jaw_period: int, 
        jaw_shift: int, 
        teeth_period: int, 
        teeth_shift: int, 
        lips_period: int, 
        lips_shift: int
    ) -> Dict[str, Any]:
        """
        Обновляет настройки сигнала Alligator.
        
        Args:
            jaw_period: Период челюсти
            jaw_shift: Сдвиг челюсти
            teeth_period: Период зубов
            teeth_shift: Сдвиг зубов
            lips_period: Период губ
            lips_shift: Сдвиг губ
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигнала
        """
        existing = self.get_signal_alligator()
        if existing:
            response = requests.put(
                f"{self.api_url}/signals/alligator/{existing['id']}", 
                json={
                    "jaw_period": jaw_period, 
                    "jaw_shift": jaw_shift, 
                    "teeth_period": teeth_period, 
                    "teeth_shift": teeth_shift, 
                    "lips_period": lips_period, 
                    "lips_shift": lips_shift
                }
            )
        else:
            response = requests.post(
                f"{self.api_url}/signals/alligator/", 
                json={
                    "jaw_period": jaw_period, 
                    "jaw_shift": jaw_shift, 
                    "teeth_period": teeth_period, 
                    "teeth_shift": teeth_shift, 
                    "lips_period": lips_period, 
                    "lips_shift": lips_shift
                }
            )
        return response.json()
    
    def get_signal_gpt(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала GPT.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        response = requests.get(f"{self.api_url}/signals/gpt/")
        data = response.json()
        return data[0] if data else None
    
    def update_signal_gpt(self, text: str) -> Dict[str, Any]:
        """
        Обновляет настройки сигнала GPT.
        
        Args:
            text: Текст сигнала
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигнала
        """
        existing = self.get_signal_gpt()
        if existing:
            response = requests.put(
                f"{self.api_url}/signals/gpt/{existing['id']}", 
                json={"text": text}
            )
        else:
            response = requests.post(
                f"{self.api_url}/signals/gpt/", 
                json={"text": text}
            )
        return response.json()
    
    # Strategy methods
    def get_strategy_signals(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигналов стратегии.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигналов стратегии или None, если не найдены
        """
        response = requests.get(f"{self.api_url}/strategy/signals/")
        data = response.json()
        return data[0] if data else None
    
    def update_strategy_signals(
        self,
        tpls_trigger: bool,
        rsi_trigger: bool,
        sma_trigger: bool,
        alligator_trigger: bool,
        gpt_trigger: bool,
        lstm_trigger: bool,
        bollinger_trigger: bool,
        macd_trigger: bool,
        ema_trigger: bool,
        joint: bool
    ) -> Dict[str, Any]:
        """
        Обновляет настройки сигналов стратегии.
        
        Args:
            tpls_trigger: Флаг TPSL
            rsi_trigger: Флаг RSI
            sma_trigger: Флаг SMA
            alligator_trigger: Флаг Alligator
            gpt_trigger: Флаг GPT
            lstm_trigger: Флаг LSTM
            bollinger_trigger: Флаг Bollinger
            macd_trigger: Флаг MACD
            ema_trigger: Флаг EMA
            joint: Флаг объединения
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигналов стратегии
        """
        response = requests.put(
            f"{self.api_url}/strategy/update-signals/", 
            json={
                "tpls_trigger": tpls_trigger,
                "rsi_trigger": rsi_trigger,
                "sma_trigger": sma_trigger,
                "alligator_trigger": alligator_trigger,
                "gpt_trigger": gpt_trigger,
                "lstm_trigger": lstm_trigger,
                "bollinger_trigger": bollinger_trigger,
                "macd_trigger": macd_trigger,
                "ema_trigger": ema_trigger,
                "joint": joint
            }
        )
        return response.json()
    
    def get_strategy_settings(self) -> Optional[Dict[str, Any]]:
        """
        Получает общие настройки стратегии.
        
        Returns:
            Optional[Dict[str, Any]]: Общие настройки стратегии или None, если не найдены
        """
        response = requests.get(f"{self.api_url}/strategy/settings/")
        data = response.json()
        return data[0] if data else None
    
    def update_strategy_settings(
        self,
        time: str,
        auto_market: bool,
        quantity: int
    ) -> Dict[str, Any]:
        """
        Обновляет общие настройки стратегии.
        
        Args:
            time: Время стратегии
            auto_market: Флаг автоматического рынка
            quantity: Количество
            
        Returns:
            Dict[str, Any]: Обновленные общие настройки стратегии
        """
        response = requests.put(
            f"{self.api_url}/strategy/update-settings/", 
            json={
                "time": time,
                "auto_market": auto_market,
                "quantity": quantity
            }
        )
        return response.json()
    
    # Trading methods
    def get_margins(self) -> List[Dict[str, Any]]:
        """
        Получает список всех маржинальных позиций.
        
        Returns:
            List[Dict[str, Any]]: Список маржинальных позиций
        """
        response = requests.get(f"{self.api_url}/trading/margin/")
        return response.json()
    
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
        response = requests.post(f"{self.api_url}/trading/margin/", json=data)
        return response.json()
    
    def get_buys(self) -> List[Dict[str, Any]]:
        """
        Получает список всех покупок.
        
        Returns:
            List[Dict[str, Any]]: Список покупок
        """
        response = requests.get(f"{self.api_url}/trading/buy/")
        return response.json()
    
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
        response = requests.post(f"{self.api_url}/trading/buy/", json=data)
        return response.json()
    
    def get_orders(self) -> List[Dict[str, Any]]:
        """
        Получает список всех заказов.
        
        Returns:
            List[Dict[str, Any]]: Список заказов
        """
        response = requests.get(f"{self.api_url}/trading/orders/")
        return response.json()
    
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
        response = requests.post(
            f"{self.api_url}/trading/orders/", 
            json=data
        )
        return response.json()
    
    def delete_order(self, order_id: int) -> Dict[str, Any]:
        """
        Удаляет заказ по ID.
        
        Args:
            order_id: ID заказа
            
        Returns:
            Dict[str, Any]: Удаленный заказ
        """
        response = requests.delete(f"{self.api_url}/trading/orders/{order_id}")
        return response.json()
    
    def delete_order_by_order_id(self, order_id: str) -> Dict[str, Any]:
        """
        Удаляет заказ по order_id.
        
        Args:
            order_id: order_id заказа
            
        Returns:
            Dict[str, Any]: Удаленный заказ
        """
        response = requests.delete(f"{self.api_url}/trading/orders/order_id/{order_id}")
        return response.json()
