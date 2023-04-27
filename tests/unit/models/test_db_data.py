import pickle
import statistics
import pandas
from datetime import (
    datetime,
    timedelta,
)
from aio_pika.message import IncomingMessage
from aiormq.abc import DeliveredMessage
from pamqp.header import ContentHeader
from pamqp.commands import Basic

from app.models import DBData


class TestDBData:
    """Формирование объектов, дробление"""

    def _make_incoming_message(self, body: bytes) -> IncomingMessage:
        """Подделка сообщения RabbitMQ"""
        deliver: Basic.Deliver = Basic.Deliver(
            consumer_tag=None,
            delivery_tag=None,
            redelivered=False,
            exchange="",
            routing_key="custom_route",
        )
        message: DeliveredMessage = DeliveredMessage(
            delivery=deliver,
            header=ContentHeader(),
            body=body,
            channel=None,  # type: ignore
        )
        return IncomingMessage(message=message)

    def _make_db_data_from_objects(self, objects: list[dict]) -> DBData:
        """Создание объекта DBData из списка словарей"""
        db_data: DBData = DBData(
            table_name="",
            objects=objects,
            errors_bodies=[],
            errors_objects=[],
        )
        return db_data

    def test_from_rabbit_messages_correct_parse(self) -> None:
        """
        Формирование объекта DBData из "пачки" сообщений RabbitMQ
        Все объекты валидные, удалось распарсить
        """
        messages: list[IncomingMessage] = []
        valid_count: int = 100
        for _ in range(valid_count):
            src_body: dict = {"any_field": "any_value"}
            messages.append(self._make_incoming_message(body=pickle.dumps(src_body)))
        db_data: DBData | None = DBData.from_rabbit_messages(rabbit_messages=messages)
        assert db_data is not None
        assert len(db_data.objects) == valid_count

    def test_from_rabbit_messages_invalid_parse(self) -> None:
        """
        Формирование объекта DBData из "пачки" сообщений RabbitMQ
        Все объекты неправильные, не удалось распарсить
        """
        messages: list[IncomingMessage] = []
        invalid_count: int = 100
        for _ in range(invalid_count):
            messages.append(self._make_incoming_message(body="str value".encode()))
        db_data: DBData | None = DBData.from_rabbit_messages(rabbit_messages=messages)
        assert db_data is not None
        assert not db_data.objects
        assert len(db_data.errors_bodies) == invalid_count

    def test_from_rabbit_messages_partially_valid(self) -> None:
        """
        Формирование объекта DBData из "пачки" сообщений RabbitMQ
        Часть объектов удалось распарсить, другая сложена в ошибки
        """
        messages: list[IncomingMessage] = []
        valid_count: int = 33
        for _ in range(valid_count):
            src_body: dict = {"any_field": "any_value"}
            messages.append(self._make_incoming_message(body=pickle.dumps(src_body)))
        invalid_count: int = 100
        for _ in range(invalid_count):
            messages.append(self._make_incoming_message(body="str value".encode()))
        db_data: DBData | None = DBData.from_rabbit_messages(rabbit_messages=messages)
        assert db_data is not None
        assert len(db_data.objects) == valid_count
        assert len(db_data.errors_bodies) == invalid_count

    def test_shatter_counts(self) -> None:
        """
        Дробление на равные (+-1) части.
        Путём эксперимента выявлено, что текущий алгоритм может коррекнто делить на равные части,
            при количестве этих самых частей не превышающем 3. Далее "разброс" от среднего может
            увеличиваться.
        Проверка на отрицательное значение не рассматривается, parts_count задается вручную,
            добавлять такую проверку в коде и в тестах избыточно.
        """
        object_body: dict = {"key": "value"}
        for objects_count in range(1000):
            objects: list[dict] = [object_body for _ in range(objects_count)]
            for parts_count in range(1, 4):  # 1, 2, 3
                db_data: DBData = self._make_db_data_from_objects(objects=objects)
                db_data_parts: list[DBData] = list(db_data.shatter(parts_count=parts_count))
                assert len(db_data_parts) == parts_count
                sizes: list[int] = [len(db_data.objects) for db_data in db_data_parts]
                # Проверить, что размер объектов сформированных частей не отличается больше, чем на единицу
                for db_data_size in sizes:
                    assert (int(statistics.mean(sizes)) - db_data_size) <= 1, f"{objects_count=}, {parts_count=}"

    def test_prepared_clear_empty(self) -> None:
        """Очистка значений от пустых полей"""
        object_with_empty_value: dict = {
            "key_with_filled_value": "filled_value",
            "key_with_empty_value": None,
        }
        db_data: DBData = self._make_db_data_from_objects(objects=[object_with_empty_value])
        prepared_db_data: DBData = db_data.prepared()
        first_object: dict = prepared_db_data.objects[0]
        assert "key_with_empty_value" not in first_object, "Fields are not removed"
        assert "key_with_filled_value" in first_object, "Removed correct field"

    def test_prepared_fill_empty_created_at(self) -> None:
        """При наличии пустого created_at заполнение текущим временем"""
        object_with_empty_created_at: dict = {
            "key_with_filled_value": "filled_value",
            "created_at": None,
        }
        db_data: DBData = self._make_db_data_from_objects(objects=[object_with_empty_created_at])
        prepared_db_data: DBData = db_data.prepared()
        first_object: dict = prepared_db_data.objects[0]
        assert "key_with_filled_value" in first_object, "Removed correct field"
        assert "created_at" in first_object, "Removed empty created_at field"
        assert isinstance(first_object["created_at"], datetime)
        assert first_object["created_at"] - datetime.now() < timedelta(seconds=1)

    def test_prepared_correct_pandas_timestamp(self) -> None:
        """Преобразование pandas.Timestamp в datetime"""
        object_with_pandas_timestamp: dict = {
            "key_with_filled_value": "filled_value",
            "key_with_pandas_timestamp": pandas.Timestamp(datetime.now()),
        }
        db_data: DBData = self._make_db_data_from_objects(objects=[object_with_pandas_timestamp])
        prepared_db_data: DBData = db_data.prepared()
        first_object: dict = prepared_db_data.objects[0]
        assert "key_with_filled_value" in first_object, "Removed correct field"
        assert "key_with_pandas_timestamp" in first_object, "Removed timestamp field"
        assert isinstance(first_object["key_with_pandas_timestamp"], datetime)
