import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from reminder_common.config import Settings, get_settings
from reminder_common.logging import configure_logging


def create_service_app(service_name: str) -> FastAPI:
    settings = get_settings().model_copy(update={"service_name": service_name})
    configure_logging(service_name, settings.log_level)
    logger = logging.LoggerAdapter(logging.getLogger(service_name), {"service": service_name})

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.db = create_async_engine(settings.database_url, pool_pre_ping=True)
        app.state.session_factory = async_sessionmaker(app.state.db, expire_on_commit=False)
        app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
        logger.info("service started")
        yield
        await app.state.redis.aclose()
        await app.state.db.dispose()
        logger.info("service stopped")

    app = FastAPI(
        title=f"Reminder Platform {service_name}",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Any]]
    ) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "unhandled request error", extra={"request_id": request_id, "user_id": None}
            )
            raise
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request completed",
            extra={
                "request_id": request_id,
                "user_id": None,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return response

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        return {"status": "ok", "service": service_name}

    @app.get("/health/ready", tags=["health"])
    async def readiness(request: Request) -> JSONResponse:
        checks = await _dependency_checks(
            request.app.state.db,
            request.app.state.redis,
            request.app.state.settings,
        )
        healthy = all(value == "ok" for value in checks.values())
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={"status": "ok" if healthy else "unavailable", "checks": checks},
        )

    return app


async def _dependency_checks(
    engine: AsyncEngine, redis: Redis, settings: Settings
) -> dict[str, str]:
    async def database_check() -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def redis_check() -> None:
        await redis.ping()

    checks: dict[str, str] = {}
    results = await asyncio.gather(
        asyncio.wait_for(database_check(), settings.readiness_timeout_seconds),
        asyncio.wait_for(redis_check(), settings.readiness_timeout_seconds),
        return_exceptions=True,
    )
    checks["postgres"] = "ok" if not isinstance(results[0], BaseException) else "error"
    checks["redis"] = "ok" if not isinstance(results[1], BaseException) else "error"
    return checks
