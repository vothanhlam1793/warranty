"""Admin router — manage users and system settings."""

from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models import User, UserRole, UserSession
from .auth import hash_password, _serialize_user, get_session

router = APIRouter(prefix="/api/admin", tags=["admin"])

def get_current_admin(request: Request, db: Session = Depends(get_db)) -> User:
    session = get_session(request, db)
    if not session or session.user.role != UserRole.admin:
        raise HTTPException(403, "Quyền Admin là bắt buộc")
    return session.user

class UserUpdateIn(BaseModel):
    display_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class UserCreateIn(BaseModel):
    username: str
    password: str
    display_name: str
    role: UserRole = UserRole.technician

@router.get("/users")
def list_users(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    users = db.query(User).order_by(User.id.asc()).all()
    return [_serialize_user(u) for u in users]

@router.post("/users", status_code=201)
def create_user(payload: UserCreateIn, db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(400, "Username đã tồn tại")
    
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _serialize_user(user)

@router.patch("/users/{user_id}")
def update_user(user_id: int, payload: UserUpdateIn, db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.password_hash = hash_password(payload.password)
    
    db.commit()
    return _serialize_user(user)

@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    if user_id == admin.id:
        raise HTTPException(400, "Không thể tự xóa chính mình")
    
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    db.delete(user)
    db.commit()
    return {"ok": True}
