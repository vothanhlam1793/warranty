"""Odoo master-data client.

This module reuses the same JSON-RPC approach already used in the
`sync-kiot-odoo` project so Warranty can read shared master data directly
from `odoo.creta.vn`.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests


ODOO_BASE_URL = os.environ.get("ODOO_BASE_URL", os.environ.get("ODOO_URL", "")).rstrip("/")
ODOO_DB = os.environ.get("ODOO_DB", "")
ODOO_USERNAME = os.environ.get("ODOO_USERNAME", "")
ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD", "")
ODOO_CUSTOMER_MODEL = os.environ.get("ODOO_CUSTOMER_MODEL", "res.partner")
ODOO_PRODUCT_MODEL = os.environ.get("ODOO_PRODUCT_MODEL", "product.product")
ODOO_TIMEOUT = int(os.environ.get("ODOO_TIMEOUT", "15"))


_MOCK_CUSTOMERS = [
    {"odoo_id": "mock-c-001", "name": "Anh Thanh (Nha Be)", "phone": "0901234567", "address": "Nha Be, TP.HCM"},
    {"odoo_id": "mock-c-002", "name": "Quoc Thinh", "phone": "0912345678", "address": "TP.HCM"},
]

_MOCK_PRODUCTS = [
    {"odoo_id": "mock-p-001", "name": "DS-2CD1023G0-IUF", "sku": "DS-2CD1023G0-IUF"},
    {"odoo_id": "mock-p-002", "name": "DS-7616NI-K2", "sku": "DS-7616NI-K2"},
]


def _is_configured() -> bool:
    return all([ODOO_BASE_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD])


class OdooClient:
    def __init__(self, base_url: str, username: str, password: str, db: str | None = None, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.db = db
        self.timeout = timeout
        self.max_retries = 5
        self.retry_base_seconds = 0.5
        self.uid: int | None = None
        self.session = requests.Session()

    def _jsonrpc(self, service: str, method: str, args: list[Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": service,
                "method": method,
                "args": args,
            },
            "id": 1,
        }
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                res = self.session.post(f"{self.base_url}/jsonrpc", json=payload, timeout=self.timeout)
                res.raise_for_status()
                body = res.json()
                if body.get("error"):
                    raise RuntimeError(f"Odoo RPC error: {body['error']}")
                return body.get("result")
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_base_seconds * (2**attempt))
        if last_error:
            raise RuntimeError(f"Odoo RPC failed after retries: {last_error}")
        raise RuntimeError("Odoo RPC failed unexpectedly")

    def authenticate(self) -> tuple[str, int]:
        if self.db is None:
            raise RuntimeError("ODOO_DB is required")
        uid = self._jsonrpc("common", "authenticate", [self.db, self.username, self.password, {}])
        if not isinstance(uid, int) or uid <= 0:
            raise RuntimeError("Odoo authentication failed")
        self.uid = uid
        return self.db, uid

    def _execute_kw(self, model: str, method: str, args: list[Any] | None = None, kwargs: dict[str, Any] | None = None) -> Any:
        if self.db is None or self.uid is None:
            self.authenticate()
        return self._jsonrpc(
            "object",
            "execute_kw",
            [self.db, self.uid, self.password, model, method, args or [], kwargs or {}],
        )

    def search_read(
        self,
        model: str,
        domain: list[Any],
        fields: list[str],
        limit: int = 10,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {"fields": fields, "limit": limit, "offset": offset}
        if order:
            kwargs["order"] = order
        return self._execute_kw(model, "search_read", [domain], kwargs)


def _build_client() -> OdooClient:
    return OdooClient(
        base_url=ODOO_BASE_URL,
        username=ODOO_USERNAME,
        password=ODOO_PASSWORD,
        db=ODOO_DB or None,
        timeout=ODOO_TIMEOUT,
    )


def _none_if_false(value: Any) -> Any:
    return None if value is False else value


def _customer_domain(keyword: str) -> list[Any]:
    if not keyword:
        return [["customer_rank", ">", 0]]
    if keyword.upper().startswith("KH"):
        return ["|", ["x_kiotviet_1", "=", keyword.upper()], ["ref", "=", keyword.upper()]]
    return [
        ["customer_rank", ">", 0],
        "|",
        "|",
        ["name", "ilike", keyword],
        ["phone", "ilike", keyword],
        ["x_kiotviet_1", "ilike", keyword],
    ]


def _product_domain(keyword: str) -> list[Any]:
    if not keyword:
        return []
    return ["|", ["name", "ilike", keyword], ["default_code", "ilike", keyword]]


def search_customers(keyword: str, limit: int = 10) -> list[dict]:
    if not _is_configured():
        kw = keyword.lower()
        rows = _MOCK_CUSTOMERS if not keyword else [c for c in _MOCK_CUSTOMERS if kw in c["name"].lower() or kw in (c.get("phone") or "")]
        return rows[:limit]

    try:
        rows = _build_client().search_read(
            ODOO_CUSTOMER_MODEL,
            _customer_domain(keyword),
            ["id", "name", "phone", "mobile", "street", "street2", "city", "email", "ref", "x_kiotviet_1"],
            limit=limit,
            order="x_kiotviet_1 asc, ref asc, name asc",
        )
        result = []
        for row in rows:
            address_parts = [row.get("street"), row.get("street2"), row.get("city")]
            result.append(
                {
                    "odoo_id": str(row.get("id")),
                    "customer_code": _none_if_false(row.get("x_kiotviet_1") or row.get("ref")),
                    "name": _none_if_false(row.get("name")),
                    "phone": _none_if_false(row.get("phone") or row.get("mobile")),
                    "email": _none_if_false(row.get("email")),
                    "address": ", ".join([x for x in address_parts if x]),
                }
            )
        return result
    except Exception:
        kw = keyword.lower()
        rows = _MOCK_CUSTOMERS if not keyword else [c for c in _MOCK_CUSTOMERS if kw in c["name"].lower() or kw in (c.get("phone") or "")]
        return rows[:limit]


def fetch_customers_with_codes(limit: int = 500) -> list[dict]:
    if not _is_configured():
        return []
    try:
        rows = _build_client().search_read(
            ODOO_CUSTOMER_MODEL,
            [["x_kiotviet_1", "!=", False]],
            ["id", "name", "phone", "mobile", "street", "street2", "city", "email", "ref", "x_kiotviet_1"],
            limit=limit,
            order="x_kiotviet_1 asc",
        )
        result = []
        for row in rows:
            address_parts = [row.get("street"), row.get("street2"), row.get("city")]
            result.append(
                {
                    "odoo_id": str(row.get("id")),
                    "customer_code": _none_if_false(row.get("x_kiotviet_1") or row.get("ref")),
                    "name": _none_if_false(row.get("name")),
                    "phone": _none_if_false(row.get("phone") or row.get("mobile")),
                    "email": _none_if_false(row.get("email")),
                    "address": ", ".join([x for x in address_parts if x]),
                }
            )
        return result
    except Exception:
        return []


def search_products(keyword: str, limit: int = 10) -> list[dict]:
    if not _is_configured():
        kw = keyword.lower()
        rows = _MOCK_PRODUCTS if not keyword else [p for p in _MOCK_PRODUCTS if kw in p["name"].lower() or kw in (p.get("sku") or "").lower()]
        return rows[:limit]

    try:
        rows = _build_client().search_read(
            ODOO_PRODUCT_MODEL,
            _product_domain(keyword),
            ["id", "name", "default_code"],
            limit=limit,
            order="name asc",
        )
        return [
            {
                "odoo_id": str(row.get("id")),
                "name": _none_if_false(row.get("name")),
                "sku": _none_if_false(row.get("default_code")),
            }
            for row in rows
        ]
    except Exception:
        kw = keyword.lower()
        rows = _MOCK_PRODUCTS if not keyword else [p for p in _MOCK_PRODUCTS if kw in p["name"].lower() or kw in (p.get("sku") or "").lower()]
        return rows[:limit]
