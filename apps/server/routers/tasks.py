"""Tasks router - danh sách việc cần làm theo trạng thái, upload bằng chứng."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import TicketItem, WorkflowLog, WorkflowState, Ticket, Customer, Product, ChecklistRun, ChecklistStage, ChecklistConclusion

router = APIRouter(tags=["tasks"])

# Thư mục lưu ảnh bằng chứng
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _days_since(dt: Optional[datetime]) -> int:
    """Số ngày kể từ một thời điểm đến hôm nay."""
    if not dt:
        return 0
    delta = datetime.utcnow() - dt
    return delta.days


def _working_days_since(dt: Optional[datetime]) -> int:
    """Số ngày làm việc từ dt đến hôm nay, bỏ qua Chủ nhật."""
    if not dt:
        return 0
    start = dt.date()
    end = date.today()
    if start > end:
        return 0
    days = 0
    cur = start
    from datetime import timedelta
    while cur <= end:
        if cur.weekday() != 6:  # Sunday
            days += 1
        cur += timedelta(days=1)
    return max(days - 1, 0)


def _last_log_date(item: TicketItem, state: str) -> Optional[datetime]:
    """Lấy thời điểm item lần đầu vào state này (workflow_log)."""
    for log in sorted(item.workflow_logs, key=lambda l: l.created_at):
        if log.to_state == state:
            return log.created_at
    return None


def _serialize_task_item(item: TicketItem, days_waiting: int) -> dict:
    ticket = item.ticket
    today = date.today()
    dl = ticket.deadline_date if ticket else None
    days_to_deadline = (dl - today).days if dl else None
    is_deadline_overdue = days_to_deadline is not None and days_to_deadline < 0
    is_urgent = days_to_deadline is not None and 0 <= days_to_deadline <= 2
    return {
        "item_id": item.id,
        "ticket_id": item.ticket_id,
        "ticket_no": ticket.ticket_no if ticket else None,
        "item_code": item.item_code,
        "product_name": item.product.name if item.product else None,
        "serial_no": item.serial_no,
        "customer_name": ticket.customer.name if ticket and ticket.customer else None,
        "customer_phone": ticket.customer.phone if ticket and ticket.customer else None,
        "workflow_state": item.workflow_state,
        "customer_complaint": item.customer_complaint,
        "diagnosis_note": item.diagnosis_note,
        "expected_return_date": item.expected_return_date.isoformat() if item.expected_return_date else None,
        "evidence_url": item.evidence_url,
        "days_waiting": days_waiting,
        "is_overdue": False,  # sẽ set bên dưới tuỳ state
        # Deadline 14 ngày
        "deadline_date": dl.isoformat() if dl else None,
        "days_to_deadline": days_to_deadline,
        "is_deadline_overdue": is_deadline_overdue,
        "is_urgent": is_urgent,
        "extension_days": ticket.extension_days or 0 if ticket else 0,
        "notified_late": bool(ticket.notified_late) if ticket else False,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/api/tasks/pending")
def get_pending_tasks(db: Session = Depends(get_db)):
    """
    Trả về tất cả items đang cần action, nhóm theo trạng thái.
    Không bao gồm C6 (đã hoàn thành).
    """
    # Load tất cả items chưa hoàn thành, kèm relationships
    items = (
        db.query(TicketItem)
        .options(
            joinedload(TicketItem.product),
            joinedload(TicketItem.workflow_logs),
            joinedload(TicketItem.ticket).joinedload(Ticket.customer),
        )
        .filter(TicketItem.workflow_state != WorkflowState.C6)
        .all()
    )

    # Nhóm theo state
    groups: dict[str, list] = {s.value: [] for s in WorkflowState if s != WorkflowState.C6}

    for item in items:
        state = item.workflow_state.value

        # Tính days_waiting từ log gần nhất vào state hiện tại
        # Đặc biệt: B2 tính từ lúc vào B1 (theo yêu cầu)
        if state == "B2":
            log_dt = _last_log_date(item, "B1")
        else:
            log_dt = _last_log_date(item, state)

        days = _working_days_since(log_dt)
        task = _serialize_task_item(item, days)

        # Đánh dấu quá hạn
        if state == "B1" and days > 2:
            task["is_overdue"] = True
        elif state == "B2" and days > 7:
            task["is_overdue"] = True
        elif state == "C5" and days > 2:
            task["is_overdue"] = True
        elif state in ("A1", "A2") and days > 3:
            task["is_overdue"] = True
        elif state == "C1" and days > 2:
            task["is_overdue"] = True

        groups[state].append(task)

    # Sắp xếp: quá hạn lên trên, rồi theo days_waiting giảm dần
    for state in groups:
        groups[state].sort(key=lambda x: (-x["is_overdue"], -x.get("is_deadline_overdue", False), -x["days_waiting"]))

    # Tổng hợp stats
    total_pending = sum(len(v) for v in groups.values())
    total_overdue = sum(1 for lst in groups.values() for x in lst if x["is_overdue"])
    total_deadline_overdue = sum(1 for lst in groups.values() for x in lst if x.get("is_deadline_overdue"))
    total_urgent = sum(1 for lst in groups.values() for x in lst if x.get("is_urgent"))
    total_not_notified = sum(1 for lst in groups.values() for x in lst if x.get("is_deadline_overdue") and not x.get("notified_late"))

    return {
        "total_pending": total_pending,
        "total_overdue": total_overdue,
        "total_deadline_overdue": total_deadline_overdue,
        "total_urgent": total_urgent,
        "total_not_notified": total_not_notified,
        "groups": groups,
    }


@router.post("/api/tickets/{ticket_id}/items/{item_id}/evidence")
async def upload_evidence(
    ticket_id: int,
    item_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload ảnh bằng chứng cho một ticket item (dùng ở B1 và C5)."""
    item = db.query(TicketItem).filter(
        TicketItem.id == item_id,
        TicketItem.ticket_id == ticket_id,
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")

    # Kiểm tra file type
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(400, "Chỉ chấp nhận ảnh JPG, PNG, WEBP")

    # Lưu file
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"item_{item_id}_{int(datetime.utcnow().timestamp())}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Lưu URL vào DB
    item.evidence_url = f"/uploads/{filename}"

    # C5 → C6 tự động khi upload ảnh bằng chứng trả khách
    if item.workflow_state == WorkflowState.C5:
        item.workflow_state = WorkflowState.C6
        from datetime import date as _date
        item.returned_date = _date.today()
        db.add(WorkflowLog(
            ticket_item_id=item.id,
            from_state=WorkflowState.C5,
            to_state=WorkflowState.C6,
            note="Đã upload ảnh bằng chứng trả khách – tự động hoàn thành",
            actor=None,
        ))

    db.commit()
    db.refresh(item)

    return {"evidence_url": item.evidence_url, "filename": filename, "workflow_state": item.workflow_state}


@router.patch("/api/tickets/{ticket_id}/items/{item_id}/quick-state")
def quick_state_change(
    ticket_id: int,
    item_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Chuyển trạng thái nhanh từ dashboard (không cần mở modal)."""
    item = db.query(TicketItem).filter(
        TicketItem.id == item_id,
        TicketItem.ticket_id == ticket_id,
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")

    to_state = payload.get("to_state")
    if not to_state:
        raise HTTPException(400, "to_state required")

    try:
        new_state = WorkflowState(to_state)
    except ValueError:
        raise HTTPException(400, f"Invalid state: {to_state}")

    # Chặn các bước phải đi qua nghiệp vụ cụ thể
    if item.workflow_state == WorkflowState.A3 and new_state == WorkflowState.B1:
        raise HTTPException(400, "A3 -> B1 phải thực hiện qua tạo phiếu gửi NCC")
    if item.workflow_state == WorkflowState.B1 and new_state == WorkflowState.B2:
        raise HTTPException(400, "B1 -> B2 phải thực hiện qua xác nhận gửi phiếu NCC")
    if item.workflow_state == WorkflowState.B2 and new_state == WorkflowState.C1:
        raise HTTPException(400, "B2 -> C1 phải thực hiện qua phiếu nhận về NCC")
    if item.workflow_state == WorkflowState.A2 and new_state == WorkflowState.A3 and item.a2_required:
        has_a2 = db.query(ChecklistRun).filter(
            ChecklistRun.ticket_item_id == item.id,
            ChecklistRun.stage == ChecklistStage.A2_PRECHECK,
            ChecklistRun.conclusion == ChecklistConclusion.completed,
        ).first()
        if not has_a2:
            raise HTTPException(400, "Item yêu cầu A2 checklist completed trước khi sang A3")
    if item.workflow_state == WorkflowState.C1 and new_state in (WorkflowState.C2, WorkflowState.C3):
        has_c1 = db.query(ChecklistRun).filter(
            ChecklistRun.ticket_item_id == item.id,
            ChecklistRun.stage == ChecklistStage.C1_RETURN,
            ChecklistRun.finalized_at != None,
        ).first()
        if not has_c1:
            raise HTTPException(400, "Cần checklist C1 finalized trước khi sang C2/C3")

    from ..models import WorkflowLog
    old_state = item.workflow_state
    item.workflow_state = new_state

    if new_state == WorkflowState.C6:
        item.returned_date = date.today()

    note = payload.get("note") or f"Chuyển nhanh từ dashboard"
    actor = payload.get("actor") or None

    log = WorkflowLog(
        ticket_item_id=item.id,
        from_state=old_state,
        to_state=new_state,
        note=note,
        actor=actor,
    )
    db.add(log)
    db.commit()
    return {"ok": True, "item_id": item_id, "new_state": new_state}
