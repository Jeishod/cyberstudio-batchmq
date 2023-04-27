import asyncio
from urllib.parse import quote
from sqlalchemy import (
    MetaData,
    Table,
)
from sqlalchemy.exc import (
    DBAPIError,
    IntegrityError,
)
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
    engine,
    session,
)
from sqlalchemy.orm import declarative_base

from app.services.database.postgresql.settings import PostgreSQLParams
from app.services.services_base import ServiceBase
from app.services.database import Database
from app.models import DBData


class PostgreSQL(ServiceBase, Database):
    """
    Реализация работы с базой данных PostgreSQL
    - загрузка метаинформации таблиц из базы данных (_prepare_metadata)
    - подготовка объектов для групповой вставки (_prepare_objects)
    - выполнение групповой вставки (bulk_create)
    - при получении метаданных, они сохраняются в словаре, для кэширования (_fetched_tables)
    """

    _params: PostgreSQLParams
    _engine: engine.AsyncEngine
    _metadata: MetaData
    _session_maker: async_sessionmaker[session.AsyncSession]
    _fetched_tables: dict[str, Table]

    def __init__(self, connection_params: PostgreSQLParams) -> None:
        super().__init__()
        self._params = connection_params
        self._fetched_tables = dict()
        self._metadata = MetaData()
        self._base = declarative_base(metadata=self._metadata)

    @staticmethod
    def _make_url(connection_params: PostgreSQLParams) -> str:
        """Формирование строки подключения к БД"""
        username: str = quote(connection_params.USERNAME)
        password: str = quote(connection_params.PASSWORD)
        port: int = connection_params.PORT
        host: str = connection_params.HOST + (f":{port}" if port else "")
        database: str = connection_params.DATABASE
        return f"postgresql+asyncpg://{username}:{password}@{host}/{database}"

    async def connect(self) -> None:
        """Подключение к БД"""
        self._engine = create_async_engine(
            url=self._make_url(connection_params=self._params),
            pool_size=self._params.POOL_SIZE,
            echo_pool=self._params.ECHO_POOL,
            pool_pre_ping=True,
            connect_args={
                "server_settings": {
                    "statement_timeout": "5000",
                },
            },
        )
        self._session_maker = async_sessionmaker(bind=self._engine, expire_on_commit=False)
        await self._prepare_metadata()

    async def _prepare_metadata(self) -> None:
        """Загрузка текущего состояния таблиц"""
        async with self._engine.connect() as conn:
            await conn.run_sync(fn=self._metadata.reflect)

    def _get_table(self, table_name: str) -> Table:
        """
        Формирование объекта Table из метаданных
        - проверка на наличие объекта в кэше класса
        - сохранение сформированной таблицы в кэше
        """
        if table_name in self._fetched_tables:
            return self._fetched_tables[table_name]

        table: Table = Table(name=table_name, metadata=self._metadata)
        self._fetched_tables[table_name] = table
        return table

    async def bulk_create(self, db_data: DBData) -> DBData:
        """
        Групповое создание записей в БД.
        В процессе формируется список объектов, которые не удалось создать в БД.
            Этот список возвращается в исключении: BulkCreateError.db_data.objects
        """
        if not db_data.objects:
            return db_data

        sql_alchemy_table: Table = self._get_table(table_name=db_data.table_name)
        # Для избежания переполнения рекурсии при отвалившемся подключении к БД операция повторяется в цикле
        is_batch_processed: bool = False
        while not is_batch_processed:
            try:
                # Попытка вставки текущих данных
                async with self._session_maker() as _session:
                    await _session.execute(statement=sql_alchemy_table.insert(), params=db_data.objects)
                    await _session.commit()
            except OSError as os_error:
                # Отвал подключения к базе данных
                self.logger.exception(os_error)
                self.logger.error(f"Disconnected, retry in {self._params.CONNECTION_RETRY_PERIOD_SEC}")
                await asyncio.sleep(delay=self._params.CONNECTION_RETRY_PERIOD_SEC)
                continue  # Повторение обработки (цикл)
            except (IntegrityError, DBAPIError):
                # Ошибка при попытке вставить весь объем в одной операции
                if len(db_data.objects) == 1:
                    # Остался один объект, обрабатывать больше нечего
                    db_data.errors_objects = [db_data.objects[0]]
                else:
                    """
                    Разделить на две части принятый объем и обработать раздельно
                    Задача: при возникновении ошибки во время групповой вставки,
                            выполнить дробление наборов данных для корректной
                            записи в БД всех записей, которые не вызывают ошибок
                        * при наличии ошибок данные помещаются во внутреннюю переменную и
                          в конце обработки возвращаются
                    """
                    for part_of_db_data in db_data.shatter():
                        processed_db_data: DBData = await self.bulk_create(db_data=part_of_db_data)
                        if processed_db_data.errors_objects:
                            db_data.errors_objects += processed_db_data.errors_objects
            is_batch_processed = True
        return db_data
