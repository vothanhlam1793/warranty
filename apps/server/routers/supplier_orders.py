"""Supplier orders router - gửi NCC, tiếp nhận trả về, in phiếu."""

import os, shutil, uuid
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from .auth import resolve_actor
from ..models import (
    SupplierOrder, SupplierOrderItem, SupplierOrderStatus,
    TicketItem, Supplier, WorkflowLog, WorkflowState,
)

router = APIRouter(prefix="/api/supplier-orders", tags=["supplier-orders"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class SupplierOrderItemIn(BaseModel):
    ticket_item_id: int


class SupplierOrderIn(BaseModel):
    supplier_id: int
    note: Optional[str] = None
    actor: Optional[str] = None
    items: List[SupplierOrderItemIn]


class SendOrderIn(BaseModel):
    actor: Optional[str] = None
    evidence_url: str   # bắt buộc — ảnh bằng chứng đã gửi NCC
    note: Optional[str] = None


class ReceiveBackItemIn(BaseModel):
    ticket_item_id: int
    result: str  # doi_moi / sua_duoc / tra_xac / dang_xu_ly
    result_note: Optional[str] = None


class ReceiveBackIn(BaseModel):
    received_date: date
    items: List[ReceiveBackItemIn]
    actor: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _next_order_no(db: Session) -> str:
    last = db.query(SupplierOrder).order_by(SupplierOrder.id.desc()).first()
    num = (last.id + 1) if last else 1
    return f"NCC-{num:04d}"


def _serialize_order(order: SupplierOrder) -> dict:
    return {
        "id": order.id,
        "order_no": order.order_no,
        "supplier_id": order.supplier_id,
        "supplier_name": order.supplier.name if order.supplier else None,
        "status": order.status,
        "sent_date": order.sent_date.isoformat() if order.sent_date else None,
        "received_date": order.received_date.isoformat() if order.received_date else None,
        "evidence_url": order.evidence_url,
        "note": order.note,
        "created_at": order.created_at.isoformat(),
        "items": [
            {
                "id": oi.id,
                "ticket_item_id": oi.ticket_item_id,
                "ticket_no": oi.ticket_item.ticket.ticket_no if oi.ticket_item and oi.ticket_item.ticket else None,
                "product_name": oi.ticket_item.product.name if oi.ticket_item and oi.ticket_item.product else None,
                "serial_no": oi.ticket_item.serial_no if oi.ticket_item else None,
                "customer_complaint": oi.ticket_item.customer_complaint if oi.ticket_item else None,
                "result": oi.result,
                "result_note": oi.result_note,
                "received_back": oi.received_back,
            }
            for oi in order.items
        ],
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_order(payload: SupplierOrderIn, request: Request, db: Session = Depends(get_db)):
    actor = resolve_actor(request, db, payload.actor, required=True)
    if not db.get(Supplier, payload.supplier_id):
        raise HTTPException(404, "Supplier not found")

    order = SupplierOrder(
        order_no=_next_order_no(db),
        supplier_id=payload.supplier_id,
        note=payload.note,
        status=SupplierOrderStatus.draft,
    )
    db.add(order)
    db.flush()

    for oi_in in payload.items:
        ti = db.get(TicketItem, oi_in.ticket_item_id)
        if not ti:
            raise HTTPException(404, f"TicketItem {oi_in.ticket_item_id} not found")
        # Validate item phải ở A3 mới được đưa vào phiếu gửi NCC
        if ti.workflow_state != WorkflowState.A3:
            raise HTTPException(
                400,
                f"Mã hàng {ti.item_code or ti.id} đang ở trạng thái {ti.workflow_state.value}, "
                f"phải ở A3 (Sẵn sàng gửi NCC) mới có thể thêm vào phiếu."
            )
        oi = SupplierOrderItem(order_id=order.id, ticket_item_id=oi_in.ticket_item_id)
        db.add(oi)
        # A3 → B1 tự động
        old = ti.workflow_state
        ti.workflow_state = WorkflowState.B1
        db.add(WorkflowLog(
            ticket_item_id=ti.id,
            from_state=old,
            to_state=WorkflowState.B1,
            note=f"Đã đưa vào phiếu gửi NCC",
            actor=actor,
        ))

    db.commit()
    db.refresh(order)
    order = db.query(SupplierOrder).options(
        joinedload(SupplierOrder.supplier),
        joinedload(SupplierOrder.items).joinedload(SupplierOrderItem.ticket_item)
            .joinedload(TicketItem.product),
        joinedload(SupplierOrder.items).joinedload(SupplierOrderItem.ticket_item)
            .joinedload(TicketItem.ticket),
    ).filter(SupplierOrder.id == order.id).first()
    return _serialize_order(order)


@router.get("/sent")
def list_sent_orders(db: Session = Depends(get_db)):
    """Lấy tất cả phiếu đang chờ nhận về (status=sent)."""
    orders = (
        db.query(SupplierOrder)
        .options(
            joinedload(SupplierOrder.supplier),
            joinedload(SupplierOrder.items).joinedload(SupplierOrderItem.ticket_item)
                .joinedload(TicketItem.product),
            joinedload(SupplierOrder.items).joinedload(SupplierOrderItem.ticket_item)
                .joinedload(TicketItem.ticket),
        )
        .filter(SupplierOrder.status == SupplierOrderStatus.sent)
        .order_by(SupplierOrder.id.desc())
        .all()
    )
    return [_serialize_order(o) for o in orders]


@router.get("")
def list_orders(db: Session = Depends(get_db)):
    orders = (
        db.query(SupplierOrder)
        .options(
            joinedload(SupplierOrder.supplier),
            joinedload(SupplierOrder.items).joinedload(SupplierOrderItem.ticket_item)
                .joinedload(TicketItem.product),
            joinedload(SupplierOrder.items).joinedload(SupplierOrderItem.ticket_item)
                .joinedload(TicketItem.ticket),
        )
        .order_by(SupplierOrder.id.desc())
        .all()
    )
    return [_serialize_order(o) for o in orders]


@router.get("/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = (
        db.query(SupplierOrder)
        .options(
            joinedload(SupplierOrder.supplier),
            joinedload(SupplierOrder.items).joinedload(SupplierOrderItem.ticket_item)
                .joinedload(TicketItem.product),
            joinedload(SupplierOrder.items).joinedload(SupplierOrderItem.ticket_item)
                .joinedload(TicketItem.ticket),
        )
        .filter(SupplierOrder.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(404, "Order not found")
    return _serialize_order(order)


UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")


@router.post("/{order_id}/send")
def mark_sent(order_id: int, payload: SendOrderIn, request: Request, db: Session = Depends(get_db)):
    actor = resolve_actor(request, db, payload.actor, required=True)
    order = db.get(SupplierOrder, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status != SupplierOrderStatus.draft:
        raise HTTPException(400, "Phiếu đã được gửi trước đó")
    if not payload.evidence_url.strip() or not payload.evidence_url.startswith("/uploads/"):
        raise HTTPException(400, "Cần có ảnh bằng chứng hợp lệ trước khi xác nhận gửi NCC")

    order.status = SupplierOrderStatus.sent
    order.sent_date = date.today()
    order.evidence_url = payload.evidence_url  # lưu ảnh bằng chứng vào phiếu
    if payload.note and payload.note.strip():
        order.note = payload.note.strip()

    # B1 → B2 tự động cho tất cả items trong phiếu
    for oi in order.items:
        ti = oi.ticket_item
        if ti and ti.workflow_state == WorkflowState.B1:
            ti.workflow_state = WorkflowState.B2
            db.add(WorkflowLog(
                ticket_item_id=ti.id,
                from_state=WorkflowState.B1,
                to_state=WorkflowState.B2,
                note=f"Đã gửi NCC – phiếu {order.order_no}",
                actor=actor,
            ))
    db.commit()
    return {"status": "sent"}


@router.post("/{order_id}/upload-evidence")
async def upload_order_evidence(order_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload ảnh bằng chứng cho phiếu gửi NCC (dùng trước khi gọi /send)."""
    order = db.get(SupplierOrder, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    fname = f"ncc_{order_id}_{uuid.uuid4().hex[:8]}{ext}"
    fpath = os.path.join(UPLOADS_DIR, fname)
    with open(fpath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    url = f"/uploads/{fname}"
    return {"url": url}


@router.post("/{order_id}/receive-back")
def receive_back(order_id: int, payload: ReceiveBackIn, request: Request, db: Session = Depends(get_db)):
    actor = resolve_actor(request, db, payload.actor)
    order = db.get(SupplierOrder, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    item_map = {oi.ticket_item_id: oi for oi in order.items}

    for rb in payload.items:
        oi = item_map.get(rb.ticket_item_id)
        if not oi:
            continue
        oi.result = rb.result
        oi.result_note = rb.result_note
        oi.received_back = True
        ti = oi.ticket_item
        if ti:
            old = ti.workflow_state
            ti.workflow_state = WorkflowState.C1
            ti.result_note = rb.result_note
            db.add(WorkflowLog(
                ticket_item_id=ti.id, from_state=old, to_state=WorkflowState.C1,
                note=f"NCC trả về: {rb.result}. {rb.result_note or ''}",
                actor=actor,
            ))

    all_received = all(oi.received_back for oi in order.items)
    if all_received:
        order.status = SupplierOrderStatus.received
        order.received_date = payload.received_date

    db.commit()
    return {"status": "received", "all_received": all_received}


@router.get("/{order_id}/print", response_class=HTMLResponse)
def print_order(order_id: int, db: Session = Depends(get_db)):
    order = (
        db.query(SupplierOrder)
        .options(
            joinedload(SupplierOrder.supplier),
            joinedload(SupplierOrder.items).joinedload(SupplierOrderItem.ticket_item)
                .joinedload(TicketItem.product),
            joinedload(SupplierOrder.items).joinedload(SupplierOrderItem.ticket_item)
                .joinedload(TicketItem.ticket),
        )
        .filter(SupplierOrder.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(404, "Order not found")

    sup = order.supplier
    rows = ""
    for idx, oi in enumerate(order.items, 1):
        ti = oi.ticket_item
        rows += f"""
        <tr>
          <td>{idx}</td>
          <td>{ti.ticket.ticket_no if ti and ti.ticket else ''}</td>
          <td><b>{ti.item_code or ''}</b></td>
          <td>{ti.product.name if ti and ti.product else ''}</td>
          <td>{ti.serial_no or ''}</td>
          <td>{ti.customer_complaint or ''}</td>
        </tr>"""

    company_block = """
      <div class=\"brand\">
        <img src=\"/uploads/creta-logo.png\" alt=\"CRETA\" class=\"logo\"/>
        <div class=\"company-block\">
          <div class=\"company-name\">CÔNG TY TNHH GIẢI PHÁP CÔNG NGHỆ CRETA</div>
          <div class=\"company-sub\">Phòng Kỹ thuật (Bảo hành)</div>
          <div>Điện thoại: 0909 856 315 / Zalo: 0935 107 509</div>
          <div>Địa chỉ: 572/15A7 Âu Cơ, Phường Bảy Hiền, Hồ Chí Minh</div>
        </div>
      </div>
    """

    html = f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="UTF-8"/>
  <title>Phiếu gửi NCC - {order.order_no}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&display=swap');
    *{{box-sizing:border-box; margin:0; padding:0}}
    @page{{size:A4 portrait; margin:12mm}}
    html,body{{width:210mm; min-height:297mm}}
    body{{font-family:'Manrope',sans-serif; font-size:13px; color:#1f2937; padding:10mm 12mm; margin:0 auto}}
    .header{{display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin-bottom:14px; padding-bottom:12px; border-bottom:2px solid #0e7c66}}
    .brand{{display:flex; align-items:flex-start; gap:14px; max-width:78%}}
    .logo{{width:70px; height:70px; object-fit:contain; flex:0 0 auto}}
    .company-block{{line-height:1.5}}
    .company-name{{font-size:18px; font-weight:800; color:#0f172a; text-transform:uppercase}}
    .company-sub{{font-weight:700; color:#0e7c66}}
    .print-btn{{padding:8px 16px;background:#0e7c66;color:#fff;border:none;border-radius:6px;cursor:pointer}}
    .title{{text-align:center; margin-bottom:18px}}
    h1{{font-size:20px; font-weight:800; letter-spacing:.04em}}
    .subtitle{{color:#4b5563; margin-top:6px}}
    .meta{{display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:18px; border:1px solid #d1d5db; border-radius:10px; padding:14px 16px; background:#f8fafc}}
    .meta-row{{display:flex; gap:8px; align-items:flex-start}}
    .meta-label{{color:#6b7280; min-width:118px; font-weight:600}}
    table{{width:100%; border-collapse:collapse; margin-top:8px}}
    th,td{{border:1px solid #cbd5e1; padding:9px 10px; text-align:left; vertical-align:top}}
    th{{background:#eef6f3; font-weight:700}}
    .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-weight:700; color:#0e7c66}}
    .footer{{margin-top:32px; display:flex; justify-content:space-between}}
    .sign{{text-align:center; width:220px}}
    .sign-label{{font-size:11px; color:#6b7280; margin-bottom:52px; text-transform:uppercase}}
    @media print{{html,body{{width:auto;min-height:auto}} body{{padding:0}} button{{display:none}}}}
  </style>
</head>
<body>
  <div class="header">
    {company_block}
    <button onclick="window.print()" class="print-btn">In phiếu</button>
  </div>
  <div class="title">
    <h1>PHIẾU GỬI NHÀ CUNG CẤP</h1>
    <div class="subtitle">Số phiếu: <b>{order.order_no}</b> &nbsp;|&nbsp; Ngày in: {date.today().strftime('%d/%m/%Y')} &nbsp;|&nbsp; Trạng thái: <b>{order.status.value}</b></div>
  </div>
  <div class="meta">
    <div class="meta-row"><span class="meta-label">Nhà cung cấp:</span><b>{sup.name if sup else ''}</b></div>
    <div class="meta-row"><span class="meta-label">Người liên hệ:</span>{sup.contact_name or '' if sup else ''}</div>
    <div class="meta-row"><span class="meta-label">Điện thoại:</span>{sup.phone or '' if sup else ''}</div>
    <div class="meta-row"><span class="meta-label">Địa chỉ:</span>{sup.address or '' if sup else ''}</div>
    <div class="meta-row"><span class="meta-label">Ghi chú:</span>{order.note or ''}</div>
  </div>
  <table>
    <thead><tr><th>#</th><th>Phiếu BH</th><th>Mã xử lý</th><th>Tên sản phẩm</th><th>Serial</th><th>Lỗi / Yêu cầu</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <div class="footer">
    <div class="sign"><div class="sign-label">Đại diện CRETA</div><div>__________________</div></div>
    <div class="sign"><div class="sign-label">Đại diện NCC</div><div>__________________</div></div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)
