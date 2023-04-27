import asyncio
import logging
from asyncio import AbstractEventLoop
from contextlib import suppress
from typing import Generator

import aio_pika
import docker
import pytest
from aio_pika.abc import AbstractRobustConnection
from docker.models.containers import Container

from app.services.queue import RabbitMQParams


logger = logging.getLogger(__name__)


class DockerContainer(object):
    image: str
    name: str
    command: str | None
    environment: dict | None
    ports: dict | None
    remove: bool
    healthcheck: dict | None
    _container: Container | None

    def __init__(
        self,
        image: str,
        name: str,
        command: str | None = None,
        environment: dict | None = None,
        ports: dict | None = None,
        remove: bool = True,
        healthcheck: dict | None = None,
    ):
        self.client = docker.from_env()
        self.image = image
        self.name = name
        self.command = command
        self.environment = environment
        self.ports = ports
        self.remove = remove
        self.healthcheck = healthcheck
        self._container = None

    def __enter__(self):
        logger.info("Pulling image %s", self.image)
        self._container = self.client.containers.run(
            image=self.image,
            name=self.name,
            command=self.command,
            remove=self.remove,
            detach=True,
            environment=self.environment,
            ports=self.ports,
            healthcheck=self.healthcheck,
        )
        logger.info("Container started: %s", self._container.short_id)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def __del__(self):
        """
        Try to remove the container in all circumstances
        """
        if self._container is not None:
            with suppress(Exception):
                self.stop()

    def stop(self):
        self._container.remove(v=True, force=True)


@pytest.fixture(scope="session")
def event_loop() -> Generator[AbstractEventLoop, None, None]:
    """ Установка единой сессии для всех тестов """
    loop: AbstractEventLoop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True, scope="session")
def rabbitmq_params() -> RabbitMQParams:
    return RabbitMQParams(
        HOST="localhost",
        USERNAME="test",
        PASSWORD="test",
    )


@pytest.fixture(autouse=True, scope="session")
async def rabbitmq_container(rabbitmq_params: RabbitMQParams) -> DockerContainer:
    """Подготовка и поднятие контейнера RabbitMQ"""
    params: RabbitMQParams = rabbitmq_params
    environment = {
        "RABBITMQ_DEFAULT_USER": params.USERNAME,
        "RABBITMQ_DEFAULT_PASS": params.PASSWORD,
    }
    with DockerContainer(
        image="rabbitmq:3.11.2-management",
        name="test-rabbitmq-container",
        ports={"5672/tcp": 5672},
        environment=environment,
        healthcheck={
            "test": "rabbitmq-diagnostics -q ping",
            "interval": 100,
            "timeout": 500,
            "retries": 10,
        },
    ) as container:
        while container.status != "healthy":
            await asyncio.sleep(1)

        yield container


@pytest.fixture()
async def sample_queues() -> list[str]:
    QUEUE_NAME_PREFIX: str = "monitoring.bulk."
    TABLES_COUNT: int = 5
    TABLE_NAME_PREFIX: str = "table"

    example_tables: list[str] = [f"{TABLE_NAME_PREFIX}{i}" for i in range(TABLES_COUNT)]
    example_queues: list[str] = [f"{QUEUE_NAME_PREFIX}{table_name}" for table_name in example_tables]
    return example_queues


@pytest.fixture()
async def prepare_example_queues(
    rabbitmq_container: DockerContainer,
    sample_queues: list[str],
    rabbitmq_params: RabbitMQParams,
) -> None:
    """
    Подготовка таблиц для прогонки тестов
    * имена созданных очередей сохраняются во внутреннем списке (self.queues)
    """
    connection: AbstractRobustConnection = await aio_pika.connect_robust(
        host=rabbitmq_params.HOST,
        port=rabbitmq_params.PORT,
        login=rabbitmq_params.USERNAME,
        password=rabbitmq_params.PASSWORD,
    )
    channel = await connection.channel()
    for queue_name in sample_queues:
        await channel.declare_queue(name=queue_name)
        yield
