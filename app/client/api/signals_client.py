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
        try:
            return self._get("signals/tpsl/")
        except Exception:
            return None
    
    def update_signal_tpsl(self, take_profit: float, stop_loss: float) -> Dict[str, Any]:
        """
        Обновляет настройки сигнала Take Profit/Stop Loss.
        
        Args:
            take_profit: Значение Take Profit
            stop_loss: Значение Stop Loss
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигнала
        """
        data = {"take_profit": take_profit, "stop_loss": stop_loss}
        existing = self.get_signal_tpsl()
        
        if existing:
            return self._put("signals/tpsl/", data)
        else:
            return self._post("signals/tpsl/", data)
    
    # RSI signals
    def get_signal_rsi(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала RSI.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        try:
            return self._get("signals/rsi/")
        except Exception:
            return None
    
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
        data = {"period": period, "hightLevel": high_level, "lowLevel": low_level}
        existing = self.get_signal_rsi()
        
        if existing:
            return self._put("signals/rsi/", data)
        else:
            return self._post("signals/rsi/", data)
    
    # SMA signals
    def get_signal_sma(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала SMA.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        try:
            return self._get("signals/sma/")
        except Exception:
            return None
    
    def update_signal_sma(self, fast_length: int, slow_length: int) -> Dict[str, Any]:
        """
        Обновляет настройки сигнала SMA.
        
        Args:
            fast_length: Быстрая длина
            slow_length: Медленная длина
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигнала
        """
        data = {"fastLength": fast_length, "slowLength": slow_length}
        existing = self.get_signal_sma()
        
        if existing:
            return self._put("signals/sma/", data)
        else:
            return self._post("signals/sma/", data)
    
    # EMA signals
    def get_signal_ema(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала EMA.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        try:
            return self._get("signals/ema/")
        except Exception:
            return None
    
    def update_signal_ema(self, fast_length: int, slow_length: int) -> Dict[str, Any]:
        """
        Обновляет настройки сигнала EMA.
        
        Args:
            fast_length: Быстрая длина
            slow_length: Медленная длина
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигнала
        """
        data = {"fastLength": fast_length, "slowLength": slow_length}
        existing = self.get_signal_ema()
        
        if existing:
            return self._put("signals/ema/", data)
        else:
            return self._post("signals/ema/", data)
    
    # Bollinger signals
    def get_signal_bollinger(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала Bollinger.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        try:
            return self._get("signals/bollinger/")
        except Exception:
            return None
    
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
        data = {"period": period, "deviation": deviation, "type_ma": type_ma}
        existing = self.get_signal_bollinger()
        
        if existing:
            return self._put("signals/bollinger/", data)
        else:
            return self._post("signals/bollinger/", data)
    
    # MACD signals
    def get_signal_macd(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала MACD.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        try:
            return self._get("signals/macd/")
        except Exception:
            return None
    
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
        data = {
            "fastLength": fast_length, 
            "slowLength": slow_length, 
            "signalLength": signal_length
        }
        existing = self.get_signal_macd()
        
        if existing:
            return self._put("signals/macd/", data)
        else:
            return self._post("signals/macd/", data)
    
    # Alligator signals
    def get_signal_alligator(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала Alligator.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        try:
            return self._get("signals/alligator/")
        except Exception:
            return None
    
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
        data = {
            "jaw_period": jaw_period, 
            "jaw_shift": jaw_shift, 
            "teeth_period": teeth_period, 
            "teeth_shift": teeth_shift, 
            "lips_period": lips_period, 
            "lips_shift": lips_shift
        }
        existing = self.get_signal_alligator()
        
        if existing:
            return self._put("signals/alligator/", data)
        else:
            return self._post("signals/alligator/", data)
    
    # GPT signals
    def get_signal_gpt(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигнала GPT.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигнала или None, если не найдены
        """
        try:
            return self._get("signals/gpt/")
        except Exception:
            return None
    
    def update_signal_gpt(self, text: str) -> Dict[str, Any]:
        """
        Обновляет настройки сигнала GPT.
        
        Args:
            text: Текст сигнала
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигнала
        """
        data = {"text": text}
        existing = self.get_signal_gpt()
        
        if existing:
            return self._put("signals/gpt/", data)
        else:
            return self._post("signals/gpt/", data)
