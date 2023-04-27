import time
import asyncio
import aio_pika
from typing import AsyncGenerator
from asyncio.tasks import Task

from aio_pika.abc import AbstractQueue, AbstractChannel, AbstractRobustConnection

from app.models import DBData
from app.services.queue import BatchConsumer
from app.services.queue.rabbitmq.settings import RabbitMQParams
from app.services.services_base import ServiceBase


class RabbitBatchConsumer(ServiceBase, BatchConsumer):
    """
    Класс для подготовки "пачек" сообщений из RabbitMQ.
    Использовать, как итератор:
        ```
            rabbit_batch_consumer: RabbitConnectionParams = RabbitBatchConsumer(...)
            await rabbit_batch_consumer.connect()
            async for db_data in services.batch_consumer:
                db_data  # "Пачка сообщений"
        ```
    - подключение к заданным в параметрах очередям
    - сбор сообщений во внутреннюю очередь
    - периодическое (PROCESS_INTERVAL_SEC или max_buffer_size) возвращение накопленных данных
        - если данных нет, то ничего не происходит
    """

    _params: RabbitMQParams
    _connection: AbstractRobustConnection

    def __init__(
        self,
        params: RabbitMQParams,
    ) -> None:
        super().__init__()
        self._params = params

    async def connect(self) -> None:
        """Настройка подключения к Rabbit"""
        self._connection = await aio_pika.connect_robust(
            host=self._params.HOST,
            port=self._params.PORT,
            login=self._params.USERNAME,
            password=self._params.PASSWORD,
        )

    async def _make_queue_connection(self, queue_name: str) -> AbstractQueue:
        """Установка подключения для одной очереди сообщений"""
        rabbit_channel: AbstractChannel = await self._connection.channel()
        await rabbit_channel.set_qos(prefetch_count=self._params.BATCHSIZE)
        queue: AbstractQueue = await rabbit_channel.get_queue(name=queue_name)
        return queue

    async def iterator(self, queue_name: str) -> AsyncGenerator[DBData, None]:  # type: ignore  # TODO: фикс тайпингов
        """Основной процесс обработки сообщений из очередей"""
        buffer: list[aio_pika.IncomingMessage] = list()
        inner_queue: asyncio.Queue = asyncio.Queue()
        # Запуск процедуры наполнения внутренней очереди
        queue: AbstractQueue = await self._make_queue_connection(queue_name=queue_name)
        task: Task = asyncio.create_task(queue.consume(inner_queue.put))
        # Инициализация стартовых значений
        process_interval_left_sec: float = self._params.PROCESS_INTERVAL_SEC
        start_time: float
        # Периодическая обработка содержимого
        try:
            while True:
                start_time = time.monotonic()
                try:
                    mess = await asyncio.wait_for(inner_queue.get(), process_interval_left_sec)
                    buffer.append(mess)
                    # Искусственное формирование исключения, при достижении лимита количества
                    if len(buffer) >= self._params.BATCHSIZE:
                        raise asyncio.TimeoutError
                    # Уменьшить время накопления буфера
                    process_interval_left_sec -= time.monotonic() - start_time
                    yield 1
                except asyncio.TimeoutError:
                    # Возврат "пачки", при наличии собранных данных
                    if buffer:
                        data: DBData | None = DBData.from_rabbit_messages(buffer)
                        if data:
                            yield data
                        # Подтверждение статуса обработки сообщений в RabbitMQ
                        await buffer[-1].ack(multiple=True)
                        buffer.clear()
                    # Освежить таймауты для формирования буфера
                    process_interval_left_sec = self._params.PROCESS_INTERVAL_SEC
        finally:
            # Останов процедуры наполнения внутренних очередей
            task.cancel()
