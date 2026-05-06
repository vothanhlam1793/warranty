#!/usr/bin/env python3
"""Seed database from raw CSV warranty data."""

from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps"))

from server.database import SessionLocal, init_db
from server.models import (
    Customer, Product, Supplier, Ticket, TicketItem,
    WorkflowLog, WorkflowState, RequestedAction,
)

RAW_CSV = ROOT / "data" / "raw" / "warranty_items.csv"


def parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def map_action(raw: str) -> RequestedAction:
    raw = (raw or "").strip().lower()
    if "bảo hành" in raw or "bao hanh" in raw:
        return RequestedAction.bao_hanh
    if "sửa" in raw or "sua" in raw:
        return RequestedAction.sua_chua
    if "trả hàng" in raw or "tra hang" in raw:
        return RequestedAction.tra_hang
    if "đổi" in raw or "doi" in raw:
        return RequestedAction.doi_moi
    if "mượn" in raw or "muon" in raw:
        return RequestedAction.hang_muon
    return RequestedAction.khong_ro


def map_state(raw: str) -> WorkflowState:
    mapping = {
        "A1": WorkflowState.A1, "A2": WorkflowState.A2, "A3": WorkflowState.A3,
        "B1": WorkflowState.B1, "B2": WorkflowState.B2, "B3": WorkflowState.B1,
        "B4": WorkflowState.B2, "C1": WorkflowState.C1, "C2": WorkflowState.C2,
        "C3": WorkflowState.C3, "C4": WorkflowState.C4, "C5": WorkflowState.C5,
        "C6": WorkflowState.C6, "C7": WorkflowState.C3, "C8": WorkflowState.C2,
    }
    return mapping.get((raw or "").strip().upper(), WorkflowState.A1)


def seed():
    init_db()
    db = SessionLocal()

    print("Seeding suppliers...")
    default_suppliers = [
        {"name": "CNM", "contact_name": "NCC CNM", "phone": "", "address": "TP.HCM", "note": "Nhà cung cấp chính"},
        {"name": "IMOU", "contact_name": "", "phone": "", "address": "", "note": "Camera IMOU"},
        {"name": "Hikvision", "contact_name": "", "phone": "", "address": "", "note": "Camera Hikvision"},
        {"name": "Dahua", "contact_name": "", "phone": "", "address": "", "note": "Camera Dahua"},
        {"name": "ONV", "contact_name": "", "phone": "", "address": "", "note": "Switch POE ONV"},
        {"name": "Seagate", "contact_name": "", "phone": "", "address": "", "note": "Ổ cứng Seagate"},
        {"name": "Anh Trúc", "contact_name": "Anh Trúc", "phone": "", "address": "", "note": "Kỹ thuật ngoài"},
        {"name": "Thế Kỉ", "contact_name": "", "phone": "", "address": "", "note": "Đơn vị sửa chữa"},
    ]
    supplier_map = {}
    for s_data in default_suppliers:
        existing = db.query(Supplier).filter(Supplier.name == s_data["name"]).first()
        if not existing:
            s = Supplier(**s_data)
            db.add(s)
            db.flush()
            supplier_map[s_data["name"]] = s.id
        else:
            supplier_map[s_data["name"]] = existing.id
    db.commit()

    print("Reading CSV...")
    customer_cache: dict[str, int] = {}
    product_cache: dict[str, int] = {}
    ticket_cache: dict[int, int] = {}

    rows_by_ticket: dict[int, list] = {}
    with RAW_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ticket_no = int((row.get("STT") or "").strip())
            except (ValueError, TypeError):
                continue
            rows_by_ticket.setdefault(ticket_no, []).append(row)

    print(f"Found {len(rows_by_ticket)} unique tickets...")

    for ticket_no, items in list(rows_by_ticket.items()):
        first = items[0]
        customer_name = (first.get("Tên khách hàng") or "").strip() or "Không rõ"

        # Customer
        if customer_name not in customer_cache:
            existing = db.query(Customer).filter(Customer.name == customer_name).first()
            if existing:
                customer_cache[customer_name] = existing.id
            else:
                c = Customer(name=customer_name)
                db.add(c)
                db.flush()
                customer_cache[customer_name] = c.id

        customer_id = customer_cache[customer_name]

        # Ticket
        ticket_no_str = str(ticket_no)
        existing_ticket = db.query(Ticket).filter(Ticket.ticket_no == ticket_no_str).first()
        if existing_ticket:
            ticket_cache[ticket_no] = existing_ticket.id
        else:
            received = parse_date(first.get("Ngày nhận", ""))
            t = Ticket(
                ticket_no=ticket_no_str,
                customer_id=customer_id,
                received_date=received or datetime.today().date(),
                created_by="seed",
            )
            db.add(t)
            db.flush()
            ticket_cache[ticket_no] = t.id

        ticket_id = ticket_cache[ticket_no]

        # Items – use "Su" column as item_no, generate item_code = "{ticket_no}-{item_no}"
        for idx, row in enumerate(items, start=1):
            product_name = (row.get("Mã") or "").strip() or "Sản phẩm không xác định"
            serial_no = (row.get("Series") or "").strip() or None

            # item_no: prefer "Su" column from CSV (e.g. 1, 2, 3), else use loop index
            try:
                item_no = int((row.get("Su") or "").strip())
            except (ValueError, TypeError):
                item_no = idx

            item_code = f"{ticket_no}-{item_no}"   # e.g. "742-1"

            if product_name not in product_cache:
                existing_p = db.query(Product).filter(Product.name == product_name).first()
                if existing_p:
                    product_cache[product_name] = existing_p.id
                else:
                    p = Product(name=product_name)
                    db.add(p)
                    db.flush()
                    product_cache[product_name] = p.id

            product_id = product_cache[product_name]
            state = map_state(row.get("  ", ""))
            action = map_action(row.get("Xử lý YC", ""))

            ti = TicketItem(
                ticket_id=ticket_id,
                item_no=item_no,
                item_code=item_code,
                product_id=product_id,
                serial_no=serial_no,
                requested_action=action,
                workflow_state=state,
                customer_complaint=(row.get("Yêu cầu (khách)") or "").strip() or None,
                diagnosis_note=(row.get("Kỹ thuật") or "").strip() or None,
                expected_return_date=parse_date(row.get("Dự kiến trả", "")),
                returned_date=parse_date(row.get("Ngày trả", "")),
            )
            db.add(ti)
            db.flush()
            db.add(WorkflowLog(
                ticket_item_id=ti.id,
                from_state=None,
                to_state=state,
                note="Import từ dữ liệu cũ",
                actor="seed",
            ))

    db.commit()
    db.close()

    # Summary
    db2 = SessionLocal()
    print(f"✓ Suppliers: {db2.query(Supplier).count()}")
    print(f"✓ Customers: {db2.query(Customer).count()}")
    print(f"✓ Products:  {db2.query(Product).count()}")
    print(f"✓ Tickets:   {db2.query(Ticket).count()}")
    print(f"✓ Items:     {db2.query(TicketItem).count()}")
    db2.close()


if __name__ == "__main__":
    seed()
