"""Auth router — login, logout, me."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, UserSession

import bcrypt as _bcrypt

def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_TTL_HOURS = 8


class LoginIn(BaseModel):
    username: str
    password: str


class CreateUserIn(BaseModel):
    username: str
    password: str
    display_name: str
    role: str = "technician"


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
    }


def get_session(request: Request, db: Session) -> Optional[UserSession]:
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.expires_at > datetime.utcnow(),
    ).first()
    return session


def resolve_actor(request: Request, db: Session, actor: Optional[str] = None, required: bool = False) -> Optional[str]:
    name = (actor or "").strip()
    if name:
        return name
    session = get_session(request, db)
    if session and session.user:
        return session.user.display_name or session.user.username
    if required:
        raise HTTPException(401, "Không xác định được người thao tác")
    return None


@router.post("/login")
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not user.is_active:
        raise HTTPException(401, "Tên đăng nhập hoặc mật khẩu không đúng")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Tên đăng nhập hoặc mật khẩu không đúng")

    session_id = uuid.uuid4().hex
    expires = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)
    session = UserSession(id=session_id, user_id=user.id, expires_at=expires)
    db.add(session)
    db.commit()

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=SESSION_TTL_HOURS * 3600,
        path="/",
    )
    return {"user": _serialize_user(user)}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    session_id = request.cookies.get("session_id")
    if session_id:
        db.query(UserSession).filter(UserSession.id == session_id).delete()
        db.commit()
    response.delete_cookie("session_id", path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    session = get_session(request, db)
    if not session:
        raise HTTPException(401, "Chưa đăng nhập")
    return {"user": _serialize_user(session.user)}


# ── Admin: tạo user (không cần auth để seed lần đầu) ─────────────────────────
@router.post("/users", status_code=201)
def create_user(payload: CreateUserIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(400, f"Username '{payload.username}' đã tồn tại")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _serialize_user(user)


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    return [_serialize_user(u) for u in db.query(User).all()]
