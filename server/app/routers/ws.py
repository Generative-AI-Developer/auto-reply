from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.ws_manager import manager

router = APIRouter()


@router.websocket("/ws/requests")
async def requests_ws(ws: WebSocket):
    """Live feed of request_created / status_changed events for dashboard + clients."""
    await manager.connect(ws)
    try:
        while True:
            # We don't expect inbound messages; keep the socket open.
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)
