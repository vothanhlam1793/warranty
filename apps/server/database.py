"""Database setup - Supporting SQLite and PostgreSQL."""

from __future__ import annotations

import os
from datetime import datetime, time
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase, joinedload, sessionmaker

# Load .env từ root project (2 cấp trên apps/server/)
_ROOT = Path(__file__).resolve().parents[2]
_env_file = _ROOT / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    DB_PATH = os.environ.get("WARRANTY_DB", str(_ROOT / "apps" / "server" / "warranty.db"))
    DATABASE_URL = f"sqlite:///{DB_PATH}"

# Connection arguments
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables and seed data."""
    import importlib
    importlib.import_module(".models", package="server")
    Base.metadata.create_all(bind=engine)
    
    # Manual compatibility patches for legacy databases.
    if DATABASE_URL.startswith("sqlite"):
        with engine.begin() as conn:
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info(ticket_items)"))]
            if "a2_required" not in cols:
                conn.execute(text("ALTER TABLE ticket_items ADD COLUMN a2_required BOOLEAN DEFAULT 0"))
            if "a2_template_id" not in cols:
                conn.execute(text("ALTER TABLE ticket_items ADD COLUMN a2_template_id INTEGER"))
            if "c1_template_id" not in cols:
                conn.execute(text("ALTER TABLE ticket_items ADD COLUMN c1_template_id INTEGER"))
            if "a2_template_locked" not in cols:
                conn.execute(text("ALTER TABLE ticket_items ADD COLUMN a2_template_locked BOOLEAN DEFAULT 0"))
            if "c1_template_locked" not in cols:
                conn.execute(text("ALTER TABLE ticket_items ADD COLUMN c1_template_locked BOOLEAN DEFAULT 0"))
            if "delivery_confirm_note" not in cols:
                conn.execute(text("ALTER TABLE ticket_items ADD COLUMN delivery_confirm_note TEXT"))
            if "shipping_note" not in cols:
                conn.execute(text("ALTER TABLE ticket_items ADD COLUMN shipping_note TEXT"))
            if "deadline_date" not in cols:
                conn.execute(text("ALTER TABLE ticket_items ADD COLUMN deadline_date DATE"))
            if "extension_days" not in cols:
                conn.execute(text("ALTER TABLE ticket_items ADD COLUMN extension_days INTEGER DEFAULT 0"))
            if "notified_late" not in cols:
                conn.execute(text("ALTER TABLE ticket_items ADD COLUMN notified_late BOOLEAN DEFAULT 0"))
            if "requires_customer_payment" not in cols:
                conn.execute(text("ALTER TABLE ticket_items ADD COLUMN requires_customer_payment BOOLEAN DEFAULT 0"))

            txn_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(transactions)"))]
            if txn_cols and "status" not in txn_cols:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN status VARCHAR(20) DEFAULT 'posted'"))
                conn.execute(text("UPDATE transactions SET status = 'posted' WHERE status IS NULL OR status = ''"))
            
            slip_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(return_slips)"))]
            if slip_cols and "return_method" not in slip_cols:
                conn.execute(text("ALTER TABLE return_slips ADD COLUMN return_method TEXT"))
            customer_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(customers)"))]
            if "customer_code" not in customer_cols:
                conn.execute(text("ALTER TABLE customers ADD COLUMN customer_code TEXT"))
    else:
        with engine.begin() as conn:
            customer_col = conn.execute(text("""
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'customers' AND column_name = 'customer_code'
                LIMIT 1
            """)).first()
            if not customer_col:
                conn.execute(text("ALTER TABLE customers ADD COLUMN customer_code VARCHAR(50)"))

            for col_name, ddl in [
                ("deadline_date", "ALTER TABLE ticket_items ADD COLUMN deadline_date DATE"),
                ("extension_days", "ALTER TABLE ticket_items ADD COLUMN extension_days INTEGER DEFAULT 0"),
                ("notified_late", "ALTER TABLE ticket_items ADD COLUMN notified_late BOOLEAN DEFAULT FALSE"),
                ("requires_customer_payment", "ALTER TABLE ticket_items ADD COLUMN requires_customer_payment BOOLEAN DEFAULT FALSE"),
            ]:
                exists = conn.execute(text(f"""
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'ticket_items' AND column_name = '{col_name}'
                    LIMIT 1
                """)).first()
                if not exists:
                    conn.execute(text(ddl))

            txn_status_exists = conn.execute(text("""
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'transactions' AND column_name = 'status'
                LIMIT 1
            """)).first()
            if not txn_status_exists:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN status VARCHAR(20) DEFAULT 'posted'"))
                conn.execute(text("UPDATE transactions SET status = 'posted' WHERE status IS NULL"))

    from .models import (
        ChecklistStage,
        ChecklistTemplate,
        ChecklistTemplateItem,
        ReturnSlip,
        ReturnSlipItem,
        TicketItem,
        WorkflowState,
    )
    db = SessionLocal()
    try:
        def next_slip_no() -> str:
            last = db.query(ReturnSlip).order_by(ReturnSlip.id.desc()).first()
            num = (last.id + 1) if last else 1
            return f"TK-{datetime.today().strftime('%Y%m')}-{num:04d}"

        def ensure_template(name: str, stage: ChecklistStage, description: str):
            t = db.query(ChecklistTemplate).filter(ChecklistTemplate.name == name).first()
            if not t:
                t = ChecklistTemplate(name=name, stage=stage, description=description)
                db.add(t)
                db.flush()
            return t

        cam_a2 = ensure_template("Camera A2 Pre-check", ChecklistStage.A2_PRECHECK, "Checklist sơ bộ trước gửi NCC")
        cam_c1 = ensure_template("Camera C1 Return-check", ChecklistStage.C1_RETURN, "Checklist kiểm tra sau khi NCC trả")
        dau_c1 = ensure_template("Đầu ghi C1 Return-check", ChecklistStage.C1_RETURN, "Checklist kiểm tra đầu ghi")

        def ensure_items(template_id: int, labels: list[str]):
            existing = db.query(ChecklistTemplateItem).filter(ChecklistTemplateItem.template_id == template_id).count()
            if existing > 0:
                return
            for idx, label in enumerate(labels, start=1):
                db.add(ChecklistTemplateItem(
                    template_id=template_id,
                    label=label,
                    required=True,
                    sort_order=idx,
                    input_type="boolean",
                ))

        ensure_items(cam_a2.id, [
            "Ngoại quan: vỏ máy không trầy, bể, biến dạng",
            "Nguồn: bật nguồn được",
            "Hình ảnh: có tín hiệu hình ảnh",
            "Lỗi mô tả của khách: đã tái hiện được / không tái hiện",
            "Serial: khớp với phiếu",
        ])

        ensure_items(cam_c1.id, [
            "Ngoại quan sau bảo hành",
            "Bật nguồn được",
            "Hình ảnh rõ, đúng thông số",
            "Chức năng chính hoạt động bình thường",
            "Lỗi cũ đã được xử lý",
            "Serial khớp với phiếu",
            "Phụ kiện đầy đủ",
        ])

        ensure_items(dau_c1.id, [
            "Ngoại quan sau bảo hành",
            "Bật nguồn, boot bình thường",
            "Nhận đủ camera theo cấu hình cũ",
            "Ghi hình được",
            "Playback bình thường",
            "HDD nhận đúng dung lượng",
            "Lỗi cũ đã được xử lý",
            "Serial khớp với phiếu",
        ])

        # Backfill logic (optional, for existing items without return slips)
        legacy_items = (
            db.query(TicketItem)
            .options(joinedload(TicketItem.ticket), joinedload(TicketItem.return_slip_items))
            .filter(TicketItem.workflow_state.in_([WorkflowState.C4, WorkflowState.C5, WorkflowState.C6]))
            .all()
        )
        for item in legacy_items:
            if item.return_slip_items:
                continue
            if not item.ticket:
                continue

            delivered_at = None
            if item.workflow_state == WorkflowState.C6 and item.returned_date:
                delivered_at = datetime.combine(item.returned_date, time.min)

            slip = ReturnSlip(
                slip_no=next_slip_no(),
                customer_id=item.ticket.customer_id,
                status=item.workflow_state,
                note=item.diagnosis_note or f"Backfill legacy return slip cho {item.item_code or item.id}",
                shipping_note=item.shipping_note,
                pack_image_url=item.evidence_url if item.workflow_state in (WorkflowState.C4, WorkflowState.C5) else None,
                delivery_note=item.delivery_confirm_note,
                delivered_image_url=item.evidence_url if item.workflow_state == WorkflowState.C6 else None,
                created_by="system-backfill",
                created_at=item.created_at,
                packed_at=item.created_at if item.workflow_state in (WorkflowState.C5, WorkflowState.C6) else None,
                delivered_at=delivered_at,
            )
            db.add(slip)
            db.flush()
            db.add(ReturnSlipItem(return_slip_id=slip.id, ticket_item_id=item.id))

        all_items = db.query(TicketItem).options(joinedload(TicketItem.ticket)).all()
        for item in all_items:
            if item.deadline_date is None:
                if item.expected_return_date:
                    item.deadline_date = item.expected_return_date
                elif item.ticket and item.ticket.received_date:
                    item.deadline_date = item.ticket.received_date
            if item.extension_days is None:
                item.extension_days = 0
            if item.notified_late is None:
                item.notified_late = False

        db.commit()
    finally:
        db.close()
