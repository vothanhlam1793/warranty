# Warranty Data Design

This project now uses a layered data layout and treats product/customer as master data sourced from KiotViet.

## Folder layout

```text
Warranty/
  apps/
    web-demo/
  data/
    raw/
      warranty_items.csv
      warranty_report.csv
    processed/
      warranty_items.normalized.json
      warranty_dashboard.summary.json
      warranty_report.states.json
      products.catalog.json
      customers.catalog.json
    schema/
      warranty_item.schema.json
      warranty_report_state.schema.json
      product_master.schema.json
      customer_master.schema.json
  docs/
    data-design.md
  scripts/
    prepare_data.py
```

## Data layers

- `data/raw`: immutable source exports.
- `data/processed`: normalized artifacts for dashboard and app consumption.
- `data/schema`: JSON schema contracts for integration and validation.

## Master data strategy (KiotViet)

- Product master source: `kiotviet`.
- Customer master source: `kiotviet`.
- Warranty item records keep business snapshots but are linked to master keys:
  - `product_key`
  - `customer_key`
  - `master_data_source = kiotviet`
- `products.catalog.json` and `customers.catalog.json` are local catalogs extracted from legacy warranty records and marked with `master_source: kiotviet`.
- `kiotviet_item_id` and `kiotviet_customer_id` are kept for future synchronization.

## Normalized warranty item shape

Core fields in `warranty_items.normalized.json`:

- `ticket_no`, `item_no`, `ticket_item_id`
- `product_name`, `product_key`, `serial_number`
- `customer_name`, `customer_key`
- `workflow_state`, `requested_action`, `current_location`
- `received_date`, `processing_deadline`, `expected_return_date`, `returned_date`
- `processing_notes`, `customer_request`, `return_assessment`

## Processing command

Run this command from project root:

```bash
python3 scripts/prepare_data.py
```

It regenerates all files in `data/processed`.
