from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from database.models import ApplicationEvent
from database.session import AsyncSessionLocal
from notifications.telegram import send_health_alert

router = APIRouter(tags=["websocket"])

AGENT_STATE_KEY = "autohire:agent_state"
STOP_KEY = "autohire:stop_requested"


class ConnectionManager:
    """Manages all active WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        await self.send_event(
            websocket,
            {"event": "AGENT_STATUS", "status": await get_agent_status()},
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_event(self, websocket: WebSocket, event: dict[str, Any]) -> None:
        if "timestamp" not in event:
            event["timestamp"] = _timestamp()
        await websocket.send_json(event)

    async def broadcast(self, event: dict[str, Any]) -> None:
        if "timestamp" not in event:
            event["timestamp"] = _timestamp()
        disconnected: list[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(event)
            except Exception:
                disconnected.append(connection)
        for connection in disconnected:
            await self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


async def publish_ws_event(event_type: str, **payload: Any) -> None:
    """Called by agent, scanner, preparer, and notification jobs when an event happens."""
    event = {"event": event_type, **payload}
    await manager.broadcast(event)

    application_id = payload.get("application_id")
    await save_event_to_db(
        application_id=str(application_id) if application_id else None,
        trace_id=str(payload["trace_id"]) if payload.get("trace_id") else None,
        event_type=event_type,
        event=event,
    )
    if event_type == "ERROR":
        await send_health_alert(str(payload.get("error_code", "ERROR")), str(payload.get("message", "")))


async def save_event_to_db(
    application_id: str | None,
    trace_id: str | None,
    event_type: str,
    event: dict[str, Any],
) -> None:
    async with AsyncSessionLocal() as db:
        db.add(
            ApplicationEvent(
                application_id=application_id,
                trace_id=trace_id,
                event_type=event_type,
                event_data=event,
            )
        )
        await db.commit()


async def get_agent_status() -> dict[str, Any]:
    redis = _redis()
    try:
        raw = await redis.get(AGENT_STATE_KEY)
        stop_requested = bool(await redis.get(STOP_KEY))
    finally:
        await redis.aclose()

    status = json.loads(raw) if raw else {"status": "idle"}
    return {
        "status": status.get("status", "idle"),
        "current_application_id": status.get("current_application_id"),
        "current_company": status.get("current_company"),
        "current_field": status.get("current_field"),
        "trace_id": status.get("trace_id"),
        "stop_requested": stop_requested,
    }


def _redis() -> Redis:
    return Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
