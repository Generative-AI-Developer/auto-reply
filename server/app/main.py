import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .routers import auth, requests, users, ws
from .services.watcher import start_watcher
from .services.ws_manager import manager

logging.basicConfig(level=logging.INFO)

settings = get_settings()
app = FastAPI(title="Auto-Reply Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(requests.router)
app.include_router(ws.router)

_observer = None


@app.on_event("startup")
def on_startup():
    settings.ensure_dirs()
    init_db()
    manager.set_loop(asyncio.get_event_loop())
    global _observer
    _observer = start_watcher()


@app.on_event("shutdown")
def on_shutdown():
    if _observer is not None:
        _observer.stop()
        _observer.join(timeout=5)


@app.get("/health")
def health():
    return {"status": "ok"}
