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
            Dict[str, Any]: Конфигурация
            
        Raises:
            Exception: Если произошла ошибка при получении конфигурации
        """
        return self._get("config/")
    
    def create_config(self, 
                     collapse_updates_time: str, 
                     collapse_updates: bool, 
                     market_updates_time: str, 
                     market_updates: bool) -> Dict[str, Any]:
        """
        Создает новую конфигурацию.
        
        Args:
            collapse_updates_time: Время для уведомлений о падениях
            collapse_updates: Флаг включения уведомлений о падениях
            market_updates_time: Время для уведомлений об обновлениях
            market_updates: Флаг включения уведомлений об обновлениях
            
        Returns:
            Dict[str, Any]: Созданная конфигурация
            
        Raises:
            requests.exceptions.HTTPError: Если произошла ошибка HTTP при создании конфигурации
        """
        data = {
            "collapse_updates_time": collapse_updates_time,
            "collapse_updates": collapse_updates,
            "market_updates_time": market_updates_time,
            "market_updates": market_updates
        }
        return self._post("config/", data)
    
    def update_config(self, 
                     collapse_updates_time: str, 
                     collapse_updates: bool, 
                     market_updates_time: str, 
                     market_updates: bool) -> Dict[str, Any]:
        """
        Обновляет настройки уведомлений.
        
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
            return self._put("config/", data)
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            print(f"Response content: {e.response.content}")
            raise
    
    def delete_config(self) -> Dict[str, Any]:
        """
        Удаляет конфигурацию.
        
        Returns:
            Dict[str, Any]: Удаленная конфигурация
            
        Raises:
            requests.exceptions.HTTPError: Если произошла ошибка HTTP при удалении конфигурации
        """
        return self._delete("config/")
    
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
