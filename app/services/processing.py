import asyncio

from app.models import DBData
from app.services import (
    Services,
    Database,
    BatchConsumer,
    Collector,
)
from app.services.services_base import ServiceBase


class Processing(ServiceBase):
    _queues: str
    _database: Database = Services.database()
    _batch_consumer: BatchConsumer = Services.batch_consumer()
    _collector: Collector = Services.collector()

    def __init__(self, queues: str) -> None:
        super().__init__()
        self._queues = queues

    async def start(self) -> None:
        queues: list[str] = self._queues.split(",")
        for queue_name in queues:
            asyncio.create_task(self.process_queue(queue_name=queue_name))

    async def process_queue(self, queue_name: str) -> None:
        """Запуск процесса прослушивания очередей на предмет новых данных для записи в БД"""

        async for db_data in self._batch_consumer.iterator(queue_name=queue_name):  # noqa  # TODO: чекнуть тайпинги
            prepared_db_data: DBData = db_data.prepared()
            processed_db_data: DBData = await self._database.bulk_create(db_data=prepared_db_data)
            self._collector.append_db_data(db_data=processed_db_data)
            if processed_db_data.errors_bodies:
                """Обработка данных, которые не удалось десериализовать (unpickle)"""
                # TODO: имплементировать
            if processed_db_data.errors_objects:
                """Обработка данных, которые не удалось сохранить в базе данных"""
                # TODO: имплементировать
            self.logger.info(processed_db_data)
