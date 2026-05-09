from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from redis.asyncio import Redis
from sqlalchemy import text

from agent.scanner import start_scheduler, stop_scheduler
from api.auth import decode_access_token, router as auth_router
from api.jobs import router as jobs_router
from api.resume import router as resume_router
from database.session import engine
from schemas.api_schemas import (
    AgentStatusResponse,
    ApplicationDetailResponse,
    ApplicationListItem,
    ErrorResponse,
    MetricsResponse,
)
from storage import data_dir
from websocket import websocket_manager

AUTH_EXEMPT_PATHS = {"/api/health", "/api/auth/login", "/api/auth/setup"}


def not_implemented(message: str) -> JSONResponse:
    payload = ErrorResponse(error="not_implemented", message=message)
    return JSONResponse(status_code=501, content=payload.model_dump())


def run_migrations() -> None:
    backend_dir = Path(__file__).resolve().parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


app = FastAPI(
    title="AutoHire API",
    version="0.1.0",
    description="AutoHire backend.",
)

nextauth_url = os.getenv("NEXTAUTH_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[nextauth_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and {"error", "message"} <= set(exc.detail):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "ERROR", "message": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "EXTRACTION_INCOMPLETE", "message": str(exc)},
    )


@app.middleware("http")
async def auth_middleware(request: Request, call_next: Any) -> Any:
    if request.method == "OPTIONS" or request.url.path in AUTH_EXEMPT_PATHS:
        return await call_next(request)

    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return JSONResponse(status_code=401, content={"error": "UNAUTHORIZED", "message": "Missing bearer token"})
    try:
        decode_access_token(authorization.split(" ", 1)[1])
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return await call_next(request)


@app.on_event("startup")
async def startup() -> None:
    data_dir()
    await asyncio.to_thread(run_migrations)
    start_scheduler()


@app.on_event("shutdown")
async def shutdown() -> None:
    await stop_scheduler()


@app.get("/api/health", tags=["system"])
async def health() -> dict[str, str]:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))

    redis = Redis.from_url(os.environ["REDIS_URL"])
    try:
        await redis.ping()
    finally:
        await redis.aclose()

    return {"status": "ok", "db": "connected", "redis": "connected"}


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)


app.include_router(auth_router)
app.include_router(resume_router)
app.include_router(jobs_router)
app.mount("/api/files", StaticFiles(directory=str(data_dir())), name="files")


@app.get(
    "/api/applications",
    response_model=list[ApplicationListItem] | ErrorResponse,
    tags=["applications"],
)
async def list_applications() -> Any:
    return not_implemented("Application listing is not implemented.")


@app.get(
    "/api/applications/{application_id}",
    response_model=ApplicationDetailResponse | ErrorResponse,
    tags=["applications"],
)
async def get_application(application_id: str) -> Any:
    return not_implemented(
        f"Application detail retrieval is not implemented for application {application_id}."
    )


@app.post(
    "/api/applications/{application_id}/approve-submit",
    response_model=ApplicationDetailResponse | ErrorResponse,
    tags=["applications"],
)
async def approve_submit(application_id: str) -> Any:
    return not_implemented(f"Submit approval is not implemented for application {application_id}.")


@app.post(
    "/api/applications/{application_id}/retry",
    response_model=ApplicationDetailResponse | ErrorResponse,
    tags=["applications"],
)
async def retry_application(application_id: str) -> Any:
    return not_implemented(f"Application retry is not implemented for application {application_id}.")


@app.get(
    "/api/agent/status",
    response_model=AgentStatusResponse | ErrorResponse,
    tags=["agent"],
)
async def get_agent_status() -> Any:
    return not_implemented("Agent status retrieval is not implemented.")


@app.post(
    "/api/agent/stop",
    response_model=AgentStatusResponse | ErrorResponse,
    tags=["agent"],
)
async def stop_agent() -> Any:
    return not_implemented("Agent stop is not implemented.")


@app.get(
    "/api/metrics",
    response_model=MetricsResponse | ErrorResponse,
    tags=["metrics"],
)
async def get_metrics() -> Any:
    return not_implemented("Metrics retrieval is not implemented.")
