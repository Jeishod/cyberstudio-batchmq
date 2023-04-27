from abc import abstractmethod
from typing import Protocol

from app.models import DBData


class Database(Protocol):
    """Интерфейс целевого хранилища данных (БД)"""

    @abstractmethod
    async def bulk_create(self, db_data: DBData) -> DBData:
        """Групповое создание записей в БД"""

    @abstractmethod
    async def connect(self) -> None:
        """Подключение к БД"""
