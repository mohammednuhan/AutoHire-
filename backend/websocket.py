from __future__ import annotations

from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def publish(self, event: dict[str, Any]) -> None:
        disconnected: list[WebSocket] = []
        for websocket in self._connections:
            try:
                await websocket.send_json(event)
            except RuntimeError:
                disconnected.append(websocket)
        for websocket in disconnected:
            self.disconnect(websocket)


websocket_manager = WebSocketManager()
