from typing import Dict, Any
import requests
from app.client.api.base_client import BaseApiClient


class ConfigApiClient(BaseApiClient):
    """
    Клиент API для работы с конфигурацией.
    """
    
    def get_config(self) -> Dict[str, Any]:
        """
        Получает общую конфигурацию.
        
        Returns:
            Dict[str, Any]: Конфигурация или значения по умолчанию
        """
        try:
            data = self._get("config/")
            if data and len(data) > 0:
                config = data[0]
                
                # Получаем sandbox_trigger из настроек стратегии
                try:
                    sandbox_response = self._get("config/sandbox-trigger/")
                    config["sandbox_trigger"] = sandbox_response
                except:
                    config["sandbox_trigger"] = False
                
                return config
            else:
                # Если конфигурация не найдена, создаем новую
                config = {
                    "collapse_updates": False,
                    "collapse_updates_time": "60",
                    "market_updates": False,
                    "market_updates_time": "60"
                }
                
                # Сохраняем конфигурацию в базе данных
                config_data = self._post("config/", config)
                
                # Добавляем sandbox_trigger (по умолчанию False)
                config_data["sandbox_trigger"] = False
                
                return config_data
        except Exception as e:
            # В случае ошибки возвращаем значения по умолчанию
            return {
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
        return self._get("config/sandbox-trigger/")
    
    def set_sandbox_trigger(self, value: bool) -> Dict[str, Any]:
        """
        Устанавливает значение флага sandbox_trigger.
        
        Args:
            value: Новое значение флага
            
        Returns:
            Dict[str, Any]: Обновленная конфигурация
        """
        return self._put("config/sandbox-trigger/", {"value": value})
    
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
            data = {
                "collapse_updates_time": collapse_updates_time,
                "collapse_updates": collapse_updates,
                "market_updates_time": market_updates_time,
                "market_updates": market_updates
            }
            return self._put("config/collapse-updates/", data)
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            print(f"Response content: {e.response.content}")
            raise
