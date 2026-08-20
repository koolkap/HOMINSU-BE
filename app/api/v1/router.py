from fastapi import APIRouter

from app.api.v1.endpoints import auth, content, fleet, points, srs_webhooks

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(points.router)
api_router.include_router(content.router)
api_router.include_router(fleet.router)
api_router.include_router(srs_webhooks.router)

# WebSocket routes live at the top level (/ws/...), not under /api/v1.
ws_router = APIRouter()
ws_router.include_router(fleet.ws_router)
