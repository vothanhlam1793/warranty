"""Transactions router - thu/chi nội bộ và báo cáo."""

from __future__ import annotations

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from ..database import get_db
from ..models import Transaction, TransactionType, TicketItem, WorkflowState, WorkflowLog

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


class TransactionIn(BaseModel):
    ticket_item_id: Optional[int] = None
    type: TransactionType
    amount: float
    note: Optional[str] = None
    created_by: Optional[str] = None


def _serialize(t: Transaction) -> dict:
    return {
        "id": t.id,
        "ticket_item_id": t.ticket_item_id,
        "type": t.type,
        "amount": t.amount,
        "note": t.note,
        "created_by": t.created_by,
        "created_at": t.created_at.isoformat(),
    }


@router.post("", status_code=201)
def create_transaction(payload: TransactionIn, db: Session = Depends(get_db)):
    if payload.ticket_item_id and not db.get(TicketItem, payload.ticket_item_id):
        raise HTTPException(404, "TicketItem not found")
    t = Transaction(**payload.model_dump())
    db.add(t)
    db.flush()

    # C4 → C5 tự động khi ghi transaction thu
    if payload.ticket_item_id and payload.type == TransactionType.thu:
        ti = db.get(TicketItem, payload.ticket_item_id)
        if ti and ti.workflow_state == WorkflowState.C4:
            ti.workflow_state = WorkflowState.C5
            db.add(WorkflowLog(
                ticket_item_id=ti.id,
                from_state=WorkflowState.C4,
                to_state=WorkflowState.C5,
                note=f"Đã ghi nhận thu tiền – tự động chuyển C5",
                actor=payload.created_by,
            ))

    db.commit()
    db.refresh(t)
    return _serialize(t)


@router.get("")
def list_transactions(
    ticket_item_id: Optional[int] = Query(None),
    type: Optional[TransactionType] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Transaction).order_by(Transaction.created_at.desc())
    if ticket_item_id:
        query = query.filter(Transaction.ticket_item_id == ticket_item_id)
    if type:
        query = query.filter(Transaction.type == type)
    return [_serialize(t) for t in query.limit(200).all()]


@router.get("/report")
def report(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Transaction)
    if from_date:
        query = query.filter(func.date(Transaction.created_at) >= from_date)
    if to_date:
        query = query.filter(func.date(Transaction.created_at) <= to_date)

    transactions = query.all()
    total_thu = sum(t.amount for t in transactions if t.type == TransactionType.thu)
    total_chi = sum(t.amount for t in transactions if t.type == TransactionType.chi)

    # Dashboard stats
    total_tickets = db.query(TicketItem).count()
    open_tickets = db.query(TicketItem).filter(TicketItem.workflow_state != WorkflowState.C6).count()
    done_tickets = db.query(TicketItem).filter(TicketItem.workflow_state == WorkflowState.C6).count()

    state_counts = {}
    for state in WorkflowState:
        count = db.query(TicketItem).filter(TicketItem.workflow_state == state).count()
        if count:
            state_counts[state.value] = count

    return {
        "total_thu": total_thu,
        "total_chi": total_chi,
        "profit": total_thu - total_chi,
        "transaction_count": len(transactions),
        "stats": {
            "total_items": total_tickets,
            "open_items": open_tickets,
            "done_items": done_tickets,
            "by_state": state_counts,
        },
        "transactions": [_serialize(t) for t in transactions],
    }


@router.get("/{ticket_id}/print", )
def print_return_slip(ticket_id: int, db: Session = Depends(get_db)):
    """Generate return slip HTML for a ticket."""
    from ..models import Ticket
    from fastapi.responses import HTMLResponse

    ticket = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.customer),
            joinedload(Ticket.items).joinedload(TicketItem.product),
        )
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    rows = ""
    total = 0.0
    for idx, item in enumerate(ticket.items, 1):
        txns = db.query(Transaction).filter(
            Transaction.ticket_item_id == item.id,
            Transaction.type == TransactionType.thu,
        ).all()
        cost = sum(t.amount for t in txns)
        total += cost
        cost_str = f"{cost:,.0f}đ" if cost else "Miễn phí"
        rows += f"""
        <tr>
          <td>{idx}</td>
          <td><b>{item.item_code or ''}</b></td>
          <td>{item.product.name if item.product else ''}</td>
          <td>{item.serial_no or ''}</td>
          <td>{item.result_note or item.diagnosis_note or ''}</td>
          <td style="text-align:right">{cost_str}</td>
        </tr>"""

    cust = ticket.customer
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
  <title>Phiếu trả khách - {ticket.ticket_no}</title>
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
    .meta-row{{display:flex; gap:8px}}
    .meta-label{{color:#6b7280; min-width:120px; font-weight:600}}
    table{{width:100%; border-collapse:collapse; margin-top:8px}}
    th,td{{border:1px solid #cbd5e1; padding:9px 10px; text-align:left; vertical-align:top}}
    th{{background:#eef6f3; font-weight:700}}
    .total-row td{{font-weight:800; background:#f0faf6}}
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
    <h1>PHIẾU TRẢ HÀNG KHÁCH</h1>
    <div class="subtitle">Số phiếu: <b>{ticket.ticket_no}</b> &nbsp;|&nbsp; Ngày in: {date.today().strftime('%d/%m/%Y')}</div>
  </div>
  <div class="meta">
    <div class="meta-row"><span class="meta-label">Khách hàng:</span><b>{cust.name if cust else ''}</b></div>
    <div class="meta-row"><span class="meta-label">Điện thoại:</span>{cust.phone or '' if cust else ''}</div>
    <div class="meta-row"><span class="meta-label">Địa chỉ:</span>{cust.address or '' if cust else ''}</div>
    <div class="meta-row"><span class="meta-label">Ngày nhận:</span>{ticket.received_date.strftime('%d/%m/%Y')}</div>
    <div class="meta-row"><span class="meta-label">Ngày trả:</span>{date.today().strftime('%d/%m/%Y')}</div>
    <div class="meta-row"><span class="meta-label">Ghi chú:</span>{ticket.note or ''}</div>
  </div>
  <table>
    <thead><tr><th>#</th><th>Mã xử lý</th><th>Tên sản phẩm</th><th>Serial</th><th>Kết quả xử lý</th><th>Chi phí</th></tr></thead>
    <tbody>
      {rows}
      <tr class="total-row">
        <td colspan="5" style="text-align:right">TỔNG CỘNG</td>
        <td style="text-align:right">{total:,.0f}đ</td>
      </tr>
    </tbody>
  </table>
  <div class="footer">
    <div class="sign"><div class="sign-label">Đại diện CRETA</div><div>__________________</div></div>
    <div class="sign"><div class="sign-label">Khách hàng ký nhận</div><div>__________________</div></div>
  </div>
</body>
</html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)
