from typing import Dict, Any, Optional
from app.client.api.base_client import BaseApiClient


class StrategyApiClient(BaseApiClient):
    """
    Клиент API для работы со стратегиями.
    """
    
    def get_strategy_signals(self) -> Optional[Dict[str, Any]]:
        """
        Получает настройки сигналов стратегии.
        
        Returns:
            Optional[Dict[str, Any]]: Настройки сигналов стратегии или None, если не найдены
        """
        try:
            return self._get("strategy/signals/")
        except Exception:
            return None
    
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
            joint: Флаг объединения (будет обновлен в настройках стратегии)
            
        Returns:
            Dict[str, Any]: Обновленные настройки сигналов стратегии
        """
        # Обновляем сигналы стратегии
        data = {
            "tpls_trigger": tpls_trigger,
            "rsi_trigger": rsi_trigger,
            "sma_trigger": sma_trigger,
            "alligator_trigger": alligator_trigger,
            "gpt_trigger": gpt_trigger,
            "lstm_trigger": lstm_trigger,
            "bollinger_trigger": bollinger_trigger,
            "macd_trigger": macd_trigger,
            "ema_trigger": ema_trigger
        }
        signals_response = self._put("strategy/update-signals/", data)
        
        # Получаем текущие настройки стратегии
        settings = self.get_strategy_settings()
        
        if settings:
            # Обновляем настройку joint в настройках стратегии
            settings_data = {
                "time": settings.get("time", "60"),
                "auto_market": settings.get("auto_market", False),
                "quantity": settings.get("quantity", 1),
                "joint": joint,
                "sandbox_trigger": settings.get("sandbox_trigger", False)
            }
            self._put("strategy/update-settings/", settings_data)
        
        # Возвращаем обновленные сигналы стратегии
        signals_data = signals_response
        signals_data["joint"] = joint  # Добавляем joint в ответ для обратной совместимости
        return signals_data
    
    def get_strategy_settings(self) -> Optional[Dict[str, Any]]:
        """
        Получает общие настройки стратегии.
        
        Returns:
            Optional[Dict[str, Any]]: Общие настройки стратегии или None, если не найдены
        """
        try:
            return self._get("strategy/settings/")
        except Exception:
            return None
    
    def update_strategy_settings(
        self,
        time: str,
        auto_market: bool,
        quantity: int,
        joint: Optional[bool] = None,
        sandbox_trigger: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Обновляет общие настройки стратегии.
        
        Args:
            time: Время стратегии
            auto_market: Флаг автоматического рынка
            quantity: Количество
            joint: Флаг объединения (опционально)
            sandbox_trigger: Флаг песочницы (опционально)
            
        Returns:
            Dict[str, Any]: Обновленные общие настройки стратегии
        """
        # Получаем текущие настройки для полей, которые не переданы
        current_settings = self.get_strategy_settings() or {}
        
        # Формируем данные для обновления
        data = {
            "time": time,
            "auto_market": auto_market,
            "quantity": quantity,
            "joint": joint if joint is not None else current_settings.get("joint", False),
            "sandbox_trigger": sandbox_trigger if sandbox_trigger is not None else current_settings.get("sandbox_trigger", False)
        }
        
        return self._put("strategy/update-settings/", data)
