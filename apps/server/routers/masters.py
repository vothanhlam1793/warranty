"""Customers, Products, Suppliers master data routers."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Customer, Product, Supplier, SyncState
from ..kiotviet.client import search_customers, search_products
from ..services.kiotviet_sync import sync_all

# ── Customers ─────────────────────────────────────────────────────────────────
customers_router = APIRouter(prefix="/api/customers", tags=["customers"])


class CustomerIn(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    kiotviet_id: Optional[str] = None
    note: Optional[str] = None


def _serialize_customer(c: Customer) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "phone": c.phone,
        "email": c.email,
        "address": c.address,
        "kiotviet_id": c.kiotviet_id,
        "note": c.note,
        "created_at": c.created_at.isoformat(),
    }


@customers_router.get("")
def list_customers(q: Optional[str] = Query(None), limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(Customer).order_by(Customer.name)
    if q:
        query = query.filter(Customer.name.ilike(f"%{q}%") | Customer.phone.ilike(f"%{q}%"))
    return [_serialize_customer(c) for c in query.limit(limit).all()]


@customers_router.post("", status_code=201)
def create_customer(payload: CustomerIn, db: Session = Depends(get_db)):
    c = Customer(**payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return _serialize_customer(c)


@customers_router.put("/{customer_id}")
def update_customer(customer_id: int, payload: CustomerIn, db: Session = Depends(get_db)):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "Customer not found")
    for k, v in payload.model_dump().items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return _serialize_customer(c)


@customers_router.get("/kiotviet/search")
def kiotviet_search_customers(q: str = Query(""), limit: int = 10):
    return search_customers(q, limit)


# ── Products ──────────────────────────────────────────────────────────────────
products_router = APIRouter(prefix="/api/products", tags=["products"])


class ProductIn(BaseModel):
    name: str
    sku: Optional[str] = None
    kiotviet_item_id: Optional[str] = None
    kiotviet_synced: bool = False
    note: Optional[str] = None


def _serialize_product(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "kiotviet_item_id": p.kiotviet_item_id,
        "kiotviet_synced": p.kiotviet_synced,
        "note": p.note,
        "created_at": p.created_at.isoformat(),
    }


@products_router.get("")
def list_products(q: Optional[str] = Query(None), limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(Product).order_by(Product.name)
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%") | Product.sku.ilike(f"%{q}%"))
    return [_serialize_product(p) for p in query.limit(limit).all()]


@products_router.post("", status_code=201)
def create_product(payload: ProductIn, db: Session = Depends(get_db)):
    p = Product(**payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _serialize_product(p)


@products_router.put("/{product_id}")
def update_product(product_id: int, payload: ProductIn, db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Product not found")
    for k, v in payload.model_dump().items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return _serialize_product(p)


@products_router.get("/kiotviet/search")
def kiotviet_search_products(q: str = Query(""), limit: int = 10):
    return search_products(q, limit)


@customers_router.get("/sync/status")
def sync_status(db: Session = Depends(get_db)):
    rows = db.query(SyncState).all()
    return {
        r.key: {
            "last_success_at": r.last_success_at.isoformat() if r.last_success_at else None,
            "last_error": r.last_error,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    }


@customers_router.post("/sync", status_code=202)
def trigger_sync(db: Session = Depends(get_db)):
    return sync_all(db)


# ── Suppliers ─────────────────────────────────────────────────────────────────
suppliers_router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


class SupplierIn(BaseModel):
    name: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    note: Optional[str] = None
    is_active: bool = True


def _serialize_supplier(s: Supplier) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "contact_name": s.contact_name,
        "phone": s.phone,
        "email": s.email,
        "address": s.address,
        "note": s.note,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat(),
    }


@suppliers_router.get("")
def list_suppliers(db: Session = Depends(get_db)):
    return [_serialize_supplier(s) for s in db.query(Supplier).order_by(Supplier.name).all()]


@suppliers_router.post("", status_code=201)
def create_supplier(payload: SupplierIn, db: Session = Depends(get_db)):
    s = Supplier(**payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return _serialize_supplier(s)


@suppliers_router.put("/{supplier_id}")
def update_supplier(supplier_id: int, payload: SupplierIn, db: Session = Depends(get_db)):
    s = db.get(Supplier, supplier_id)
    if not s:
        raise HTTPException(404, "Supplier not found")
    for k, v in payload.model_dump().items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return _serialize_supplier(s)
