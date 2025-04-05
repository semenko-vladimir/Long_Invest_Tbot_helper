import requests
from typing import Dict, Any, Optional


class BaseApiClient:
    """
    Базовый класс для клиентов API.
    Предоставляет общую функциональность для всех клиентов API.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Инициализирует базовый клиент API.
        
        Args:
            base_url: Базовый URL API-сервера
        """
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
    
    def _get(self, endpoint: str) -> Any:
        """
        Выполняет GET-запрос к указанному эндпоинту.
        
        Args:
            endpoint: Эндпоинт API
            
        Returns:
            Any: Результат запроса в формате JSON
            
        Raises:
            requests.exceptions.HTTPError: Если произошла ошибка HTTP
        """
        response = requests.get(f"{self.api_url}/{endpoint}")
        response.raise_for_status()
        return response.json()
    
    def _post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Any:
        """
        Выполняет POST-запрос к указанному эндпоинту.
        
        Args:
            endpoint: Эндпоинт API
            data: Данные для отправки (опционально)
            
        Returns:
            Any: Результат запроса в формате JSON
            
        Raises:
            requests.exceptions.HTTPError: Если произошла ошибка HTTP
        """
        response = requests.post(f"{self.api_url}/{endpoint}", json=data)
        response.raise_for_status()
        return response.json()
    
    def _put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Any:
        """
        Выполняет PUT-запрос к указанному эндпоинту.
        
        Args:
            endpoint: Эндпоинт API
            data: Данные для отправки (опционально)
            
        Returns:
            Any: Результат запроса в формате JSON
            
        Raises:
            requests.exceptions.HTTPError: Если произошла ошибка HTTP
        """
        response = requests.put(f"{self.api_url}/{endpoint}", json=data)
        response.raise_for_status()
        return response.json()
    
    def _delete(self, endpoint: str) -> Any:
        """
        Выполняет DELETE-запрос к указанному эндпоинту.
        
        Args:
            endpoint: Эндпоинт API
            
        Returns:
            Any: Результат запроса в формате JSON
            
        Raises:
            requests.exceptions.HTTPError: Если произошла ошибка HTTP
        """
        response = requests.delete(f"{self.api_url}/{endpoint}")
        response.raise_for_status()
        return response.json()
