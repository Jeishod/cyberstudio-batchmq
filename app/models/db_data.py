from __future__ import annotations
import pickle
from pandas import Timestamp
from math import ceil
from typing import Generator
from datetime import datetime
from dataclasses import (
    dataclass,
    field,
)
from aio_pika.message import IncomingMessage


@dataclass
class DBData:
    """
    Модель для работы с базой данных
    - формирование из списка сообщений RabbitMQ
    - дробление на равные части
    - корректировка полей (например, преобразование pandas.Timestamp в datetime)
    """

    table_name: str
    objects: list[dict]
    errors_bodies: list[bytes] = field(default_factory=list)
    errors_objects: list[dict] = field(default_factory=list)

    @staticmethod
    def from_rabbit_messages(rabbit_messages: list[IncomingMessage]) -> DBData | None:
        """Формирование данных для БД из массива сообщений RabbitMQ"""
        if not rabbit_messages or not rabbit_messages[0].routing_key:
            return None
        # Подготовка данных
        first_message: IncomingMessage = rabbit_messages[0]
        table_name: str = first_message.routing_key.split(".")[-1]  # type: ignore
        values_list: list[dict] = list()
        errors_list: list[bytes] = list()
        for message in rabbit_messages:
            try:
                values_list.append(pickle.loads(message.body))
            except:  # noqa: E722 - ignore bare exception
                errors_list.append(message.body)
        return DBData(
            table_name=table_name,
            objects=values_list,
            errors_bodies=errors_list,
            errors_objects=[],
        )

    def shatter(self, parts_count: int = 2) -> Generator[DBData, None, None]:
        """
        Дробление одного объекта на parts_count объектов.
        Путем эксперимента выявлено, что количество частей не должно превышать значения 3.
            В противном случае разница количества объектов при дроблении (shatter) будет
            больше, чем 1 запись.
        !!! Отсутствуют проверки на отрицательное значение. Не использовать.
        """
        total_objects: int = len(self.objects)
        part_size: int = ceil(total_objects / parts_count)
        for part_number in range(parts_count):
            start_position: int = part_number * part_size
            end_position: int = (part_number + 1) * part_size
            part_of_db_data: DBData = DBData(
                table_name=self.table_name,
                objects=self.objects[start_position:end_position],
                errors_objects=[],
                errors_bodies=[],
            )
            yield part_of_db_data

    def prepared(self) -> DBData:
        """
        Корректировка полей datetime и удаление пустых полей
            (для замены на стороне БД дефолтными значениями)
        """
        dst_db_data: DBData = DBData(
            table_name=self.table_name,
            objects=[],
            errors_bodies=self.errors_bodies,
            errors_objects=self.errors_objects,
        )
        for src_obj in self.objects:
            dst_obj: dict = dict()
            for key, value in src_obj.items():
                if value is None:
                    continue
                if isinstance(value, Timestamp):
                    value = value.to_pydatetime()
                dst_obj[key] = value
            if "created_at" in src_obj:
                dst_obj["created_at"] = src_obj["created_at"] or datetime.now()
            dst_db_data.objects.append(dst_obj)
        return dst_db_data

    def __str__(self) -> str:
        return (
            "DBData("
            f"total objects: {len(self.objects)}, "
            f"errors_bodies(pickle): {len(self.errors_bodies)}, "
            f"errors_objects(db insert): {len(self.errors_objects)}"
            ")"
        )
