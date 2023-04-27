from pydantic import BaseSettings

from app.services.database import PostgreSQLParams
from app.services.queue import RabbitMQParams


class Settings(BaseSettings):
    DEBUG: int = 0

    APP_TITLE: str = "BatchMQ"
    APP_DESCRIPTION: str = "Групповая запись данных из очереди в базу данных"

    LOG_FORMAT: str = "%(asctime)s [%(name)s:%(lineno)s] [%(levelname)s]: %(message)s"

    rabbitmq: RabbitMQParams = RabbitMQParams()
    postgresql: PostgreSQLParams = PostgreSQLParams()

    class Config:
        env_file = ".env"
        env_prefix = "BATCHMQ_"
