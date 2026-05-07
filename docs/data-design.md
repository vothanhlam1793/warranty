# Warranty Data Design

Tai lieu nay mo ta thiet ke du lieu va runtime architecture hien tai cua he thong Warranty.

## Tong quan hien tai

He thong gom 3 lop du lieu chinh:

- Runtime application data trong database quan he
- Uploaded files trong `apps/server/uploads`
- Processed/exported data trong `data/`

## Runtime architecture

```text
Browser
  -> Frontend static files (`apps/web`)
  -> API FastAPI (`apps/server`)
  -> PostgreSQL (primary runtime DB)
  -> uploads/ (evidence images)
```

## Database runtime

### Primary database

- PostgreSQL remote
- Ket noi qua `DATABASE_URL` trong `.env`

### Fallback database

- SQLite
- Chi dung cho legacy/dev fallback khi `DATABASE_URL` khong duoc set

## Runtime entities

### User/Auth

- `users`
- `user_sessions`

### Master data

- `customers`
- `products`
- `suppliers`
- `sync_states`

### Warranty workflow

- `tickets`
- `ticket_items`
- `workflow_logs`

### Supplier flow

- `supplier_orders`
- `supplier_order_items`
- `supplier_receives`
- `supplier_receive_items`

### Checklist flow

- `checklist_templates`
- `checklist_template_items`
- `checklist_template_changes`
- `checklist_runs`
- `checklist_run_items`
- `checklist_evidences`

### Return flow

- `return_slips`
- `return_slip_items`

### Finance

- `transactions`

## Thu muc du lieu file

```text
Warranty/
  apps/
    server/
      uploads/
    web/
  data/
    raw/
    processed/
    schema/
```

### `apps/server/uploads`

Luu anh bang chung cho:

- Ticket item evidence
- Checklist evidence
- Return slip pack image
- Return slip delivered image

### `data/raw`

- Nguon xuat thang/lich su hoac file dau vao nghiep vu

### `data/processed`

- Artifact da normalize de phuc vu dashboard, doi chieu, import/export

### `data/schema`

- JSON schema contracts cho cac file normalized

## Master data strategy (Odoo-first)

- Product master source: `odoo.creta.vn`
- Customer master source: `odoo.creta.vn`
- He thong hien uu tien search/sync tu Odoo qua JSON-RPC
- Trong giai doan chuyen doi, mot so field legacy ten `kiotviet_*` van duoc giu de tranh migration schema lon ngay lap tuc
- Khi chot schema production, nen doi ten cac field legacy nay thanh ten trung lap hon voi nguon Odoo

## Nhom field nghiep vu quan trong

### Ticket / item

- `ticket_no`
- `item_no`
- `item_code`
- `workflow_state`
- `requested_action`
- `received_date`
- `deadline_date`
- `expected_return_date`
- `returned_date`
- `evidence_url`
- `shipping_note`
- `delivery_confirm_note`

### Checklist

- `stage`
- `template_id`
- `conclusion`
- `inspector`
- `finalized_at`

### Return slip

- `slip_no`
- `status`
- `return_method`
- `shipping_note`
- `pack_image_url`
- `delivery_note`
- `delivered_image_url`
- `packed_at`
- `delivered_at`

### Customer master

- `customer_code` la ma nghiep vu noi bo dang `KHxxxxxx`
- Nguon uu tien: `res.partner.x_kiotviet_1` tren Odoo
- Fallback: `res.partner.ref`

## Processing command

Tu root project:

```bash
python3 scripts/prepare_data.py
```

Lenh nay van dung de tai tao cac artifact trong `data/processed` khi can.

## Ghi chu migration

Hien tai `database.py` van con mot it logic patch schema de ho tro legacy SQLite. Neu he thong tiep tuc dung PostgreSQL lam runtime chinh, buoc tiep theo nen la:

- dua schema migration sang Alembic
- tach seed data khoi logic startup
- chot quy trinh migrate du lieu legacy
