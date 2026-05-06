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
    html = f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="UTF-8"/>
  <title>Phiếu trả khách - {ticket.ticket_no}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700&display=swap');
    *{{box-sizing:border-box; margin:0; padding:0}}
    body{{font-family:'Manrope',sans-serif; font-size:13px; color:#1a1a1a; padding:24px}}
    .header{{display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px}}
    .company{{font-size:20px; font-weight:700; color:#0e7c66}}
    .title{{text-align:center; margin-bottom:20px}}
    h1{{font-size:18px; font-weight:700}}
    .meta{{display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:20px;
           border:1px solid #d0d7de; border-radius:8px; padding:12px}}
    .meta-row{{display:flex; gap:8px}}
    .meta-label{{color:#666; min-width:120px}}
    table{{width:100%; border-collapse:collapse; margin-top:8px}}
    th,td{{border:1px solid #c9d1d9; padding:8px 10px; text-align:left}}
    th{{background:#f6f8fa; font-weight:600}}
    .total-row td{{font-weight:700; background:#f0faf6}}
    .footer{{margin-top:30px; display:flex; justify-content:space-between}}
    .sign{{text-align:center; width:200px}}
    .sign-label{{font-size:11px; color:#666; margin-bottom:48px}}
    @media print{{body{{padding:0}} button{{display:none}}}}
  </style>
</head>
<body>
  <div class="header">
    <div class="company">CRETA WARRANTY</div>
    <button onclick="window.print()" style="padding:8px 16px;background:#0e7c66;color:#fff;border:none;border-radius:6px;cursor:pointer">In phiếu</button>
  </div>
  <div class="title">
    <h1>PHIẾU TRẢ HÀNG KHÁCH</h1>
    <p style="color:#666">Số phiếu: <b>{ticket.ticket_no}</b> &nbsp;|&nbsp; Ngày: {date.today().strftime('%d/%m/%Y')}</p>
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
    <div class="sign"><div class="sign-label">Người giao hàng (CRETA)</div><div>__________________</div></div>
    <div class="sign"><div class="sign-label">Khách hàng ký nhận</div><div>__________________</div></div>
  </div>
</body>
</html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)
