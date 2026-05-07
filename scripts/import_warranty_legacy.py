#!/usr/bin/env python3
"""Import legacy CRETA warranty CSV into runtime DB as snapshot state.

Usage examples:
  python3 scripts/import_warranty_legacy.py --dry-run
  python3 scripts/import_warranty_legacy.py --dry-run --limit-tickets 10
  python3 scripts/import_warranty_legacy.py --dry-run --ticket 262
  python3 scripts/import_warranty_legacy.py --commit --ticket 262

This importer intentionally does NOT replay workflow transitions. It snapshots
the current legacy state for each item and creates a minimal workflow log.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps"))

from server.database import SessionLocal, init_db  # noqa: E402
from server.models import (  # noqa: E402
    Customer,
    Product,
    RequestedAction,
    Ticket,
    TicketItem,
    WorkflowLog,
    WorkflowState,
)


RAW_CSV = ROOT / "data" / "raw" / "warranty_items.csv"
LEGACY_ACTOR = "legacy_import"
STATE_COLUMN = "  "


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import legacy warranty CSV")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, do not write DB")
    parser.add_argument("--commit", action="store_true", help="Write to DB")
    parser.add_argument("--ticket", type=int, action="append", default=[], help="Import only selected ticket number")
    parser.add_argument("--limit-tickets", type=int, default=0, help="Limit number of tickets processed")
    parser.add_argument("--summary-out", type=str, default="", help="Write summary JSON to this path")
    return parser.parse_args()


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


def clean_text(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def map_action(raw: str | None) -> RequestedAction:
    value = (raw or "").strip().lower()
    if "bảo hành" in value or "bao hanh" in value:
        return RequestedAction.bao_hanh
    if "sửa" in value or "sua" in value:
        return RequestedAction.sua_chua
    if "trả hàng" in value or "tra hang" in value:
        return RequestedAction.tra_hang
    if "đổi" in value or "doi" in value:
        return RequestedAction.doi_moi
    if "mượn" in value or "muon" in value:
        return RequestedAction.hang_muon
    return RequestedAction.khong_ro


def map_state(raw: str | None) -> WorkflowState:
    mapping = {
        "A1": WorkflowState.A1,
        "A2": WorkflowState.A2,
        "A3": WorkflowState.A3,
        "B1": WorkflowState.B1,
        "B2": WorkflowState.B2,
        "B3": WorkflowState.B1,
        "B4": WorkflowState.B2,
        "C1": WorkflowState.C1,
        "C2": WorkflowState.C2,
        "C3": WorkflowState.C3,
        "C4": WorkflowState.C4,
        "C5": WorkflowState.C5,
        "C6": WorkflowState.C6,
        "C7": WorkflowState.C3,
        "C8": WorkflowState.C2,
    }
    return mapping.get((raw or "").strip().upper(), WorkflowState.A1)


def legacy_result_note(row: dict[str, str]) -> str | None:
    lines = []
    current_location = clean_text(row.get("Vị trí - hiện tại"))
    item_status = clean_text(row.get("Tình trạng"))
    return_assessment = clean_text(row.get("Đánh giá trả"))

    if current_location:
        lines.append(f"Vi tri legacy: {current_location}")
    if item_status:
        lines.append(f"Tinh trang legacy: {item_status}")
    if return_assessment:
        lines.append(f"Danh gia tra legacy: {return_assessment}")

    if not lines:
        return None
    return "\n".join(lines)


def to_int(value: str | None) -> int | None:
    try:
        return int((value or "").strip())
    except (TypeError, ValueError):
        return None


def compute_standard_return_date(received_date, explicit_return_date, explicit_expected_date):
    if explicit_return_date is not None:
        return explicit_return_date
    if explicit_expected_date is not None:
        return explicit_expected_date
    if received_date is not None:
        return received_date + timedelta(days=14)
    return None


def compute_deadline_date(received_date, explicit_deadline_date):
    if explicit_deadline_date is not None:
        return explicit_deadline_date
    if received_date is not None:
        return received_date + timedelta(days=14)
    return None


def load_rows() -> list[dict[str, str]]:
    with RAW_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def select_rows(rows: list[dict[str, str]], wanted_tickets: set[int], limit_tickets: int) -> tuple[list[dict[str, str]], list[int]]:
    rows_by_ticket: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        ticket_no = to_int(row.get("STT"))
        if ticket_no is None:
            continue
        rows_by_ticket[ticket_no].append(row)

    ordered_tickets = sorted(rows_by_ticket.keys())
    if wanted_tickets:
        ordered_tickets = [ticket for ticket in ordered_tickets if ticket in wanted_tickets]
    if limit_tickets > 0:
        ordered_tickets = ordered_tickets[:limit_tickets]

    selected_rows: list[dict[str, str]] = []
    for ticket_no in ordered_tickets:
        selected_rows.extend(rows_by_ticket[ticket_no])
    return selected_rows, ordered_tickets


def analyze_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    warnings: list[str] = []
    state_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    duplicate_keys: list[str] = []
    parse_errors: list[str] = []
    ticket_customers: dict[int, set[str]] = defaultdict(set)
    ticket_received_dates: dict[int, set[str]] = defaultdict(set)
    seen_item_keys: set[str] = set()
    missing = Counter()

    for row_index, row in enumerate(rows, start=1):
        ticket_no = to_int(row.get("STT"))
        item_no = to_int(row.get("Su"))
        customer_name = clean_text(row.get("Tên khách hàng"))
        product_name = clean_text(row.get("Mã"))
        state_raw = clean_text(row.get(STATE_COLUMN))
        action_raw = clean_text(row.get("Xử lý YC"))

        if ticket_no is None:
            missing["missing_ticket_no"] += 1
            continue
        if item_no is None:
            missing["missing_item_no"] += 1
            warnings.append(f"Row {row_index}: ticket {ticket_no} missing item_no")
            continue
        if not customer_name:
            missing["missing_customer_name"] += 1
        if not product_name:
            missing["missing_product_name"] += 1

        item_key = f"{ticket_no}-{item_no}"
        if item_key in seen_item_keys:
            duplicate_keys.append(item_key)
        seen_item_keys.add(item_key)

        if customer_name:
            ticket_customers[ticket_no].add(customer_name)
        received_raw = clean_text(row.get("Ngày nhận"))
        if received_raw:
            ticket_received_dates[ticket_no].add(received_raw)

        if state_raw:
            state_counts[state_raw.upper()] += 1
        if action_raw:
            action_counts[action_raw] += 1

        for field_name in ("Ngày nhận", "Xử lý kế", "Dự kiến trả", "Ngày trả"):
            raw_date = clean_text(row.get(field_name))
            if raw_date and parse_date(raw_date) is None:
                parse_errors.append(f"Row {row_index}: invalid {field_name}='{raw_date}'")

    for ticket_no, names in ticket_customers.items():
        if len(names) > 1:
            warnings.append(f"Ticket {ticket_no}: multiple customer names {sorted(names)}")
    for ticket_no, dates in ticket_received_dates.items():
        if len(dates) > 1:
            warnings.append(f"Ticket {ticket_no}: multiple received dates {sorted(dates)}")

    return {
        "row_count": len(rows),
        "ticket_count": len({to_int(row.get('STT')) for row in rows if to_int(row.get('STT')) is not None}),
        "item_count": len(seen_item_keys),
        "customer_count": len({clean_text(row.get('Tên khách hàng')) for row in rows if clean_text(row.get('Tên khách hàng'))}),
        "product_count": len({clean_text(row.get('Mã')) for row in rows if clean_text(row.get('Mã'))}),
        "state_counts": dict(state_counts.most_common()),
        "action_counts": dict(action_counts.most_common()),
        "missing": dict(missing),
        "duplicate_item_keys": duplicate_keys,
        "parse_errors": parse_errors,
        "warnings": warnings,
    }


def get_or_create_customer(db, cache: dict[str, int], customer_name: str) -> int:
    existing_id = cache.get(customer_name)
    if existing_id:
        return existing_id
    existing = db.query(Customer).filter(Customer.name == customer_name).first()
    if existing:
        cache[customer_name] = existing.id
        return existing.id
    customer = Customer(name=customer_name)
    db.add(customer)
    db.flush()
    cache[customer_name] = customer.id
    return customer.id


def get_or_create_product(db, cache: dict[str, int], product_name: str) -> int:
    existing_id = cache.get(product_name)
    if existing_id:
        return existing_id
    existing = db.query(Product).filter(Product.name == product_name).first()
    if existing:
        cache[product_name] = existing.id
        return existing.id
    product = Product(name=product_name)
    db.add(product)
    db.flush()
    cache[product_name] = product.id
    return product.id


def import_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    init_db()
    db = SessionLocal()
    created = Counter()
    customer_cache: dict[str, int] = {}
    product_cache: dict[str, int] = {}
    item_keys_seen = 0
    warnings: list[str] = []

    try:
        rows_by_ticket: dict[int, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            ticket_no = to_int(row.get("STT"))
            item_no = to_int(row.get("Su"))
            if ticket_no is None or item_no is None:
                continue
            rows_by_ticket[ticket_no].append(row)

        for ticket_no in sorted(rows_by_ticket.keys()):
            ticket_rows = rows_by_ticket[ticket_no]
            first = ticket_rows[0]
            ticket_no_str = str(ticket_no)
            customer_name = clean_text(first.get("Tên khách hàng")) or "Không rõ"
            customer_id = get_or_create_customer(db, customer_cache, customer_name)

            existing_ticket = db.query(Ticket).filter(Ticket.ticket_no == ticket_no_str).first()
            if existing_ticket:
                warnings.append(f"Skip existing ticket {ticket_no_str}")
                continue

            received_date = parse_date(first.get("Ngày nhận")) or datetime.today().date()
            ticket = Ticket(
                ticket_no=ticket_no_str,
                customer_id=customer_id,
                received_date=received_date,
                deadline_date=compute_deadline_date(received_date, parse_date(first.get("Xử lý kế"))),
                note=f"Legacy import from CRETA CSV (ticket {ticket_no_str})",
                created_by=LEGACY_ACTOR,
            )
            db.add(ticket)
            db.flush()
            created["tickets"] += 1

            for fallback_idx, row in enumerate(ticket_rows, start=1):
                item_no = to_int(row.get("Su")) or fallback_idx
                item_code = f"{ticket_no_str}-{item_no}"
                existing_item = db.query(TicketItem).filter(TicketItem.item_code == item_code).first()
                if existing_item:
                    warnings.append(f"Skip existing item {item_code}")
                    continue

                product_name = clean_text(row.get("Mã")) or "Sản phẩm không xác định"
                product_id = get_or_create_product(db, product_cache, product_name)
                created["products_seen"] += 1
                item_keys_seen += 1

                raw_state = clean_text(row.get(STATE_COLUMN)) or "A1"
                mapped_state = map_state(raw_state)
                raw_action = clean_text(row.get("Xử lý YC"))
                received_date = ticket.received_date
                explicit_expected_date = parse_date(row.get("Dự kiến trả"))
                explicit_return_date = parse_date(row.get("Ngày trả"))
                standard_return_date = compute_standard_return_date(
                    received_date,
                    explicit_return_date,
                    explicit_expected_date,
                )

                item = TicketItem(
                    ticket_id=ticket.id,
                    item_no=item_no,
                    item_code=item_code,
                    product_id=product_id,
                    serial_no=clean_text(row.get("Series")),
                    qty=1,
                    requested_action=map_action(raw_action),
                    workflow_state=mapped_state,
                    customer_complaint=clean_text(row.get("Yêu cầu (khách)")),
                    diagnosis_note=clean_text(row.get("Kỹ thuật")),
                    result_note=legacy_result_note(row),
                    expected_return_date=standard_return_date if mapped_state != WorkflowState.C6 else explicit_expected_date,
                    returned_date=standard_return_date if mapped_state == WorkflowState.C6 else explicit_return_date,
                )
                db.add(item)
                db.flush()
                created["items"] += 1

                db.add(
                    WorkflowLog(
                        ticket_item_id=item.id,
                        from_state=None,
                        to_state=mapped_state,
                        note=f"Legacy snapshot import from CRETA CSV (source state: {raw_state})",
                        actor=LEGACY_ACTOR,
                    )
                )
                created["logs"] += 1

        db.commit()
        created["item_keys_seen"] = item_keys_seen
        created["warnings"] = len(warnings)
        return {"created": dict(created), "warnings": warnings}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def print_summary(summary: dict[str, Any]) -> None:
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    args = parse_args()
    if args.dry_run and args.commit:
        raise SystemExit("Use either --dry-run or --commit, not both")
    if not args.dry_run and not args.commit:
        raise SystemExit("Specify one of --dry-run or --commit")

    rows = load_rows()
    selected_rows, selected_tickets = select_rows(rows, set(args.ticket), args.limit_tickets)
    summary = analyze_rows(selected_rows)
    summary["selected_tickets"] = selected_tickets

    if args.summary_out:
        output_path = Path(args.summary_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.dry_run:
        print_summary(summary)
        return

    result = import_rows(selected_rows)
    print_summary({
        "mode": "commit",
        "selection": summary,
        "result": result,
    })


if __name__ == "__main__":
    main()
