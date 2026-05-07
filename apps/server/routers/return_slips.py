from __future__ import annotations

import os
import shutil
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, Request
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel

from ..database import get_db
from .auth import resolve_actor
from ..models import Customer, ReturnSlip, ReturnSlipItem, Ticket, TicketItem, WorkflowLog, WorkflowState

router = APIRouter(prefix="/api/return-slips", tags=["return-slips"])
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
DEBUG_VERSION = "return-slips-source-2026-05-06-a"


class ReturnSlipCreateIn(BaseModel):
    customer_id: int
    item_ids: list[int]
    actor: Optional[str] = None
    note: str


class ConfirmPackIn(BaseModel):
    actor: Optional[str] = None
    return_method: str
    shipping_note: str


class ConfirmDeliveryIn(BaseModel):
    actor: Optional[str] = None
    delivery_note: Optional[str] = None


def _next_slip_no(db: Session) -> str:
    last = db.query(ReturnSlip).order_by(ReturnSlip.id.desc()).first()
    num = (last.id + 1) if last else 1
    return f"TK-{date.today().strftime('%Y%m')}-{num:04d}"


def _serialize_slip(slip: ReturnSlip) -> dict:
    items = []
    for rs_item in slip.items:
        ti = rs_item.ticket_item
        items.append({
            "id": rs_item.id,
            "ticket_item_id": ti.id if ti else None,
            "item_code": ti.item_code if ti else None,
            "product_name": ti.product.name if ti and ti.product else None,
            "serial_no": ti.serial_no if ti else None,
            "workflow_state": ti.workflow_state if ti else None,
        })
    return {
        "id": slip.id,
        "slip_no": slip.slip_no,
        "customer_id": slip.customer_id,
        "customer_name": slip.customer.name if slip.customer else None,
        "customer_phone": slip.customer.phone if slip.customer else None,
        "status": slip.status,
        "note": slip.note,
        "return_method": slip.return_method,
        "shipping_note": slip.shipping_note,
        "pack_image_url": slip.pack_image_url,
        "delivery_note": slip.delivery_note,
        "delivered_image_url": slip.delivered_image_url,
        "created_by": slip.created_by,
        "created_at": slip.created_at.isoformat() if slip.created_at else None,
        "packed_at": slip.packed_at.isoformat() if slip.packed_at else None,
        "delivered_at": slip.delivered_at.isoformat() if slip.delivered_at else None,
        "items": items,
        "item_count": len(items),
    }


@router.get("/candidates")
def list_candidates(customer_id: int = Query(...), db: Session = Depends(get_db)):
    items = (
        db.query(TicketItem)
        .join(Ticket)
        .options(joinedload(TicketItem.ticket), joinedload(TicketItem.product))
        .filter(
            Ticket.customer_id == customer_id,
            TicketItem.workflow_state.in_([WorkflowState.C2, WorkflowState.C3]),
        )
        .order_by(Ticket.id.desc(), TicketItem.item_no.asc())
        .all()
    )
    return {
        "total": len(items),
        "items": [{
            "id": i.id,
            "ticket_id": i.ticket_id,
            "ticket_no": i.ticket.ticket_no if i.ticket else None,
            "item_code": i.item_code,
            "product_name": i.product.name if i.product else None,
            "serial_no": i.serial_no,
            "workflow_state": i.workflow_state,
        } for i in items],
    }


@router.get("/_debug")
def debug_return_slips_source():
    return {
        "version": DEBUG_VERSION,
        "module_file": __file__,
    }


@router.post("", status_code=201)
def create_return_slip(payload: ReturnSlipCreateIn, request: Request, db: Session = Depends(get_db)):
    actor = resolve_actor(request, db, payload.actor, required=True)
    if not payload.note.strip():
        raise HTTPException(400, "note là bắt buộc")
    if not payload.item_ids:
        raise HTTPException(400, "Cần chọn ít nhất 1 món")
    if not db.get(Customer, payload.customer_id):
        raise HTTPException(404, "Customer not found")

    uniq_ids = sorted(set(payload.item_ids))
    items = (
        db.query(TicketItem)
        .join(Ticket)
        .filter(TicketItem.id.in_(uniq_ids))
        .all()
    )
    if len(items) != len(uniq_ids):
        raise HTTPException(404, "Có item không tồn tại")
    for item in items:
        if item.ticket.customer_id != payload.customer_id:
            raise HTTPException(400, f"Item {item.id} không thuộc khách đã chọn")
        if item.workflow_state not in (WorkflowState.C2, WorkflowState.C3):
            raise HTTPException(400, f"Item {item.item_code or item.id} không ở C2/C3")

    open_slip_items = (
        db.query(ReturnSlipItem)
        .join(ReturnSlip)
        .join(TicketItem)
        .options(joinedload(ReturnSlipItem.return_slip), joinedload(ReturnSlipItem.ticket_item))
        .filter(
            ReturnSlipItem.ticket_item_id.in_(uniq_ids),
            ReturnSlip.status.in_([WorkflowState.C4, WorkflowState.C5]),
        )
        .all()
    )
    if open_slip_items:
        blocked = []
        for rs_item in open_slip_items:
            ti = rs_item.ticket_item
            rs = rs_item.return_slip
            blocked.append(f"{ti.item_code if ti else rs_item.ticket_item_id} đã thuộc phiếu {rs.slip_no if rs else rs_item.return_slip_id}")
        raise HTTPException(400, "; ".join(blocked))

    slip = ReturnSlip(
        slip_no=_next_slip_no(db),
        customer_id=payload.customer_id,
        status=WorkflowState.C4,
        note=payload.note.strip(),
        created_by=actor,
    )
    db.add(slip)
    db.flush()

    today = date.today().isoformat()
    for item in items:
        db.add(ReturnSlipItem(return_slip_id=slip.id, ticket_item_id=item.id))
        old = item.workflow_state
        item.workflow_state = WorkflowState.C4
        db.add(WorkflowLog(
            ticket_item_id=item.id,
            from_state=old,
            to_state=WorkflowState.C4,
            note=f"Lập phiếu trả khách {slip.slip_no} ngày {today}: {payload.note.strip()}",
            actor=actor,
        ))

    db.commit()
    slip = (
        db.query(ReturnSlip)
        .options(
            joinedload(ReturnSlip.customer),
            joinedload(ReturnSlip.items).joinedload(ReturnSlipItem.ticket_item).joinedload(TicketItem.product),
        )
        .filter(ReturnSlip.id == slip.id)
        .first()
    )
    return _serialize_slip(slip)


@router.get("/list")
def list_return_slips(status: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = (
        db.query(ReturnSlip)
        .options(
            joinedload(ReturnSlip.customer),
            joinedload(ReturnSlip.items).joinedload(ReturnSlipItem.ticket_item).joinedload(TicketItem.product),
        )
        .order_by(ReturnSlip.id.desc())
    )
    if status:
        try:
            state = WorkflowState(status)
        except ValueError:
            raise HTTPException(400, f"status không hợp lệ: {status}")
        query = query.filter(ReturnSlip.status == state)
    slips = query.all()
    return {"total": len(slips), "items": [_serialize_slip(s) for s in slips]}


@router.get("/{slip_id}")
def get_return_slip(slip_id: int, db: Session = Depends(get_db)):
    slip = (
        db.query(ReturnSlip)
        .options(
            joinedload(ReturnSlip.customer),
            joinedload(ReturnSlip.items).joinedload(ReturnSlipItem.ticket_item).joinedload(TicketItem.product),
        )
        .filter(ReturnSlip.id == slip_id)
        .first()
    )
    if not slip:
        raise HTTPException(404, "Return slip not found")
    return _serialize_slip(slip)


@router.get("/{slip_id}/print")
def print_return_slip(slip_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import HTMLResponse

    slip = (
        db.query(ReturnSlip)
        .options(
            joinedload(ReturnSlip.customer),
            joinedload(ReturnSlip.items).joinedload(ReturnSlipItem.ticket_item).joinedload(TicketItem.product),
        )
        .filter(ReturnSlip.id == slip_id)
        .first()
    )
    if not slip:
        raise HTTPException(404, "Return slip not found")

    rows = ""
    for idx, rs_item in enumerate(slip.items, 1):
        ti = rs_item.ticket_item
        rows += f"""
        <tr>
          <td>{idx}</td>
          <td><b>{ti.item_code if ti else ''}</b></td>
          <td>{ti.product.name if ti and ti.product else ''}</td>
          <td>{ti.serial_no or '' if ti else ''}</td>
          <td>{ti.diagnosis_note or '' if ti else ''}</td>
        </tr>"""

    cust = slip.customer
    html = f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="UTF-8"/>
  <title>Phiếu trả khách - {slip.slip_no}</title>
  <style>
    body{{font-family:Arial,sans-serif;font-size:13px;color:#222;padding:24px}}
    .header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px}}
    .company{{font-size:20px;font-weight:700;color:#0e7c66}}
    h1{{font-size:18px;margin:0 0 8px 0}}
    .meta{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:20px;border:1px solid #d0d7de;border-radius:8px;padding:12px}}
    table{{width:100%;border-collapse:collapse;margin-top:8px}}
    th,td{{border:1px solid #c9d1d9;padding:8px 10px;text-align:left}}
    th{{background:#f6f8fa}}
    .footer{{margin-top:28px;display:flex;justify-content:space-between}}
    .sign{{text-align:center;width:220px}}
    @media print{{body{{padding:0}} button{{display:none}}}}
  </style>
</head>
<body>
  <div class="header">
    <div class="company">CRETA WARRANTY</div>
    <button onclick="window.print()" style="padding:8px 16px;background:#0e7c66;color:#fff;border:none;border-radius:6px;cursor:pointer">In phiếu</button>
  </div>
  <h1>PHIEU TRA KHACH</h1>
  <div style="color:#666;margin-bottom:14px">So phieu: <b>{slip.slip_no}</b> | Ngay: {date.today().strftime('%d/%m/%Y')}</div>
  <div class="meta">
    <div>Khach hang: <b>{cust.name if cust else ''}</b></div>
    <div>Dien thoai: {cust.phone or '' if cust else ''}</div>
    <div>Phuong thuc tra: {slip.return_method or ''}</div>
    <div>Trang thai: {slip.status.value if slip.status else ''}</div>
    <div style="grid-column:1 / span 2">Ghi chu lap phieu: {slip.note or ''}</div>
    <div style="grid-column:1 / span 2">Thong tin giao van: {slip.shipping_note or ''}</div>
  </div>
  <table>
    <thead><tr><th>#</th><th>Ma xu ly</th><th>San pham</th><th>Serial</th><th>Ghi chu</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <div class="footer">
    <div class="sign"><div>Nguoi dong goi</div><br><br>__________________</div>
    <div class="sign"><div>Khach hang ky nhan</div><br><br>__________________</div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.post("/{slip_id}/pack-image")
async def upload_pack_image(slip_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    slip = db.get(ReturnSlip, slip_id)
    if not slip:
        raise HTTPException(404, "Return slip not found")
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    fname = f"return_pack_{slip_id}_{uuid.uuid4().hex[:8]}{ext}"
    fpath = os.path.join(UPLOAD_DIR, fname)
    with open(fpath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    slip.pack_image_url = f"/uploads/{fname}"
    db.commit()
    return {"ok": True, "url": slip.pack_image_url}


@router.post("/{slip_id}/delivered-image")
async def upload_delivered_image(slip_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    slip = db.get(ReturnSlip, slip_id)
    if not slip:
        raise HTTPException(404, "Return slip not found")
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    fname = f"return_done_{slip_id}_{uuid.uuid4().hex[:8]}{ext}"
    fpath = os.path.join(UPLOAD_DIR, fname)
    with open(fpath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    slip.delivered_image_url = f"/uploads/{fname}"
    db.commit()
    return {"ok": True, "url": slip.delivered_image_url}


@router.post("/{slip_id}/confirm-pack")
def confirm_pack(slip_id: int, payload: ConfirmPackIn, request: Request, db: Session = Depends(get_db)):
    actor = resolve_actor(request, db, payload.actor, required=True)
    slip = db.get(ReturnSlip, slip_id)
    if not slip:
        raise HTTPException(404, "Return slip not found")
    if slip.status != WorkflowState.C4:
        raise HTTPException(400, "Chỉ xác nhận đóng gói khi phiếu đang ở C4")
    if not payload.return_method.strip():
        raise HTTPException(400, "return_method là bắt buộc")
    if not payload.shipping_note.strip():
        raise HTTPException(400, "shipping_note là bắt buộc")
    if not slip.pack_image_url:
        raise HTTPException(400, "Cần có hình ảnh đóng gói trước khi chuyển C5")

    slip.return_method = payload.return_method.strip()
    slip.shipping_note = payload.shipping_note.strip()
    slip.status = WorkflowState.C5
    slip.packed_at = datetime.utcnow()
    for rs_item in slip.items:
        ti = rs_item.ticket_item
        if ti and ti.workflow_state != WorkflowState.C5:
            old = ti.workflow_state
            ti.workflow_state = WorkflowState.C5
            ti.shipping_note = slip.shipping_note
            db.add(WorkflowLog(ticket_item_id=ti.id, from_state=old, to_state=WorkflowState.C5, note=f"Phiếu trả {slip.slip_no} xác nhận đóng gói", actor=actor))
    db.commit()
    return {"ok": True, "slip_id": slip.id, "new_state": slip.status}


@router.post("/{slip_id}/confirm-delivered")
def confirm_delivered(slip_id: int, payload: ConfirmDeliveryIn, request: Request, db: Session = Depends(get_db)):
    actor = resolve_actor(request, db, payload.actor, required=True)
    slip = db.get(ReturnSlip, slip_id)
    if not slip:
        raise HTTPException(404, "Return slip not found")
    if slip.status != WorkflowState.C5:
        raise HTTPException(400, "Chỉ xác nhận giao trả khi phiếu đang ở C5")
    if not slip.delivered_image_url:
        raise HTTPException(400, "Cần có hình ảnh giao trả trước khi chuyển C6")

    slip.delivery_note = (payload.delivery_note or "").strip() or None
    slip.status = WorkflowState.C6
    slip.delivered_at = datetime.utcnow()
    for rs_item in slip.items:
        ti = rs_item.ticket_item
        if ti and ti.workflow_state != WorkflowState.C6:
            old = ti.workflow_state
            ti.workflow_state = WorkflowState.C6
            ti.delivery_confirm_note = slip.delivery_note
            ti.returned_date = date.today()
            db.add(WorkflowLog(ticket_item_id=ti.id, from_state=old, to_state=WorkflowState.C6, note=f"Phiếu trả {slip.slip_no} xác nhận đã giao khách", actor=actor))
    db.commit()
    return {"ok": True, "slip_id": slip.id, "new_state": slip.status}
