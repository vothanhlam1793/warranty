"""Supplier receive slips - nhận hàng từ NCC theo lô."""

from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from .auth import resolve_actor
from ..models import (
    SupplierReceive, SupplierReceiveItem, SupplierReceiveStatus,
    SupplierOrderItem, SupplierOrder, Supplier,
    TicketItem, WorkflowState, WorkflowLog, Transaction, TransactionType, TransactionStatus,
)

router = APIRouter(prefix="/api/supplier-receives", tags=["supplier-receives"])


def _resolve_item_supplier_id(db: Session, ticket_item_id: int) -> Optional[int]:
    """Resolve single supplier for an item from supplier-order history.

    Rule: item must map to exactly one supplier across all supplier orders.
    """
    rows = (
        db.query(SupplierOrder.supplier_id)
        .join(SupplierOrderItem, SupplierOrderItem.order_id == SupplierOrder.id)
        .filter(SupplierOrderItem.ticket_item_id == ticket_item_id)
        .distinct()
        .all()
    )
    sids = {sid for (sid,) in rows}
    if len(sids) == 1:
        return next(iter(sids))
    return None


class ReceiveLineIn(BaseModel):
    ticket_item_id: int
    result: Optional[str] = None
    result_note: Optional[str] = None


class SupplierReceiveIn(BaseModel):
    supplier_id: int
    received_date: date
    actor: Optional[str] = None
    note: Optional[str] = None
    items: List[ReceiveLineIn]


def _next_receive_no(db: Session) -> str:
    last = db.query(SupplierReceive).order_by(SupplierReceive.id.desc()).first()
    num = (last.id + 1) if last else 1
    return f"RNCC-{num:04d}"


def _serialize_receive(r: SupplierReceive) -> dict:
    return {
        "id": r.id,
        "receive_no": r.receive_no,
        "supplier_id": r.supplier_id,
        "supplier_name": r.supplier.name if r.supplier else None,
        "status": r.status,
        "received_date": r.received_date.isoformat(),
        "actor": r.actor,
        "note": r.note,
        "created_at": r.created_at.isoformat(),
        "items": [
            {
                "id": it.id,
                "ticket_item_id": it.ticket_item_id,
                "item_code": it.ticket_item.item_code if it.ticket_item else None,
                "ticket_no": it.ticket_item.ticket.ticket_no if it.ticket_item and it.ticket_item.ticket else None,
                "product_name": it.ticket_item.product.name if it.ticket_item and it.ticket_item.product else None,
                "serial_no": it.ticket_item.serial_no if it.ticket_item else None,
                "result": it.result,
                "result_note": it.result_note,
            }
            for it in r.items
        ],
    }


@router.get("/candidate-items")
def list_candidates(supplier_id: int = Query(...), db: Session = Depends(get_db)):
    rows = (
        db.query(TicketItem)
        .join(SupplierOrderItem, SupplierOrderItem.ticket_item_id == TicketItem.id)
        .join(SupplierOrderItem.order)
        .options(joinedload(TicketItem.ticket), joinedload(TicketItem.product))
        .filter(
            SupplierOrderItem.order.has(supplier_id=supplier_id),
            TicketItem.workflow_state == WorkflowState.B2,
        )
        .all()
    )
    # Deduplicate and enforce unique supplier mapping per item
    out = []
    seen = set()
    for x in rows:
        if x.id in seen:
            continue
        seen.add(x.id)
        resolved_sid = _resolve_item_supplier_id(db, x.id)
        if resolved_sid != supplier_id:
            continue
        out.append({
            "ticket_item_id": x.id,
            "item_code": x.item_code,
            "ticket_no": x.ticket.ticket_no if x.ticket else None,
            "product_name": x.product.name if x.product else None,
            "serial_no": x.serial_no,
            "customer_complaint": x.customer_complaint,
        })
    return out


@router.post("", status_code=201)
def create_receive(payload: SupplierReceiveIn, request: Request, db: Session = Depends(get_db)):
    actor = resolve_actor(request, db, payload.actor)
    if not db.get(Supplier, payload.supplier_id):
        raise HTTPException(404, "Supplier not found")
    if not payload.items:
        raise HTTPException(400, "Danh sách item rỗng")

    # validate items ở B2 và thuộc supplier
    item_ids = [i.ticket_item_id for i in payload.items]
    tis = db.query(TicketItem).filter(TicketItem.id.in_(item_ids)).all()
    ti_map = {x.id: x for x in tis}
    if len(ti_map) != len(set(item_ids)):
        raise HTTPException(400, "Có item không tồn tại")

    for tid in item_ids:
        ti = ti_map[tid]
        if ti.workflow_state != WorkflowState.B2:
            raise HTTPException(400, f"Item {ti.item_code or ti.id} không ở B2")
        resolved_sid = _resolve_item_supplier_id(db, tid)
        if resolved_sid != payload.supplier_id:
            raise HTTPException(400, f"Item {ti.item_code or ti.id} không thuộc NCC đã chọn")

    rec = SupplierReceive(
        receive_no=_next_receive_no(db),
        supplier_id=payload.supplier_id,
        status=SupplierReceiveStatus.posted,
        received_date=payload.received_date,
        actor=actor,
        note=payload.note,
    )
    db.add(rec)
    db.flush()

    for ln in payload.items:
        ti = ti_map[ln.ticket_item_id]
        db.add(SupplierReceiveItem(
            receive_id=rec.id,
            ticket_item_id=ln.ticket_item_id,
            result=ln.result,
            result_note=ln.result_note,
        ))
        draft_supplier_txn = (
            db.query(Transaction)
            .filter(
                Transaction.ticket_item_id == ti.id,
                Transaction.type == TransactionType.chi,
                Transaction.status == TransactionStatus.draft,
            )
            .order_by(Transaction.id.desc())
            .first()
        )
        if draft_supplier_txn:
            draft_supplier_txn.status = TransactionStatus.posted
        old = ti.workflow_state
        ti.workflow_state = WorkflowState.C1
        if ln.result_note:
            ti.result_note = ln.result_note
        db.add(WorkflowLog(
            ticket_item_id=ti.id,
            from_state=old,
            to_state=WorkflowState.C1,
            note=f"Nhận về từ NCC qua phiếu {rec.receive_no}. {ln.result_note or ''}".strip(),
            actor=actor,
        ))

    db.commit()
    db.refresh(rec)
    rec = db.query(SupplierReceive).options(
        joinedload(SupplierReceive.supplier),
        joinedload(SupplierReceive.items).joinedload(SupplierReceiveItem.ticket_item).joinedload(TicketItem.product),
        joinedload(SupplierReceive.items).joinedload(SupplierReceiveItem.ticket_item).joinedload(TicketItem.ticket),
    ).filter(SupplierReceive.id == rec.id).first()
    return _serialize_receive(rec)


@router.get("")
def list_receives(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(SupplierReceive).options(
        joinedload(SupplierReceive.supplier),
        joinedload(SupplierReceive.items).joinedload(SupplierReceiveItem.ticket_item).joinedload(TicketItem.product),
        joinedload(SupplierReceive.items).joinedload(SupplierReceiveItem.ticket_item).joinedload(TicketItem.ticket),
    ).order_by(SupplierReceive.id.desc())
    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    return {"total": total, "limit": limit, "offset": offset, "items": [_serialize_receive(x) for x in rows]}


@router.get("/{receive_id}")
def get_receive(receive_id: int, db: Session = Depends(get_db)):
    row = db.query(SupplierReceive).options(
        joinedload(SupplierReceive.supplier),
        joinedload(SupplierReceive.items).joinedload(SupplierReceiveItem.ticket_item).joinedload(TicketItem.product),
        joinedload(SupplierReceive.items).joinedload(SupplierReceiveItem.ticket_item).joinedload(TicketItem.ticket),
    ).filter(SupplierReceive.id == receive_id).first()
    if not row:
        raise HTTPException(404, "Receive slip not found")
    return _serialize_receive(row)
