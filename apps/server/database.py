"""Database setup - SQLite via SQLAlchemy."""

from __future__ import annotations

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Load .env từ root project (2 cấp trên apps/server/)
_ROOT = Path(__file__).resolve().parents[2]
_env_file = _ROOT / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

DB_PATH = os.environ.get("WARRANTY_DB", str(_ROOT / "apps" / "server" / "warranty.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
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
    """Create all tables."""
    import importlib
    importlib.import_module(".models", package="server")
    Base.metadata.create_all(bind=engine)
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
    from .models import ChecklistTemplate, ChecklistTemplateItem, ChecklistStage
    db = SessionLocal()
    try:
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

        db.commit()
    finally:
        db.close()
