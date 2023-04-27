import logging

from fastapi import FastAPI

from app.router import router_system
from app.services import Services


class Application(FastAPI):
    logger: logging.Logger
    services: Services

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.services = Services()

        super().__init__(
            title=self.services.config.APP_TITLE,
            description=self.services.config.APP_DESCRIPTION,
        )
        self.add_event_handler("startup", self.mount_routers)
        self.add_event_handler("startup", self.init_services)

    def mount_routers(self) -> None:
        self.include_router(router_system)

    async def init_services(self) -> None:
        await self.services.initialize()


app = Application()
