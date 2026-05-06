# Warranty Workspace

Reorganized workspace for warranty operations with KiotViet-based master data design.

## What is included

- Structured data zones: `raw`, `processed`, `schema`
- Data preparation script: `scripts/prepare_data.py`
- Web prototype: `apps/web-demo`
- Data design doc: `docs/data-design.md`

## Run data preparation

```bash
python3 scripts/prepare_data.py
```

## Run web demo

From project root:

```bash
python3 -m http.server 8080
```

Then open:

- `http://localhost:8080/apps/web-demo/`

## KiotViet master data note

- `products.catalog.json` and `customers.catalog.json` are represented as KiotViet-origin masters.
- IDs are currently placeholders (`kiotviet_item_id`, `kiotviet_customer_id`) for future API sync.
