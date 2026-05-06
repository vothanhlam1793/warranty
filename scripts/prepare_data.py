#!/usr/bin/env python3
"""Normalize raw warranty CSV files into processed JSON artifacts."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_ITEMS_PATH = ROOT / "data" / "raw" / "warranty_items.csv"
RAW_REPORT_PATH = ROOT / "data" / "raw" / "warranty_report.csv"
PROCESSED_DIR = ROOT / "data" / "processed"


def parse_date(raw_value: str) -> str | None:
    value = (raw_value or "").strip()
    if not value:
        return None

    formats = ["%d/%m/%Y", "%d/%m/%y"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def to_int(raw_value: str) -> int | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def clean_text(raw_value: str) -> str | None:
    value = (raw_value or "").strip()
    return value or None


def slug_key(raw_value: str | None, prefix: str) -> str | None:
    if not raw_value:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "-", raw_value.lower())
    normalized = normalized.strip("-")
    if not normalized:
        return None
    return f"{prefix}_{normalized}"


def normalize_items() -> tuple[list[dict], dict, list[dict], list[dict]]:
    normalized = []
    status_counter = Counter()
    location_counter = Counter()
    action_counter = Counter()
    open_count = 0
    done_count = 0

    product_master: dict[str, dict] = {}
    customer_master: dict[str, dict] = {}

    with RAW_ITEMS_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for idx, row in enumerate(reader, start=1):
            ticket_no = to_int(row.get("STT", ""))
            item_no = to_int(row.get("Su", ""))

            workflow_state = clean_text(row.get("  ", ""))
            requested_action = clean_text(row.get("Xử lý YC", ""))
            current_location = clean_text(row.get("Vị trí - hiện tại", ""))
            returned_date = parse_date(row.get("Ngày trả", ""))
            product_name = clean_text(row.get("Mã", ""))
            customer_name = clean_text(row.get("Tên khách hàng", ""))
            product_key = slug_key(product_name, "prd")
            customer_key = slug_key(customer_name, "cus")

            record = {
                "row_id": idx,
                "ticket_no": ticket_no,
                "item_no": item_no,
                "ticket_item_id": (
                    f"{ticket_no}-{item_no}" if ticket_no is not None and item_no is not None else None
                ),
                "product_name": product_name,
                "serial_number": clean_text(row.get("Series", "")),
                "product_key": product_key,
                "workflow_state": workflow_state,
                "item_status": clean_text(row.get("Tình trạng", "")),
                "current_location": current_location,
                "processing_notes": clean_text(row.get("Kỹ thuật", "")),
                "customer_name": customer_name,
                "customer_key": customer_key,
                "customer_request": clean_text(row.get("Yêu cầu (khách)", "")),
                "requested_action": requested_action,
                "return_assessment": clean_text(row.get("Đánh giá trả", "")),
                "received_date": parse_date(row.get("Ngày nhận", "")),
                "processing_deadline": parse_date(row.get("Xử lý kế", "")),
                "expected_return_date": parse_date(row.get("Dự kiến trả", "")),
                "returned_date": returned_date,
                "master_data_source": "kiotviet",
            }
            normalized.append(record)

            if product_key and product_key not in product_master:
                product_master[product_key] = {
                    "product_key": product_key,
                    "name": product_name,
                    "master_source": "kiotviet",
                    "kiotviet_item_id": None,
                    "legacy_detected_from": "warranty_items.csv",
                }

            if customer_key and customer_key not in customer_master:
                customer_master[customer_key] = {
                    "customer_key": customer_key,
                    "name": customer_name,
                    "master_source": "kiotviet",
                    "kiotviet_customer_id": None,
                    "legacy_detected_from": "warranty_items.csv",
                }

            if workflow_state:
                status_counter[workflow_state] += 1
            if current_location:
                location_counter[current_location] += 1
            if requested_action:
                action_counter[requested_action] += 1

            if returned_date:
                done_count += 1
            else:
                open_count += 1

    summary = {
        "total_items": len(normalized),
        "open_items": open_count,
        "closed_items": done_count,
        "by_workflow_state": dict(status_counter.most_common()),
        "by_location": dict(location_counter.most_common()),
        "top_requested_actions": dict(action_counter.most_common(20)),
    }

    products = sorted(product_master.values(), key=lambda item: (item["name"] or ""))
    customers = sorted(customer_master.values(), key=lambda item: (item["name"] or ""))

    return normalized, summary, products, customers


def parse_report_metadata() -> dict:
    with RAW_REPORT_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        rows = list(reader)

    if len(rows) < 3:
        return {
            "states": [],
            "columns": [],
        }

    states = []
    for row in rows[2:]:
        if not row:
            continue
        code = (row[0] or "").strip()
        title = (row[1] or "").strip()
        if code:
            states.append({"code": code, "title": title})

    return {
        "state_count": len(states),
        "states": states,
    }


def write_json(path: Path, data: dict | list) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    items, summary, products, customers = normalize_items()
    report_meta = parse_report_metadata()

    write_json(PROCESSED_DIR / "warranty_items.normalized.json", items)
    write_json(PROCESSED_DIR / "warranty_dashboard.summary.json", summary)
    write_json(PROCESSED_DIR / "warranty_report.states.json", report_meta)
    write_json(PROCESSED_DIR / "products.catalog.json", products)
    write_json(PROCESSED_DIR / "customers.catalog.json", customers)

    print("Prepared data artifacts:")
    print("- data/processed/warranty_items.normalized.json")
    print("- data/processed/warranty_dashboard.summary.json")
    print("- data/processed/warranty_report.states.json")
    print("- data/processed/products.catalog.json")
    print("- data/processed/customers.catalog.json")


if __name__ == "__main__":
    main()
