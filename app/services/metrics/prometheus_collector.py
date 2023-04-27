import prometheus_client

from app.models import (
    DBData,
    CollectorObjectType,
)


class Collector:
    """Сбор статистики"""

    db_objects: prometheus_client.Counter  # Метрики по создаваемым в БД объектам

    def initialize(self):
        """
        Создание счетчиков
            - статистика во времени increase(processed_objects_total[5s])
            labels для type: models.CollectorObjectType
        """
        self.db_objects = prometheus_client.Counter(
            "processed_objects", "Результаты обработки сообщений", labelnames=["type"]
        )

    def append_db_data(self, db_data: DBData) -> None:
        """Добавление метрик для обработанных данных DBData"""
        self.db_objects.labels(CollectorObjectType.TOTAL).inc(len(db_data.objects))
        self.db_objects.labels(CollectorObjectType.UNPICKLING_ERRORS).inc(len(db_data.errors_bodies))
        self.db_objects.labels(CollectorObjectType.INSERT_ERROR).inc(len(db_data.errors_objects))

    def generate(self) -> bytes:
        """Проброс генерации результатов статистики"""
        return prometheus_client.generate_latest()
