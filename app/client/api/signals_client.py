from typing import Dict, Any, Optional
from app.client.api.base_client import BaseApiClient


class SignalsApiClient(BaseApiClient):
    """
    Клиент API для работы с сигналами.
    """
    
    # TPSL signals
    def get_signal_tpsl(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала Take Profit/Stop Loss.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        data = self._get("signals/tpsl/")
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
        data = {"take_profit": take_profit, "stop_loss": stop_loss}
        
        if existing:
            return self._put(f"signals/tpsl/{existing['id']}", data)
        else:
            return self._post("signals/tpsl/", data)
    
    # RSI signals
    def get_signal_rsi(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала RSI.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        data = self._get("signals/rsi/")
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
        data = {"period": period, "hightLevel": high_level, "lowLevel": low_level}
        
        if existing:
            return self._put(f"signals/rsi/{existing['id']}", data)
        else:
            return self._post("signals/rsi/", data)
    
    # SMA signals
    def get_signal_sma(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала SMA.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        data = self._get("signals/sma/")
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
        data = {"fastLength": fast_length, "slowLength": slow_length}
        
        if existing:
            return self._put(f"signals/sma/{existing['id']}", data)
        else:
            return self._post("signals/sma/", data)
    
    # EMA signals
    def get_signal_ema(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала EMA.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        data = self._get("signals/ema/")
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
        data = {"fastLength": fast_length, "slowLength": slow_length}
        
        if existing:
            return self._put(f"signals/ema/{existing['id']}", data)
        else:
            return self._post("signals/ema/", data)
    
    # Bollinger signals
    def get_signal_bollinger(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала Bollinger.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        data = self._get("signals/bollinger/")
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
        data = {"period": period, "deviation": deviation, "type_ma": type_ma}
        
        if existing:
            return self._put(f"signals/bollinger/{existing['id']}", data)
        else:
            return self._post("signals/bollinger/", data)
    
    # MACD signals
    def get_signal_macd(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала MACD.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        data = self._get("signals/macd/")
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
        data = {
            "fastLength": fast_length, 
            "slowLength": slow_length, 
            "signalLength": signal_length
        }
        
        if existing:
            return self._put(f"signals/macd/{existing['id']}", data)
        else:
            return self._post("signals/macd/", data)
    
    # Alligator signals
    def get_signal_alligator(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала Alligator.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        data = self._get("signals/alligator/")
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
        data = {
            "jaw_period": jaw_period, 
            "jaw_shift": jaw_shift, 
            "teeth_period": teeth_period, 
            "teeth_shift": teeth_shift, 
            "lips_period": lips_period, 
            "lips_shift": lips_shift
        }
        
        if existing:
            return self._put(f"signals/alligator/{existing['id']}", data)
        else:
            return self._post("signals/alligator/", data)
    
    # GPT signals
    def get_signal_gpt(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала GPT.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        data = self._get("signals/gpt/")
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
        data = {"text": text}
        
        if existing:
            return self._put(f"signals/gpt/{existing['id']}", data)
        else:
            return self._post("signals/gpt/", data)
