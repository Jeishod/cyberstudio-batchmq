from typing import Literal

from pydantic import BaseSettings


class PostgreSQLParams(BaseSettings):
    HOST: str
    PORT: int
    USERNAME: str
    PASSWORD: str
    DATABASE: str
    ECHO_POOL: Literal["debug"] | bool = False  # "DEBUG"\False
    POOL_SIZE: int = 10
    CONNECTION_RETRY_PERIOD_SEC: float = 5.0

    class Config:
        env_prefix = "BATCHMQ_PG_"
