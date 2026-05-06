"""KiotViet sync service: upsert customers/products to local DB."""

from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session

from ..kiotviet.client import search_customers, search_products
from ..models import Customer, Product, SyncState


def _get_or_create_state(db: Session, key: str) -> SyncState:
    st = db.get(SyncState, key)
    if not st:
        st = SyncState(key=key)
        db.add(st)
        db.flush()
    return st


def sync_customers(db: Session) -> dict:
    key = "customers"
    st = _get_or_create_state(db, key)
    created = 0
    updated = 0
    try:
        rows = search_customers("", limit=500)
        for row in rows:
            kv_id = row.get("kiotviet_id")
            if not kv_id:
                continue
            c = db.query(Customer).filter(Customer.kiotviet_id == kv_id).first()
            if c:
                c.name = row.get("name") or c.name
                c.phone = row.get("phone")
                c.address = row.get("address")
                updated += 1
            else:
                db.add(Customer(
                    name=row.get("name") or "Khách hàng KiotViet",
                    phone=row.get("phone"),
                    address=row.get("address"),
                    kiotviet_id=kv_id,
                ))
                created += 1
        st.last_success_at = datetime.utcnow()
        st.last_error = None
        db.commit()
        return {"key": key, "created": created, "updated": updated, "total_source": len(rows)}
    except Exception as e:
        st.last_error = str(e)
        db.commit()
        raise


def sync_products(db: Session) -> dict:
    key = "products"
    st = _get_or_create_state(db, key)
    created = 0
    updated = 0
    try:
        rows = search_products("", limit=1000)
        for row in rows:
            kv_id = row.get("kiotviet_item_id")
            if not kv_id:
                continue
            p = db.query(Product).filter(Product.kiotviet_item_id == kv_id).first()
            if p:
                p.name = row.get("name") or p.name
                p.sku = row.get("sku")
                p.kiotviet_synced = True
                updated += 1
            else:
                db.add(Product(
                    name=row.get("name") or "Sản phẩm KiotViet",
                    sku=row.get("sku"),
                    kiotviet_item_id=kv_id,
                    kiotviet_synced=True,
                ))
                created += 1
        st.last_success_at = datetime.utcnow()
        st.last_error = None
        db.commit()
        return {"key": key, "created": created, "updated": updated, "total_source": len(rows)}
    except Exception as e:
        st.last_error = str(e)
        db.commit()
        raise


def sync_all(db: Session) -> dict:
    c = sync_customers(db)
    p = sync_products(db)
    return {"customers": c, "products": p}
