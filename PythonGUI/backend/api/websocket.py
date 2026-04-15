from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.state_manager import StateManager


def build_websocket_router(state_manager: StateManager) -> APIRouter:
    router = APIRouter(tags=["websocket"])

    @router.websocket("/ws/status")
    async def status_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(state_manager.snapshot().model_dump(mode="json"))
                await asyncio.sleep(0.5)
        except WebSocketDisconnect:
            return

    return router
