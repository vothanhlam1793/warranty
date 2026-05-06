"""FastAPI main application."""

from __future__ import annotations

from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import os

from .database import init_db, get_db
from .models import UserSession
from .routers.tickets import router as tickets_router
from .routers.masters import customers_router, products_router, suppliers_router
from .routers.supplier_orders import router as supplier_orders_router
from .routers.transactions import router as transactions_router
from .routers.tasks import router as tasks_router
from .routers.auth import router as auth_router
from .routers.supplier_receives import router as supplier_receives_router
from .routers.checklists import router as checklists_router

app = FastAPI(title="Warranty Management System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ── Auth middleware ────────────────────────────────────────────────────────────
_AUTH_SKIP = ("/api/auth/", "/api/health", "/uploads/", "/static/")

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # Skip auth cho các path không cần kiểm tra
    skip = any(path.startswith(p) for p in _AUTH_SKIP) or not path.startswith("/api/")
    if not skip:
        session_id = request.cookies.get("session_id")
        if session_id:
            # Inject user vào state (lazy — không query nếu không cần)
            request.state.session_id = session_id
            request.state.current_user = None  # sẽ resolve trong dependency
        # Không block — vì actor vẫn có thể là optional ở một số endpoint
        # Middleware chỉ inject session_id, việc enforce là tuỳ từng endpoint
    return await call_next(request)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(tickets_router)
app.include_router(customers_router)
app.include_router(products_router)
app.include_router(suppliers_router)
app.include_router(supplier_orders_router)
app.include_router(transactions_router)
app.include_router(tasks_router)
app.include_router(supplier_receives_router)
app.include_router(checklists_router)


# ── Serve uploaded evidence files ─────────────────────────────────────────────
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ── Static web frontend ───────────────────────────────────────────────────────
WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "web")

if os.path.isdir(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def root():
        return FileResponse(os.path.join(WEB_DIR, "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        file_path = os.path.join(WEB_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(WEB_DIR, "index.html"))


@app.on_event("startup")
def on_startup():
    init_db()
    print("Database ready")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
