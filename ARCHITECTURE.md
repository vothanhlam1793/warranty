# Architecture

## Overview

Warranty Management System la he thong quan ly bao hanh noi bo cho CRETA.

He thong hien tai duoc to chuc theo mo hinh:

- Frontend static multi-page app
- Backend FastAPI
- Database quan he
- Uploaded evidence files luu tren filesystem

```text
Browser
  -> Frontend static pages (`apps/web`)
  -> FastAPI backend (`apps/server`)
  -> PostgreSQL (primary runtime database)
  -> uploads/ (evidence images)
```

## Main Components

### Frontend

Thu muc: `apps/web`

Cong nghe:

- HTML/CSS/JS thuan
- Khong dung framework SPA
- Dung `api.js` lam API wrapper
- Dung `layout.js` lam shared sidebar component

Modules chinh:

- `index.html`: dashboard + viec can lam
- `login.html`: dang nhap
- `tickets/`: tao, xem, cap nhat phieu bao hanh
- `supplier-orders/`: phieu gui NCC
- `supplier-receives/`: phieu nhan hang NCC tra ve
- `return-slips/`: phieu tra khach
- `admin/`: user management, checklist templates
- `finance/`: thu/chi va bao cao
- `masters/`: danh muc khach hang, san pham, nha cung cap

### Backend

Thu muc: `apps/server`

Cong nghe:

- FastAPI
- SQLAlchemy ORM
- Cookie-based session auth

Files chinh:

- `main.py`: app entrypoint, middleware, routers, static/uploads mount
- `database.py`: env loading, SQLAlchemy engine/session, db bootstrap
- `models.py`: toan bo ORM models

Routers:

- `auth.py`: login/logout/me
- `admin.py`: CRUD user danh cho admin
- `tickets.py`: ticket workflow
- `tasks.py`: dashboard pending tasks
- `masters.py`: master data CRUD/search
- `supplier_orders.py`: phieu gui NCC
- `supplier_receives.py`: phieu nhan NCC
- `checklists.py`: checklist template/mapping/run
- `return_slips.py`: phieu tra khach
- `transactions.py`: thu/chi va report

## Database Architecture

### Primary runtime database

- PostgreSQL
- Cau hinh qua `DATABASE_URL` trong `.env`

### Fallback database

- SQLite
- Chi de giu kha nang dev/legacy fallback

### Main entity groups

Auth:

- `users`
- `user_sessions`

Master data:

- `customers`
- `products`
- `suppliers`
- `sync_states`

Luu y:

- `customers.customer_code` duoc dung de luu ma nghiep vu `KHxxxxxx`
- Nguon uu tien cua ma nay la field Odoo `res.partner.x_kiotviet_1`

Warranty workflow:

- `tickets`
- `ticket_items`
- `workflow_logs`

Supplier workflow:

- `supplier_orders`
- `supplier_order_items`
- `supplier_receives`
- `supplier_receive_items`

Checklist workflow:

- `checklist_templates`
- `checklist_template_items`
- `checklist_template_changes`
- `checklist_runs`
- `checklist_run_items`
- `checklist_evidences`

Return workflow:

- `return_slips`
- `return_slip_items`

Finance:

- `transactions`

## Runtime Configuration

Tat ca runtime config chinh duoc tap trung trong `.env`.

Bien quan trong:

- `BACKEND_PORT`
- `FRONTEND_PORT`
- `BACKEND_URL`
- `FRONTEND_URL`
- `DATABASE_URL`

Scripts doc `.env`:

- `start.sh`
- `start_windows.bat`
- `stop_windows.bat`

## Authentication Model

- User dang nhap qua `/api/auth/login`
- Backend tao session va set cookie `session_id`
- Cookie duoc gui kem moi request API
- Backend resolve session qua bang `user_sessions`
- Admin role co them quyen quan ly user va mot so menu he thong

## Navigation / Layout Strategy

- Shared sidebar duoc render tu `apps/web/assets/layout.js`
- Cac page shell chi can:

```html
<aside class="sidebar"></aside>
```

- `layout.js` se:
  - check auth
  - render sidebar
  - render topbar user neu co `#topbarUser`
  - active menu theo current path

Ngoai le:

- `apps/web/login.html` khong co sidebar
- `apps/web/checklists/run.html` la full-page task page, khong dung shell sidebar

## File Storage

Thu muc: `apps/server/uploads`

Dung de luu:

- evidence ticket item
- checklist evidence
- return slip pack image
- return slip delivered image

Frontend truy cap file qua route `/uploads/...`

## Workflow Summary

```text
A1 -> A2 -> A3 -> B1 -> B2 -> C1 -> C2/C3 -> C4 -> C5 -> C6
```

Bo sung workflow support:

- rollback
- checklist A2/C1
- supplier send/receive
- return slip creation + pack + delivered confirmation
- finance transaction recording

## Known Technical Debt

- Chua co Alembic migration chuan cho PostgreSQL
- Van con logic patch schema trong `database.py` de ho tro SQLite legacy
- Permission hien moi o muc co ban, can siet chat them theo action/endpoint
- Chua dong bo KiotViet production

## Recommended Next Steps

1. Dua schema migration sang Alembic.
2. Tach seed/bootstrap data khoi startup flow.
3. Chot ma tran permission theo role.
4. Hoan thien quy trinh migrate du lieu cu tu SQLite.
5. Chot mapping Odoo production va bo ten field legacy `kiotviet_*` khi san sang migrate schema.
