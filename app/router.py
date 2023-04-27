from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Response, status, Depends
from fastapi.responses import JSONResponse

from app.services import Collector, Services


router_system = APIRouter()


@router_system.get(path="/")
async def healthcheck() -> JSONResponse:
    """Состояние сервиса"""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ok",
        },
    )


@router_system.get(path="/metrics", response_model=bytes)
@inject
def metrics(collector: Collector = Depends(Provide[Services.collector])) -> Response:
    """Метрики для Prometheus"""
    return Response(collector.generate())
