"""SQLAlchemy ORM models for Warranty Management System."""

from __future__ import annotations

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    String, Integer, Float, Text, Date, DateTime,
    ForeignKey, Boolean, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base
import enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class RequestedAction(str, enum.Enum):
    bao_hanh  = "bao_hanh"   # Bảo hành
    sua_chua  = "sua_chua"   # Sửa chữa
    tra_hang  = "tra_hang"   # Trả hàng
    doi_moi   = "doi_moi"    # Đổi mới
    hang_muon = "hang_muon"  # Hàng mượn
    khong_ro  = "khong_ro"   # Không rõ


class WorkflowState(str, enum.Enum):
    A1 = "A1"  # Tiếp nhận - test hàng
    A2 = "A2"  # Liên hệ khách chốt xử lý
    A3 = "A3"  # Chuyển NCC
    B1 = "B1"  # NCC đang xử lý
    B2 = "B2"  # Xử lý dài hạn
    C1 = "C1"  # NCC trả về - kiểm tra
    C2 = "C2"  # PASS - chờ trả khách
    C3 = "C3"  # NO PASS - xử lý tiếp
    C4 = "C4"  # Cần thu tiền khách
    C5 = "C5"  # Đã xuất phiếu thanh toán
    C6 = "C6"  # Hoàn thành - đã trả khách


class TransactionType(str, enum.Enum):
    thu = "thu"  # Thu tiền từ khách
    chi = "chi"  # Chi tiền cho NCC hoặc nội bộ


class SupplierOrderStatus(str, enum.Enum):
    draft    = "draft"     # Nháp
    sent     = "sent"      # Đã gửi NCC
    received = "received"  # NCC đã trả về


class SupplierReceiveStatus(str, enum.Enum):
    posted = "posted"


# ─── Master data ──────────────────────────────────────────────────────────────

class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(200))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    email: Mapped[Optional[str]] = mapped_column(String(200))
    address: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    orders: Mapped[List["SupplierOrder"]] = relationship(back_populates="supplier")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    email: Mapped[Optional[str]] = mapped_column(String(200))
    address: Mapped[Optional[str]] = mapped_column(Text)
    kiotviet_id: Mapped[Optional[str]] = mapped_column(String(100))
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tickets: Mapped[List["Ticket"]] = relationship(back_populates="customer")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(100))
    kiotviet_item_id: Mapped[Optional[str]] = mapped_column(String(100))
    kiotviet_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ticket_items: Mapped[List["TicketItem"]] = relationship(back_populates="product")


class ChecklistStage(str, enum.Enum):
    A2_PRECHECK = "A2_PRECHECK"
    C1_RETURN = "C1_RETURN"


class ChecklistConclusion(str, enum.Enum):
    draft = "draft"
    completed = "completed"
    pass_ = "pass"
    fail = "fail"


# ─── Warranty tickets ─────────────────────────────────────────────────────────

class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    deadline_date: Mapped[Optional[date]] = mapped_column(Date)           # received_date + 14 (+ extension)
    extension_days: Mapped[int] = mapped_column(Integer, default=0)       # số ngày đã gia hạn cộng dồn
    notified_late: Mapped[bool] = mapped_column(Boolean, default=False)   # đã gọi báo khách trễ chưa
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="tickets")
    items: Mapped[List["TicketItem"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")


class TicketItem(Base):
    __tablename__ = "ticket_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    item_no: Mapped[int] = mapped_column(Integer, nullable=False)          # 1, 2, 3...
    item_code: Mapped[Optional[str]] = mapped_column(String(50), index=True)  # e.g. 742-1
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    serial_no: Mapped[Optional[str]] = mapped_column(String(200))
    qty: Mapped[int] = mapped_column(Integer, default=1)
    requested_action: Mapped[RequestedAction] = mapped_column(
        SAEnum(RequestedAction), default=RequestedAction.bao_hanh
    )
    workflow_state: Mapped[WorkflowState] = mapped_column(
        SAEnum(WorkflowState), default=WorkflowState.A1
    )
    customer_complaint: Mapped[Optional[str]] = mapped_column(Text)  # Yêu cầu khách
    diagnosis_note: Mapped[Optional[str]] = mapped_column(Text)      # Kỹ thuật ghi chú
    result_note: Mapped[Optional[str]] = mapped_column(Text)         # Kết quả xử lý
    expected_return_date: Mapped[Optional[date]] = mapped_column(Date)
    returned_date: Mapped[Optional[date]] = mapped_column(Date)
    evidence_url: Mapped[Optional[str]] = mapped_column(Text)        # Ảnh bằng chứng (B1/C5)
    a2_required: Mapped[bool] = mapped_column(Boolean, default=False)
    a2_template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("checklist_templates.id"))
    c1_template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("checklist_templates.id"))
    a2_template_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    c1_template_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ticket: Mapped["Ticket"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="ticket_items")
    workflow_logs: Mapped[List["WorkflowLog"]] = relationship(back_populates="ticket_item", cascade="all, delete-orphan")
    supplier_order_items: Mapped[List["SupplierOrderItem"]] = relationship(back_populates="ticket_item")
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="ticket_item")
    a2_template: Mapped[Optional["ChecklistTemplate"]] = relationship(foreign_keys=[a2_template_id])
    c1_template: Mapped[Optional["ChecklistTemplate"]] = relationship(foreign_keys=[c1_template_id])


class ChecklistTemplate(Base):
    __tablename__ = "checklist_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    stage: Mapped[ChecklistStage] = mapped_column(SAEnum(ChecklistStage), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[List["ChecklistTemplateItem"]] = relationship(back_populates="template", cascade="all, delete-orphan")


class ChecklistTemplateItem(Base):
    __tablename__ = "checklist_template_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("checklist_templates.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    input_type: Mapped[str] = mapped_column(String(20), default="boolean")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    template: Mapped["ChecklistTemplate"] = relationship(back_populates="items")


class ChecklistTemplateChange(Base):
    __tablename__ = "checklist_template_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_item_id: Mapped[int] = mapped_column(ForeignKey("ticket_items.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(10), nullable=False)
    from_template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("checklist_templates.id"))
    to_template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("checklist_templates.id"))
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChecklistRun(Base):
    __tablename__ = "checklist_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_item_id: Mapped[int] = mapped_column(ForeignKey("ticket_items.id"), nullable=False)
    template_id: Mapped[int] = mapped_column(ForeignKey("checklist_templates.id"), nullable=False)
    stage: Mapped[ChecklistStage] = mapped_column(SAEnum(ChecklistStage), nullable=False)
    inspector: Mapped[Optional[str]] = mapped_column(String(100))
    note: Mapped[Optional[str]] = mapped_column(Text)
    conclusion: Mapped[ChecklistConclusion] = mapped_column(SAEnum(ChecklistConclusion), default=ChecklistConclusion.draft)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class ChecklistRunItem(Base):
    __tablename__ = "checklist_run_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("checklist_runs.id"), nullable=False)
    template_item_id: Mapped[int] = mapped_column(ForeignKey("checklist_template_items.id"), nullable=False)
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    value_text: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text)


class ChecklistEvidence(Base):
    __tablename__ = "checklist_evidences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("checklist_runs.id"), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ─── Workflow audit ───────────────────────────────────────────────────────────

class WorkflowLog(Base):
    __tablename__ = "workflow_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_item_id: Mapped[int] = mapped_column(ForeignKey("ticket_items.id"), nullable=False)
    from_state: Mapped[Optional[str]] = mapped_column(String(10))
    to_state: Mapped[str] = mapped_column(String(10), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    actor: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ticket_item: Mapped["TicketItem"] = relationship(back_populates="workflow_logs")


# ─── Supplier orders ──────────────────────────────────────────────────────────

class SupplierOrder(Base):
    __tablename__ = "supplier_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    status: Mapped[SupplierOrderStatus] = mapped_column(
        SAEnum(SupplierOrderStatus), default=SupplierOrderStatus.draft
    )
    sent_date: Mapped[Optional[date]] = mapped_column(Date)
    received_date: Mapped[Optional[date]] = mapped_column(Date)
    evidence_url: Mapped[Optional[str]] = mapped_column(Text)        # Ảnh bằng chứng đã gửi NCC
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    supplier: Mapped["Supplier"] = relationship(back_populates="orders")
    items: Mapped[List["SupplierOrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class SupplierOrderItem(Base):
    __tablename__ = "supplier_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("supplier_orders.id"), nullable=False)
    ticket_item_id: Mapped[int] = mapped_column(ForeignKey("ticket_items.id"), nullable=False)
    result: Mapped[Optional[str]] = mapped_column(String(100))  # doi_moi / sua_duoc / tra_xac / dang_xu_ly
    result_note: Mapped[Optional[str]] = mapped_column(Text)
    received_back: Mapped[bool] = mapped_column(Boolean, default=False)

    order: Mapped["SupplierOrder"] = relationship(back_populates="items")
    ticket_item: Mapped["TicketItem"] = relationship(back_populates="supplier_order_items")


class SupplierReceive(Base):
    __tablename__ = "supplier_receives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receive_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    status: Mapped[SupplierReceiveStatus] = mapped_column(SAEnum(SupplierReceiveStatus), default=SupplierReceiveStatus.posted)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(100))
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    supplier: Mapped["Supplier"] = relationship()
    items: Mapped[List["SupplierReceiveItem"]] = relationship(back_populates="receive", cascade="all, delete-orphan")


class SupplierReceiveItem(Base):
    __tablename__ = "supplier_receive_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receive_id: Mapped[int] = mapped_column(ForeignKey("supplier_receives.id"), nullable=False)
    ticket_item_id: Mapped[int] = mapped_column(ForeignKey("ticket_items.id"), nullable=False)
    result: Mapped[Optional[str]] = mapped_column(String(100))
    result_note: Mapped[Optional[str]] = mapped_column(Text)

    receive: Mapped["SupplierReceive"] = relationship(back_populates="items")
    ticket_item: Mapped["TicketItem"] = relationship()


# ─── Transactions ─────────────────────────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ticket_items.id"))
    type: Mapped[TransactionType] = mapped_column(SAEnum(TransactionType), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ticket_item: Mapped[Optional["TicketItem"]] = relationship(back_populates="transactions")

class UserRole(str, enum.Enum):
    admin       = "admin"
    technician  = "technician"
    reception   = "reception"
    accountant  = "accountant"


# ─── Auth ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), nullable=False, default=UserRole.technician)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[List["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # UUID hex
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped["User"] = relationship(back_populates="sessions")


class SyncState(Base):
    __tablename__ = "sync_states"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
