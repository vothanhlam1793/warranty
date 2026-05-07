"""Odoo sync service: upsert customers/products to local DB."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..models import Customer, Product, ReturnSlip, SyncState
from ..odoo.client import fetch_customers_with_codes, search_customers, search_products


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit())
    return digits or None


def _pick_customer_winner(customers: list[Customer]) -> Customer:
    def score(customer: Customer) -> tuple[int, int, int]:
        return (
            1 if customer.customer_code else 0,
            1 if customer.kiotviet_id else 0,
            -customer.id,
        )

    return max(customers, key=score)


def apply_odoo_customer_data(customer: Customer, row: dict) -> None:
    customer.customer_code = row.get("customer_code") or customer.customer_code
    customer.kiotviet_id = row.get("odoo_id") or row.get("kiotviet_id") or customer.kiotviet_id
    customer.name = row.get("name") or customer.name
    customer.phone = normalize_phone(row.get("phone")) or customer.phone
    customer.email = row.get("email") or customer.email
    customer.address = row.get("address") or customer.address


def merge_customers_by_phone(db: Session, phone: str | None, preferred: Customer | None = None) -> Customer | None:
    normalized_phone = normalize_phone(phone)
    if not normalized_phone:
        return preferred

    matches = [c for c in db.query(Customer).all() if normalize_phone(c.phone) == normalized_phone]
    if len(matches) <= 1:
        if preferred:
            preferred.phone = normalized_phone
        return preferred or (matches[0] if matches else None)

    winner = preferred if preferred in matches else _pick_customer_winner(matches)
    winner.phone = normalized_phone
    for customer in matches:
        if customer.id == winner.id:
            continue
        if not winner.customer_code and customer.customer_code:
            winner.customer_code = customer.customer_code
        if not winner.kiotviet_id and customer.kiotviet_id:
            winner.kiotviet_id = customer.kiotviet_id
        if not winner.email and customer.email:
            winner.email = customer.email
        if not winner.address and customer.address:
            winner.address = customer.address
        if not winner.note and customer.note:
            winner.note = customer.note
        if winner.name.startswith("Khach hang") and customer.name:
            winner.name = customer.name
        for ticket in customer.tickets:
            ticket.customer = winner
        db.query(ReturnSlip).filter(ReturnSlip.customer_id == customer.id).update(
            {ReturnSlip.customer_id: winner.id},
            synchronize_session=False,
        )
        db.query(Customer).filter(Customer.id == customer.id).delete()
    db.flush()
    return winner


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
        rows = fetch_customers_with_codes(limit=500) or search_customers("", limit=500)
        for row in rows:
            source_id = row.get("odoo_id") or row.get("kiotviet_id")
            customer_code = row.get("customer_code")
            phone = normalize_phone(row.get("phone"))
            if not source_id:
                continue
            filters = [Customer.kiotviet_id == source_id]
            if customer_code:
                filters.append(Customer.customer_code == customer_code)
            c = db.query(Customer).filter(or_(*filters)).first()
            if c:
                apply_odoo_customer_data(c, row)
                c = merge_customers_by_phone(db, phone, preferred=c) or c
                apply_odoo_customer_data(c, row)
                updated += 1
            else:
                c = Customer(
                    name=row.get("name") or "Khach hang Odoo",
                    customer_code=customer_code,
                    phone=phone,
                    email=row.get("email"),
                    address=row.get("address"),
                    kiotviet_id=source_id,
                )
                db.add(c)
                db.flush()
                c = merge_customers_by_phone(db, phone, preferred=c) or c
                apply_odoo_customer_data(c, row)
                created += 1
        st.last_success_at = datetime.utcnow()
        st.last_error = None
        db.commit()
        return {"key": key, "created": created, "updated": updated, "total_source": len(rows), "source": "odoo"}
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
            source_id = row.get("odoo_id") or row.get("kiotviet_item_id")
            if not source_id:
                continue
            p = db.query(Product).filter(Product.kiotviet_item_id == source_id).first()
            if p:
                p.name = row.get("name") or p.name
                p.sku = row.get("sku")
                p.kiotviet_synced = True
                updated += 1
            else:
                db.add(
                    Product(
                        name=row.get("name") or "San pham Odoo",
                        sku=row.get("sku"),
                        kiotviet_item_id=source_id,
                        kiotviet_synced=True,
                    )
                )
                created += 1
        st.last_success_at = datetime.utcnow()
        st.last_error = None
        db.commit()
        return {"key": key, "created": created, "updated": updated, "total_source": len(rows), "source": "odoo"}
    except Exception as e:
        st.last_error = str(e)
        db.commit()
        raise


def sync_all(db: Session) -> dict:
    c = sync_customers(db)
    p = sync_products(db)
    return {"customers": c, "products": p, "source": "odoo"}
