from pydantic import BaseSettings


class RabbitMQParams(BaseSettings):
    HOST: str
    USERNAME: str
    PASSWORD: str
    PORT: int = 5672
    QUEUES: str = "monitoring.bulk.malfunctions_ti"  # Перечисление через запятую без пробелов
    BATCHSIZE: int = 1000  #: Максимальный размер одной пачки сообщений для сохранения в БД
    PROCESS_INTERVAL_SEC: float = 0.1  #: Периодичность обработки накопленного объема собранных данных

    class Config:
        env_prefix = "BATCHMQ_MQ_"
