from enum import StrEnum


class CollectorObjectType(StrEnum):
    TOTAL = "total"
    UNPICKLING_ERRORS = "error_bodies"
    INSERT_ERROR = "error_objects"
