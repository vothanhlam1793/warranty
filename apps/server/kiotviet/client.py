"""KiotViet mock client - swap real token later."""

from __future__ import annotations
from typing import Optional

# ── Mock data (replace with real API calls after token is ready) ──────────────

_MOCK_CUSTOMERS = [
    {"kiotviet_id": "kv-c-001", "name": "Anh Thanh (Nhà Bè)", "phone": "0901234567", "address": "Nhà Bè, TP.HCM"},
    {"kiotviet_id": "kv-c-002", "name": "Quốc Thịnh", "phone": "0912345678", "address": "TP.HCM"},
    {"kiotviet_id": "kv-c-003", "name": "KALA", "phone": "0923456789", "address": "TP.HCM"},
    {"kiotviet_id": "kv-c-004", "name": "Anh Duy", "phone": "0934567890", "address": "TP.HCM"},
    {"kiotviet_id": "kv-c-005", "name": "Anh Hùng (Kiên Giang)", "phone": "0945678901", "address": "Kiên Giang"},
    {"kiotviet_id": "kv-c-006", "name": "Lương Duy Tuấn", "phone": "0956789012", "address": "TP.HCM"},
    {"kiotviet_id": "kv-c-007", "name": "Anh Bình (Núi Sập)", "phone": "0967890123", "address": "An Giang"},
    {"kiotviet_id": "kv-c-008", "name": "Hải IT", "phone": "0978901234", "address": "TP.HCM"},
    {"kiotviet_id": "kv-c-009", "name": "Camera Ngọc Huy", "phone": "0989012345", "address": "TP.HCM"},
    {"kiotviet_id": "kv-c-010", "name": "Thái Minh Hùng", "phone": "0990123456", "address": "TP.HCM"},
]

_MOCK_PRODUCTS = [
    {"kiotviet_item_id": "kv-p-001", "name": "DS-2CD1023G0-IUF", "sku": "DS-2CD1023G0-IUF"},
    {"kiotviet_item_id": "kv-p-002", "name": "DS-7616NI-K2", "sku": "DS-7616NI-K2"},
    {"kiotviet_item_id": "kv-p-003", "name": "CS-C6N 1080P", "sku": "CS-C6N-1080P"},
    {"kiotviet_item_id": "kv-p-004", "name": "IPC-F22FEP-D-IMOU", "sku": "IPC-F22FEP-D"},
    {"kiotviet_item_id": "kv-p-005", "name": "DH-HAC-HFW1239CP-A-LED", "sku": "DH-HAC-HFW1239CP"},
    {"kiotviet_item_id": "kv-p-006", "name": "Switch POE ONV 8 Port", "sku": "POE-ONV-8P"},
    {"kiotviet_item_id": "kv-p-007", "name": "Switch POE ONV 4 Port", "sku": "POE-ONV-4P"},
    {"kiotviet_item_id": "kv-p-008", "name": "Ổ cứng Seagate Skyhawk 1TB", "sku": "HDD-SG-1TB"},
    {"kiotviet_item_id": "kv-p-009", "name": "Ổ cứng Seagate Skyhawk 4TB", "sku": "HDD-SG-4TB"},
    {"kiotviet_item_id": "kv-p-010", "name": "KX-7108Ai", "sku": "KX-7108AI"},
    {"kiotviet_item_id": "kv-p-011", "name": "DS-7104HGHI-F1", "sku": "DS-7104HGHI-F1"},
    {"kiotviet_item_id": "kv-p-012", "name": "IPC-A42P-D-IMOU", "sku": "IPC-A42P-D"},
    {"kiotviet_item_id": "kv-p-013", "name": "Thẻ nhớ 32GB Hikvision", "sku": "SD-HK-32GB"},
    {"kiotviet_item_id": "kv-p-014", "name": "Thẻ nhớ Sandisk 64GB", "sku": "SD-SNDK-64GB"},
    {"kiotviet_item_id": "kv-p-015", "name": "Nguồn Adapter 12V-2A", "sku": "PSU-12V2A"},
]


def search_customers(keyword: str, limit: int = 10) -> list[dict]:
    """Search customers from KiotViet (mock)."""
    if not keyword:
        return _MOCK_CUSTOMERS[:limit]
    kw = keyword.lower()
    results = [c for c in _MOCK_CUSTOMERS if kw in c["name"].lower() or kw in (c["phone"] or "")]
    return results[:limit]


def search_products(keyword: str, limit: int = 10) -> list[dict]:
    """Search products from KiotViet (mock)."""
    if not keyword:
        return _MOCK_PRODUCTS[:limit]
    kw = keyword.lower()
    results = [p for p in _MOCK_PRODUCTS if kw in p["name"].lower() or kw in (p["sku"] or "").lower()]
    return results[:limit]


# ── Placeholder for real API calls ────────────────────────────────────────────
# When token is ready:
#   BASE_URL = "https://public.kiotapi.com"
#   RETAILER = "your_retailer_code"
#   TOKEN = os.environ.get("KIOTVIET_TOKEN")
#
# def search_customers(keyword, limit=10):
#     resp = requests.get(
#         f"{BASE_URL}/customers",
#         headers={"Retailer": RETAILER, "Authorization": f"Bearer {TOKEN}"},
#         params={"searchTerm": keyword, "pageSize": limit},
#     )
#     return resp.json().get("data", [])
