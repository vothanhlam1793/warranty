"""FastAPI main application."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from .database import init_db, get_db
from .models import UserSession
from .routers.tickets import router as tickets_router
from .routers.masters import customers_router, products_router, suppliers_router
from .routers.supplier_orders import router as supplier_orders_router
from .routers.transactions import router as transactions_router
from .routers.tasks import router as tasks_router
from .routers.auth import router as auth_router
from .routers.admin import router as admin_router
from .routers.supplier_receives import router as supplier_receives_router
from .routers.checklists import router as checklists_router
from .routers.return_slips import router as return_slips_router

app = FastAPI(title="Warranty Management System", version="1.3.4")

_extra_origins = [origin.strip() for origin in os.environ.get("CORS_ALLOW_ORIGINS", "").split(",") if origin.strip()]
_default_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8000",
    "http://localhost:8001",
    "https://warranty.camerangochoang.com",
]
_allow_origins = list(dict.fromkeys(_default_origins + _extra_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
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
app.include_router(admin_router)
app.include_router(tickets_router)
app.include_router(customers_router)
app.include_router(products_router)
app.include_router(suppliers_router)
app.include_router(supplier_orders_router)
app.include_router(transactions_router)
app.include_router(tasks_router)
app.include_router(supplier_receives_router)
app.include_router(checklists_router)
app.include_router(return_slips_router)


# ── Serve uploaded evidence files ─────────────────────────────────────────────
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.on_event("startup")
def on_startup():
    init_db()
    print("Database ready")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.3.4"}
