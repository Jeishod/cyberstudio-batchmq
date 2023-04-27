from dependency_injector import containers, providers

from app.services.database import (
    Database,
    PostgreSQL,
)
from app.services.queue import (
    BatchConsumer,
    RabbitBatchConsumer,
)
from app.services.metrics import Collector
from app.settings import Settings


class Services(containers.DeclarativeContainer):
    """Оркестратор сервисов"""

    wiring_config: containers.WiringConfiguration = containers.WiringConfiguration(modules=["app.router"])
    config: Settings = providers.Configuration(pydantic_settings=[Settings()])

    batch_consumer: providers.Singleton[BatchConsumer] = providers.Singleton(
        RabbitBatchConsumer,
        params=config.rabbitmq,
    )

    collector: providers.Singleton[Collector] = providers.Singleton(Collector)

    pg_echo_pool = "debug" if config.postgresql.ECHO_POOL else False
    database: providers.Singleton[Database] = providers.Singleton(
        PostgreSQL,
        params=config.postgresql,
    )

    async def initialize(self) -> None:
        """Выполнение инициализирующих операций. В том числе установка подключений"""
        self.collector().initialize()
        await self.database().connect()
        await self.batch_consumer().connect()
