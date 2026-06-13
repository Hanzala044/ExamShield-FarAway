from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.ws_manager import manager

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/center/{center_id}")
async def ws_center(websocket: WebSocket, center_id: int):
    channel = f"center:{center_id}"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()  # keepalive; alerts are server-pushed
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


@router.websocket("/ws/admin")
async def ws_admin(websocket: WebSocket):
    await manager.connect("admin", websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect("admin", websocket)
