from __future__ import annotations

from typing import Any

from api.websocket import manager


class WebSocketManager:
    async def publish(self, event: dict[str, Any]) -> None:
        await manager.broadcast(event)


websocket_manager = WebSocketManager()
