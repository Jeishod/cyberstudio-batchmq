from abc import abstractmethod
from typing import (
    Protocol,
    AsyncGenerator,
)

from app.models import DBData


class BatchConsumer(Protocol):
    """Интерфейс источника данных (брокер сообщений)"""

    @abstractmethod
    async def iterator(self, queue_name: str) -> AsyncGenerator[DBData, None]:
        """
        Сбор данных из очереди с периодическим возвращением
        накопленного объема сообщений
        """

    @abstractmethod
    async def connect(self) -> None:
        """Установка подключения к БД"""
