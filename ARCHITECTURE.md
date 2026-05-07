# Architecture

## Purpose

Warranty Management System la he thong quan ly bao hanh noi bo cho CRETA.

Tai lieu nay mo ta:

- cac thanh phan chinh cua he thong
- ranh gioi giua frontend, backend, database, file storage
- cau truc module hien tai
- mot so quyet dinh ky thuat quan trong cua ban `1.2.0`

`README.md` duoc dung cho setup va runbook.

`plan.md` duoc dung cho current state va roadmap.

## System Shape

```text
Browser
  -> Static frontend pages (`apps/web`)
  -> FastAPI backend (`apps/server`)
  -> PostgreSQL (primary runtime database)
  -> Local uploads directory (`apps/server/uploads`)
  -> Odoo (`odoo.creta.vn`) cho customer/product master data
```

## Runtime Components

### Frontend

Thu muc: `apps/web`

Frontend la multi-page app dung HTML/CSS/JS thuan.

No khong su dung SPA framework. Moi trang tu tai du lieu qua API va tu quan ly state can thiet cua chinh no.

Frontend phu thuoc vao 2 file shared quan trong:

- `apps/web/assets/api.js`
- `apps/web/assets/layout.js`

#### Shared frontend utilities

`api.js` phu trach:

- API wrapper
- cookie-based auth check
- toast
- date/money/state formatter
- actor auto-fill helpers

`layout.js` phu trach:

- render sidebar chung
- render topbar user neu trang co `#topbarUser`
- menu theo role
- active nav theo current path

#### Frontend module groups

- `index.html`: dashboard va pending tasks
- `login.html`: login page
- `tickets/`: ticket list, create, detail
- `supplier-orders/`: phieu gui NCC
- `supplier-receives/`: phieu nhan NCC tra ve
- `return-slips/`: phieu tra khach
- `checklists/`: checklist run page
- `masters/`: suppliers, customers, products
- `finance/`: transaction report
- `admin/`: user management, checklist template management

#### Layout rule

Hau het frontend pages dung shell sau:

```html
<div class="shell">
  <aside class="sidebar"></aside>
  <div class="main">...</div>
</div>
```

Hai ngoai le hien tai:

- `apps/web/login.html`
- `apps/web/checklists/run.html`

## Backend

Thu muc: `apps/server`

Backend dung FastAPI + SQLAlchemy.

No phu trach:

- nghiep vu warranty workflow
- auth va session
- CRUD va search master data
- sync Odoo
- upload va serve evidence files
- in phieu HTML

### Main backend files

- `main.py`: app entry, middleware, router registration, uploads mount
- `database.py`: env loading, engine/session setup, bootstrap DB logic
- `models.py`: ORM models

### Router modules

- `auth.py`: login, logout, me, actor resolution
- `admin.py`: CRUD users cho admin
- `tickets.py`: ticket workflow, rollback, deadline, notify-late
- `tasks.py`: dashboard pending tasks
- `masters.py`: customers/products/suppliers CRUD, list, search, sync trigger
- `supplier_orders.py`: phieu gui NCC
- `supplier_receives.py`: phieu nhan NCC
- `checklists.py`: template, mapping, run, evidence, finalize
- `return_slips.py`: phieu tra khach
- `transactions.py`: thu/chi va report

### Middleware/auth model

He thong dung cookie-based session auth.

Flow tong quan:

1. frontend goi `/api/auth/login`
2. backend tao record trong `user_sessions`
3. backend set cookie `session_id`
4. request sau do duoc backend doc cookie de resolve current user khi can

Luu y: middleware auth hien tai chu yeu inject context session. Viec endpoint nao bat buoc auth/actor duoc quyet dinh trong tung router.

## Data Layer

### Primary runtime database

- PostgreSQL
- cau hinh qua `DATABASE_URL`

### Fallback database

- SQLite
- giu lai de phuc vu legacy/dev fallback

### Main entity groups

#### Auth

- `users`
- `user_sessions`

#### Master data

- `customers`
- `products`
- `suppliers`
- `sync_states`

#### Warranty workflow

- `tickets`
- `ticket_items`
- `workflow_logs`

#### Supplier workflow

- `supplier_orders`
- `supplier_order_items`
- `supplier_receives`
- `supplier_receive_items`

#### Checklist workflow

- `checklist_templates`
- `checklist_template_items`
- `checklist_template_changes`
- `checklist_runs`
- `checklist_run_items`
- `checklist_evidences`

#### Return workflow

- `return_slips`
- `return_slip_items`

#### Finance

- `transactions`

## Master Data Strategy

### Odoo-first

Customer va product master data hien theo huong Odoo-first.

Nguon chinh:

- `ODOO_BASE_URL`
- `ODOO_DB`
- `ODOO_USERNAME`
- `ODOO_PASSWORD`

Code lien quan:

- `apps/server/odoo/client.py`
- `apps/server/services/odoo_sync.py`
- `apps/server/routers/masters.py`

### Customer identity rule

Quyet dinh nghiep vu hien tai:

- `phone` duoc xem la ID goc cua customer trong van hanh noi bo
- `customer_code` la ma reference nghiep vu/master (`KHxxxxxx`)
- neu trung `phone` thi customer se duoc merge
- khi sync Odoo, thong tin Odoo duoc uu tien ap len record cuoi cung

### Legacy field note

Mot so field ten `kiotviet_*` van con duoc giu lai trong schema de tranh migration lon ngay lap tuc.

Chung dang dong vai tro compatibility layer, khong con phan anh chien luoc master data chinh nua.

## File Storage

Thu muc uploads:

- `apps/server/uploads`

Dung de luu:

- ticket item evidence
- checklist evidence
- supplier order evidence
- return slip pack image
- return slip delivered image

Backend mount uploads qua route:

- `/uploads/...`

## Workflow Model

Workflow item-level hien tai:

```text
A1 -> A2 -> A3 -> B1 -> B2 -> C1 -> C2/C3 -> C4 -> C5 -> C6
```

He thong ho tro them:

- rollback workflow
- checklist A2/C1
- supplier send/receive flow
- return slip flow
- transaction ghi thu/chi

## Runtime Configuration

Runtime config duoc doc tu `.env` o root project.

Bien quan trong:

- `BACKEND_PORT`
- `FRONTEND_PORT`
- `BACKEND_URL`
- `FRONTEND_URL`
- `DATABASE_URL`
- `ODOO_BASE_URL`
- `ODOO_DB`
- `ODOO_USERNAME`
- `ODOO_PASSWORD`

Scripts chinh dang duoc dung:

- `start.sh`
- `start_windows.bat`
- `stop_windows.bat`

## Known Constraints

- chua co Alembic migrations chuan
- `database.py` van con patch logic de ho tro schema legacy
- permission model moi o muc co ban, chua thiet ke matrix role/action day du
- SQLite fallback con ton tai nen mot so quyet dinh code van phai giu tinh compatibility
- `.env.example` va mot so script cu chua theo kip hoan toan runtime hien tai

## Architectural Priorities After 1.2.0

1. Dua schema migration sang Alembic.
2. Tach schema bootstrap/seed khoi startup runtime.
3. Chot permission model theo role va action.
4. Giam dan compatibility code legacy `kiotviet_*` khi schema migration san sang.
5. Chuan hoa lai env/sample scripts theo runtime that dang dung.
