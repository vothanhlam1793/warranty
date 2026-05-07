"""Tickets router - create, list, detail, state transitions."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import cast, Integer, or_
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from .auth import resolve_actor
from ..models import (
    Ticket, TicketItem, Customer, Product,
    WorkflowState, RequestedAction, WorkflowLog,
    SupplierOrderItem, SupplierOrder, SupplierOrderStatus,
    Transaction, TransactionType, TransactionStatus,
)

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class TicketItemIn(BaseModel):
    product_id: int
    serial_no: Optional[str] = None
    qty: int = 1
    requested_action: RequestedAction = RequestedAction.bao_hanh
    customer_complaint: Optional[str] = None


class TicketIn(BaseModel):
    customer_id: int
    received_date: date
    note: Optional[str] = None
    created_by: Optional[str] = None
    items: List[TicketItemIn]


class StateTransitionIn(BaseModel):
    to_state: WorkflowState
    note: str                              # bắt buộc
    actor: Optional[str] = None
    diagnosis_note: Optional[str] = None
    expected_return_date: Optional[date] = None


class QuoteDecisionIn(BaseModel):
    actor: Optional[str] = None
    note: str
    customer_approved: bool


# Ma trận chuyển trạng thái THỦ CÔNG hợp lệ
# Các bước tự động (A3→B1, B1→B2, B2→C1, C4→C5, C5→C6) KHÔNG có ở đây
ALLOWED_TRANSITIONS: dict[WorkflowState, list[WorkflowState]] = {
    WorkflowState.A1: [WorkflowState.A2],
    WorkflowState.A2: [WorkflowState.A3, WorkflowState.C2, WorkflowState.C4],
    WorkflowState.A3: [],        # chỉ tự động qua B1 khi tạo phiếu NCC
    WorkflowState.B1: [],        # chỉ tự động qua B2 khi phiếu NCC xác nhận gửi
    WorkflowState.B2: [WorkflowState.B4],
    WorkflowState.B4: [WorkflowState.B2],
    WorkflowState.C1: [WorkflowState.C2, WorkflowState.C3],
    WorkflowState.C2: [WorkflowState.C5],
    WorkflowState.C3: [WorkflowState.C4, WorkflowState.C2],
    WorkflowState.C4: [],        # chỉ tự động qua C5 khi ghi transaction thu
    WorkflowState.C5: [],        # chỉ tự động qua C6 khi upload ảnh bằng chứng
    WorkflowState.C6: [],
}


class ExtendDeadlineIn(BaseModel):
    extra_days: int
    reason: str
    actor: Optional[str] = None


class NotifyLateIn(BaseModel):
    note: Optional[str] = None
    actor: Optional[str] = None


class ItemNotifyLateIn(BaseModel):
    note: str
    actor: Optional[str] = None
    new_deadline_date: date


# ── Helpers ───────────────────────────────────────────────────────────────────

def _next_ticket_no(db: Session) -> str:
    """Generate next ticket number as a plain integer string, e.g. '742'."""
    last_numeric = (
        db.query(cast(Ticket.ticket_no, Integer))
        .filter(Ticket.ticket_no.op('~')(r'^\d+$'))
        .order_by(cast(Ticket.ticket_no, Integer).desc())
        .first()
    )
    if not last_numeric or last_numeric[0] is None:
        return "1"
    return str(int(last_numeric[0]) + 1)

def _serialize_item(item: TicketItem) -> dict:
    today = date.today()
    deadline = item.deadline_date
    item_days_to_deadline = (deadline - today).days if deadline else None
    item_is_deadline_overdue = item_days_to_deadline is not None and item_days_to_deadline < 0
    item_is_urgent = item_days_to_deadline is not None and 0 <= item_days_to_deadline <= 2
    return {
        "id": item.id,
        "ticket_id": item.ticket_id,
        "item_no": item.item_no,
        "item_code": item.item_code,          # ← e.g. "742-1"
        "product_id": item.product_id,
        "product_name": item.product.name if item.product else None,
        "product_sku": item.product.sku if item.product else None,
        "serial_no": item.serial_no,
        "qty": item.qty,
        "requested_action": item.requested_action,
        "workflow_state": item.workflow_state,
        "customer_complaint": item.customer_complaint,
        "diagnosis_note": item.diagnosis_note,
        "result_note": item.result_note,
        "deadline_date": item.deadline_date.isoformat() if item.deadline_date else None,
        "extension_days": item.extension_days or 0,
        "notified_late": bool(item.notified_late),
        "item_days_to_deadline": item_days_to_deadline,
        "item_is_deadline_overdue": item_is_deadline_overdue,
        "item_is_urgent": item_is_urgent,
        "expected_return_date": item.expected_return_date.isoformat() if item.expected_return_date else None,
        "returned_date": item.returned_date.isoformat() if item.returned_date else None,
        "evidence_url": item.evidence_url,
        "requires_customer_payment": bool(item.requires_customer_payment),
        "created_at": item.created_at.isoformat(),
    }


def _get_quote_transactions(db: Session, item_id: int) -> list[Transaction]:
    return (
        db.query(Transaction)
        .filter(
            Transaction.ticket_item_id == item_id,
            Transaction.status == TransactionStatus.draft,
            Transaction.type.in_([TransactionType.chi, TransactionType.thu]),
        )
        .order_by(Transaction.id.asc())
        .all()
    )


def _serialize_ticket(ticket: Ticket) -> dict:
    # Sort items by item_no for consistent display
    items_sorted = sorted(ticket.items, key=lambda i: i.item_no)
    today = date.today()
    dl = ticket.deadline_date
    days_to_deadline = (dl - today).days if dl else None
    is_overdue_deadline = days_to_deadline is not None and days_to_deadline < 0
    is_urgent = days_to_deadline is not None and 0 <= days_to_deadline <= 2
    return {
        "id": ticket.id,
        "ticket_no": ticket.ticket_no,
        "customer_id": ticket.customer_id,
        "customer_name": ticket.customer.name if ticket.customer else None,
        "customer_phone": ticket.customer.phone if ticket.customer else None,
        "received_date": ticket.received_date.isoformat(),
        "deadline_date": dl.isoformat() if dl else None,
        "days_to_deadline": days_to_deadline,
        "is_overdue_deadline": is_overdue_deadline,
        "is_urgent": is_urgent,
        "extension_days": ticket.extension_days or 0,
        "notified_late": bool(ticket.notified_late),
        "note": ticket.note,
        "created_by": ticket.created_by,
        "created_at": ticket.created_at.isoformat(),
        "items": [_serialize_item(i) for i in items_sorted],
        "item_count": len(ticket.items),
        "open_count": sum(1 for i in ticket.items if i.workflow_state != WorkflowState.C6),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_ticket(payload: TicketIn, request: Request, db: Session = Depends(get_db)):
    if not db.get(Customer, payload.customer_id):
        raise HTTPException(404, "Customer not found")

    created_by = resolve_actor(request, db, payload.created_by)
    ticket_no = _next_ticket_no(db)
    deadline = payload.received_date + timedelta(days=14)
    ticket = Ticket(
        ticket_no=ticket_no,
        customer_id=payload.customer_id,
        received_date=payload.received_date,
        deadline_date=deadline,
        extension_days=0,
        notified_late=False,
        note=payload.note,
        created_by=created_by,
    )
    db.add(ticket)
    db.flush()

    for idx, item_in in enumerate(payload.items, start=1):
        if not db.get(Product, item_in.product_id):
            raise HTTPException(404, f"Product {item_in.product_id} not found")

        item_code = f"{ticket_no}-{idx}"          # ← "742-1", "742-2"...

        item = TicketItem(
            ticket_id=ticket.id,
            item_no=idx,
            item_code=item_code,
            product_id=item_in.product_id,
            serial_no=item_in.serial_no,
            qty=item_in.qty,
            requested_action=item_in.requested_action,
            customer_complaint=item_in.customer_complaint,
            workflow_state=WorkflowState.A1,
        )
        db.add(item)
        db.flush()
        log = WorkflowLog(
            ticket_item_id=item.id,
            from_state=None,
            to_state=WorkflowState.A1,
            note="Tiếp nhận",
            actor=created_by,
        )
        db.add(log)

    db.commit()
    db.refresh(ticket)
    return _serialize_ticket(ticket)


@router.get("")
def list_tickets(
    state: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Ticket)
        .options(joinedload(Ticket.customer), joinedload(Ticket.items).joinedload(TicketItem.product))
        .order_by(Ticket.id.desc())
    )
    if customer_id:
        query = query.filter(Ticket.customer_id == customer_id)
    if q:
        like = f"%{q}%"
        query = query.join(Customer).outerjoin(TicketItem).filter(
            or_(
                Customer.name.ilike(like),
                Ticket.ticket_no.ilike(like),
                TicketItem.item_code.ilike(like),
                TicketItem.serial_no.ilike(like),
            )
        )
    if state:
        try:
            wf_state = WorkflowState(state)
        except ValueError:
            raise HTTPException(400, f"state không hợp lệ: {state}")
        query = query.join(Ticket.items).filter(TicketItem.workflow_state == wf_state)

    total = query.distinct(Ticket.id).count()
    tickets = query.distinct(Ticket.id).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_serialize_ticket(t) for t in tickets],
    }


@router.get("/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = (
        db.query(Ticket)
        .options(joinedload(Ticket.customer), joinedload(Ticket.items).joinedload(TicketItem.product))
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    return _serialize_ticket(ticket)


@router.get("/by-item-code/{item_code}")
def get_by_item_code(item_code: str, db: Session = Depends(get_db)):
    """Quick lookup by item code (e.g. 742-1)."""
    item = db.query(TicketItem).filter(TicketItem.item_code == item_code).first()
    if not item:
        raise HTTPException(404, f"Item code {item_code} not found")
    return get_ticket(item.ticket_id, db)


@router.patch("/{ticket_id}/items/{item_id}/state")
def transition_state(
    ticket_id: int,
    item_id: int,
    payload: StateTransitionIn,
    request: Request,
    db: Session = Depends(get_db),
):
    item = db.query(TicketItem).filter(
        TicketItem.id == item_id,
        TicketItem.ticket_id == ticket_id,
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")

    old_state = item.workflow_state

    # ── 1. Validate note và actor bắt buộc ───────────────────────────────────
    if not payload.note or not payload.note.strip():
        raise HTTPException(400, "Bắt buộc phải có ghi chú (note)")
    actor = resolve_actor(request, db, payload.actor, required=True)

    # ── 2. Validate không chuyển về cùng state ───────────────────────────────
    if payload.to_state == old_state:
        raise HTTPException(400, f"Item đang ở trạng thái {old_state.value}, không cần chuyển")

    # ── 3. Validate theo ma trận chuyển trạng thái ───────────────────────────
    allowed = ALLOWED_TRANSITIONS.get(old_state, [])
    if payload.to_state not in allowed:
        allowed_names = ", ".join(s.value for s in allowed) if allowed else "không có"
        raise HTTPException(
            400,
            f"Không thể chuyển từ {old_state.value} → {payload.to_state.value}. "
            f"Chỉ được chuyển sang: {allowed_names}"
        )

    # ── 4. Validate đặc biệt theo từng bước ──────────────────────────────────

    # A3 → B1: bắt buộc đã có phiếu gửi NCC chứa item này
    if old_state == WorkflowState.A3 and payload.to_state == WorkflowState.B1:
        has_order = db.query(SupplierOrderItem).filter(
            SupplierOrderItem.ticket_item_id == item_id
        ).first()
        if not has_order:
            raise HTTPException(
                400,
                "Chưa có phiếu gửi NCC cho sản phẩm này. "
                "Vui lòng tạo phiếu gửi NCC và gửi NCC trước khi chuyển sang B1."
            )

    # C4 → C5: bắt buộc đã có transaction thu tiền
    if old_state == WorkflowState.C4 and payload.to_state == WorkflowState.C5:
        has_posted_thu = db.query(Transaction).filter(
            Transaction.ticket_item_id == item_id,
            Transaction.type == TransactionType.thu,
            Transaction.status == TransactionStatus.posted,
        ).first()
        if item.requires_customer_payment and not has_posted_thu:
            raise HTTPException(
                400,
                "Chưa ghi nhận thu tiền khách. "
                "Vui lòng tạo phiếu thu trước khi chuyển sang C5."
            )

    # C5 → C6: bắt buộc đã có ảnh bằng chứng
    if old_state == WorkflowState.C5 and payload.to_state == WorkflowState.C6:
        if not item.evidence_url:
            raise HTTPException(
                400,
                "Chưa có ảnh bằng chứng đóng gói (C5). "
                "Vui lòng upload ảnh bằng chứng trước khi hoàn thành."
            )

    # Item quá hạn phải báo khách và gia hạn trước khi được chuyển trạng thái tiếp
    today = date.today()
    if (
        item.workflow_state != WorkflowState.C6
        and item.deadline_date is not None
        and item.deadline_date < today
        and not item.notified_late
    ):
        raise HTTPException(
            400,
            "Mã hàng đang trễ hạn và chưa báo khách. Vui lòng thực hiện thao tác thông báo khách hàng/gia hạn trước khi chuyển trạng thái."
        )

    # ── 5. Cập nhật item ──────────────────────────────────────────────────────
    item.workflow_state = payload.to_state

    if payload.diagnosis_note:
        item.diagnosis_note = payload.diagnosis_note
    if payload.expected_return_date:
        item.expected_return_date = payload.expected_return_date
    if old_state == WorkflowState.B4 and payload.to_state == WorkflowState.B2:
        raise HTTPException(400, "B4 chỉ được xử lý qua thao tác chốt báo giá")
    if payload.to_state == WorkflowState.C6:
        item.returned_date = date.today()

    log = WorkflowLog(
        ticket_item_id=item.id,
        from_state=old_state,
        to_state=payload.to_state,
        note=payload.note,
        actor=actor,
    )
    db.add(log)
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


@router.post("/{ticket_id}/items/{item_id}/quote-request")
def create_quote_request(
    ticket_id: int,
    item_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
):
    item = db.query(TicketItem).filter(
        TicketItem.id == item_id,
        TicketItem.ticket_id == ticket_id,
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    if item.workflow_state != WorkflowState.B2:
        raise HTTPException(400, "Chỉ tạo báo giá khi item đang ở B2")

    actor = resolve_actor(request, db, payload.get("actor"), required=True)
    note = (payload.get("note") or "").strip()
    supplier_amount = float(payload.get("supplier_amount") or 0)
    customer_amount = float(payload.get("customer_amount") or 0)
    if supplier_amount <= 0:
        raise HTTPException(400, "Chi phí dự kiến NCC phải lớn hơn 0")
    if customer_amount <= 0:
        raise HTTPException(400, "Số tiền dự kiến thu khách phải lớn hơn 0")
    if _get_quote_transactions(db, item.id):
        raise HTTPException(400, "Item đang có giao dịch báo giá nháp")

    item.workflow_state = WorkflowState.B4
    item.requires_customer_payment = False
    db.add(Transaction(
        ticket_item_id=item.id,
        type=TransactionType.chi,
        status=TransactionStatus.draft,
        amount=supplier_amount,
        note=(payload.get("supplier_note") or note or "Dự kiến chi NCC khi chờ khách chốt báo giá").strip(),
        created_by=actor,
    ))
    db.add(Transaction(
        ticket_item_id=item.id,
        type=TransactionType.thu,
        status=TransactionStatus.draft,
        amount=customer_amount,
        note=(payload.get("customer_note") or note or "Dự kiến thu khách khi chờ khách chốt báo giá").strip(),
        created_by=actor,
    ))
    db.add(WorkflowLog(
        ticket_item_id=item.id,
        from_state=WorkflowState.B2,
        to_state=WorkflowState.B4,
        note=note or "NCC đã báo giá, chờ khách chốt phương án sửa chữa",
        actor=actor,
    ))
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


@router.post("/{ticket_id}/items/{item_id}/quote-decision")
def finalize_quote_decision(
    ticket_id: int,
    item_id: int,
    payload: QuoteDecisionIn,
    request: Request,
    db: Session = Depends(get_db),
):
    item = db.query(TicketItem).filter(
        TicketItem.id == item_id,
        TicketItem.ticket_id == ticket_id,
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    if item.workflow_state != WorkflowState.B4:
        raise HTTPException(400, "Item không ở trạng thái B4")
    if not payload.note or not payload.note.strip():
        raise HTTPException(400, "Bắt buộc phải có ghi chú")

    actor = resolve_actor(request, db, payload.actor, required=True)
    drafts = _get_quote_transactions(db, item.id)
    if len(drafts) < 2:
        raise HTTPException(400, "Thiếu giao dịch nháp của báo giá")

    if payload.customer_approved:
        item.requires_customer_payment = True
        decision_note = f"Khách đồng ý báo giá. {payload.note.strip()}"
    else:
        item.requires_customer_payment = False
        decision_note = f"Khách không đồng ý báo giá. {payload.note.strip()}"
        for txn in drafts:
            txn.status = TransactionStatus.cancelled

    item.workflow_state = WorkflowState.B2
    db.add(WorkflowLog(
        ticket_item_id=item.id,
        from_state=WorkflowState.B4,
        to_state=WorkflowState.B2,
        note=decision_note,
        actor=actor,
    ))
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


@router.get("/{ticket_id}/items/{item_id}/logs")
def get_item_logs(ticket_id: int, item_id: int, db: Session = Depends(get_db)):
    item = db.query(TicketItem).filter(
        TicketItem.id == item_id,
        TicketItem.ticket_id == ticket_id,
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    logs = (
        db.query(WorkflowLog)
        .filter(WorkflowLog.ticket_item_id == item_id)
        .order_by(WorkflowLog.created_at)
        .all()
    )
    return [
        {
            "id": l.id,
            "from_state": l.from_state,
            "to_state": l.to_state,
            "note": l.note,
            "actor": l.actor,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


@router.patch("/{ticket_id}/items/{item_id}/notes")
def update_item_notes(
    ticket_id: int,
    item_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    item = db.query(TicketItem).filter(
        TicketItem.id == item_id,
        TicketItem.ticket_id == ticket_id,
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    for field in ("diagnosis_note", "result_note", "customer_complaint"):
        if field in payload:
            setattr(item, field, payload[field])
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


@router.post("/{ticket_id}/extend-deadline")
def extend_deadline(
    ticket_id: int,
    payload: ExtendDeadlineIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Gia hạn deadline thêm N ngày, ghi log lý do."""
    ticket = db.query(Ticket).options(
        joinedload(Ticket.customer), joinedload(Ticket.items).joinedload(TicketItem.product)
    ).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if payload.extra_days <= 0:
        raise HTTPException(400, "extra_days phải > 0")

    actor = resolve_actor(request, db, payload.actor)
    old_deadline = ticket.deadline_date
    new_deadline = (old_deadline or date.today()) + timedelta(days=payload.extra_days)
    ticket.deadline_date = new_deadline
    ticket.extension_days = (ticket.extension_days or 0) + payload.extra_days

    # Ghi log vào workflow_logs của item đầu tiên (hoặc tất cả)
    for item in ticket.items:
        if item.workflow_state != WorkflowState.C6:
            db.add(WorkflowLog(
                ticket_item_id=item.id,
                from_state=item.workflow_state,
                to_state=item.workflow_state,
                note=f"Gia hạn +{payload.extra_days} ngày. Lý do: {payload.reason}. Deadline mới: {new_deadline.strftime('%d/%m/%Y')}",
                actor=actor,
            ))
            break  # chỉ log 1 lần cho item đầu tiên còn mở

    db.commit()
    return {
        "ok": True,
        "old_deadline": old_deadline.isoformat() if old_deadline else None,
        "new_deadline": new_deadline.isoformat(),
        "extension_days_total": ticket.extension_days,
    }


class RollbackIn(BaseModel):
    reason: str
    actor: Optional[str] = None


@router.post("/{ticket_id}/items/{item_id}/rollback")
def rollback_state(
    ticket_id: int,
    item_id: int,
    payload: RollbackIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Hoàn tác bước cuối của item về trạng thái trước đó."""
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(400, "Bắt buộc phải có lý do hoàn tác")

    actor = resolve_actor(request, db, payload.actor)
    item = db.query(TicketItem).filter(
        TicketItem.id == item_id,
        TicketItem.ticket_id == ticket_id,
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")

    current_state = item.workflow_state

    # Chặn rollback ở trạng thái đầu hoặc cuối
    if current_state == WorkflowState.A1:
        raise HTTPException(400, "Không thể hoàn tác: item đang ở trạng thái ban đầu (A1)")
    if current_state == WorkflowState.C6:
        raise HTTPException(400, "Không thể hoàn tác: item đã hoàn thành (C6), cần quyền admin")

    # Chặn rollback B1 nếu đang trong phiếu NCC status=sent
    if current_state == WorkflowState.B1:
        active_order_item = db.query(SupplierOrderItem).filter(
            SupplierOrderItem.ticket_item_id == item_id
        ).join(SupplierOrderItem.order).filter(
            SupplierOrder.status == SupplierOrderStatus.sent
        ).first()
        if active_order_item:
            raise HTTPException(
                400,
                "Không thể hoàn tác: item đang có trong phiếu NCC đã gửi (status=sent). "
                "Hãy hủy phiếu NCC trước."
            )

    # Lấy 2 log gần nhất có from_state != to_state
    logs = (
        db.query(WorkflowLog)
        .filter(
            WorkflowLog.ticket_item_id == item_id,
            WorkflowLog.from_state != None,
            WorkflowLog.from_state != WorkflowLog.to_state,
        )
        .order_by(WorkflowLog.created_at.desc())
        .limit(2)
        .all()
    )
    if not logs:
        raise HTTPException(400, "Không tìm thấy lịch sử chuyển trạng thái để hoàn tác")

    last_log = logs[0]
    prev_state_str = last_log.from_state

    try:
        prev_state = WorkflowState(prev_state_str)
    except ValueError:
        raise HTTPException(400, f"Trạng thái trước ({prev_state_str}) không hợp lệ")

    # Cập nhật item
    item.workflow_state = prev_state

    db.add(WorkflowLog(
        ticket_item_id=item.id,
        from_state=current_state,
        to_state=prev_state,
        note=f"Hoàn tác: {payload.reason}",
        actor=actor or "system",
    ))
    db.commit()
    db.refresh(item)
    return _serialize_item(item)


@router.post("/{ticket_id}/items/{item_id}/notify-late")
def notify_item_late(
    ticket_id: int,
    item_id: int,
    payload: ItemNotifyLateIn,
    request: Request,
    db: Session = Depends(get_db),
):
    item = db.query(TicketItem).filter(
        TicketItem.id == item_id,
        TicketItem.ticket_id == ticket_id,
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    if item.workflow_state == WorkflowState.C6:
        raise HTTPException(400, "Item đã hoàn thành, không cần báo trễ")
    if not payload.note or not payload.note.strip():
        raise HTTPException(400, "Bắt buộc phải có ghi chú thông báo khách")

    actor = resolve_actor(request, db, payload.actor, required=True)
    old_deadline = item.deadline_date or item.expected_return_date or item.ticket.received_date or date.today()
    new_deadline = payload.new_deadline_date
    extra_days = (new_deadline - old_deadline).days
    if extra_days <= 0:
        raise HTTPException(400, "Ngày gia hạn mới phải lớn hơn deadline hiện tại")

    item.notified_late = True
    item.extension_days = (item.extension_days or 0) + extra_days
    item.deadline_date = new_deadline
    if item.expected_return_date:
        item.expected_return_date = item.expected_return_date + timedelta(days=extra_days)
    else:
        item.expected_return_date = new_deadline

    db.add(WorkflowLog(
        ticket_item_id=item.id,
        from_state=item.workflow_state,
        to_state=item.workflow_state,
        note=(
            f"📞 Đã thông báo khách hàng bị trễ. Gia hạn +{extra_days} ngày. "
            f"Deadline mới: {new_deadline.strftime('%d/%m/%Y')}. Ghi chú: {payload.note.strip()}"
        ),
        actor=actor,
    ))
    db.commit()
    db.refresh(item)
    return {
        "ok": True,
        "item": _serialize_item(item),
        "old_deadline": old_deadline.isoformat() if old_deadline else None,
        "new_deadline": new_deadline.isoformat(),
    }


def notify_late(
    ticket_id: int,
    payload: NotifyLateIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Ghi nhận đã gọi báo khách trễ."""
    ticket = db.query(Ticket).options(
        joinedload(Ticket.customer), joinedload(Ticket.items).joinedload(TicketItem.product)
    ).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    actor = resolve_actor(request, db, payload.actor)
    ticket.notified_late = True

    note_text = payload.note or "Đã gọi báo khách hàng về việc trễ hạn"
    for item in ticket.items:
        if item.workflow_state != WorkflowState.C6:
            db.add(WorkflowLog(
                ticket_item_id=item.id,
                from_state=item.workflow_state,
                to_state=item.workflow_state,
                note=f"📞 {note_text}",
                actor=actor,
            ))
            break

    db.commit()
    return {"ok": True, "notified_late": True}
