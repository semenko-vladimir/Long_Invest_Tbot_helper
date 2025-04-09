from typing import List, Dict, Any
import requests
from app.client.api.base_client import BaseApiClient


class InstrumentsApiClient(BaseApiClient):
    """
    Клиент API для работы с инструментами.
    """
    
    def get_all_instruments(self) -> List[Dict[str, Any]]:
        """
        Получает список всех инструментов.
        
        Returns:
            List[Dict[str, Any]]: Список инструментов
        """
        return self._get("instruments/")
    
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
        try:
            return self._get(f"instruments/ticker/{ticker}")
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            raise
    
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
        try:
            return self._get(f"instruments/figi/{figi}")
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            raise
    
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
        try:
            data = {"ticker": ticker, "figi": figi}
            return self._post("instruments/", data)
        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            raise
    
    def delete_instrument(self, ticker: str) -> Dict[str, Any]:
        """
        Удаляет инструмент по тикеру.
        
        Args:
            ticker: Тикер инструмента
            
        Returns:
            Dict[str, Any]: Удаленный инструмент
        """
        return self._delete(f"instruments/ticker/{ticker}")
    
    def delete_all_instruments(self) -> Dict[str, int]:
        """
        Удаляет все инструменты.
        
        Returns:
            Dict[str, int]: Количество удаленных инструментов
        """
        return self._delete("instruments/all")
