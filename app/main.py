from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.database import Base, engine
from app.routers import erg_tests, health, import_csv, projections, stats, workouts


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app import models

    Base.metadata.create_all(engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Rowing Analytics", lifespan=lifespan)
    for router in (
        health.router,
        workouts.router,
        erg_tests.router,
        projections.router,
        stats.router,
        import_csv.router,
    ):
        app.include_router(router)
    return app


app = create_app()
