# Warranty Management System

He thong quan ly bao hanh noi bo cho CRETA.

Ban `1.2.0` hien da co:

- backend FastAPI + SQLAlchemy
- frontend multi-page HTML/CSS/JS
- login theo session cookie
- workflow ticket, NCC, checklist, return slip, finance
- runtime database PostgreSQL
- Odoo-first master data sync cho customers/products

## Docs Map

- `README.md`: setup, runbook, su dung nhanh
- `ARCHITECTURE.md`: kien truc va module structure
- `plan.md`: current state, backlog, roadmap
- `docs/data-design.md`: data design va runtime data notes

## Quick Start

### Requirements

- macOS hoac Windows
- Python 3
- backend virtualenv da co trong `apps/server/.venv`
- file `.env` o root project
- neu dung PostgreSQL remote thi can ket noi mang toi DB server

### Configure `.env`

Can it nhat cac bien sau:

```env
BACKEND_PORT=8001
FRONTEND_PORT=3000
BACKEND_URL=http://localhost:8001
FRONTEND_URL=http://localhost:3000
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<db>

ODOO_BASE_URL=https://odoo.creta.vn
ODOO_DB=<odoo_db>
ODOO_USERNAME=<odoo_user>
ODOO_PASSWORD=<odoo_password>
```

Luu y:

- neu khong set `DATABASE_URL`, app se fallback ve SQLite legacy/dev
- runtime chinh hien tai la PostgreSQL, khong phai SQLite

### Start the app

macOS / Linux:

```bash
./start.sh
```

Windows:

```bat
start_windows.bat
```

Mac dinh:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8001`
- API docs: `http://localhost:8001/docs`

### Login

Trang dang nhap:

- `http://localhost:3000/login.html`

Tai khoan admin mac dinh:

- username: `admin`
- password: `admin123`

## Stop the app

Windows:

```bat
stop_windows.bat
```

macOS / Linux:

- neu dang chay foreground qua `./start.sh` thi dung `Ctrl+C`
- neu can, kill process theo `BACKEND_PORT` va `FRONTEND_PORT`

## Project Structure

```text
Warranty/
  apps/
    server/
      main.py
      database.py
      models.py
      odoo/
      routers/
      services/
      uploads/
      .venv/
    web/
      admin/
      assets/
      checklists/
      finance/
      masters/
      return-slips/
      supplier-orders/
      supplier-receives/
      tickets/
      index.html
      login.html
  docs/
    data-design.md
  scripts/
    prepare_data.py
  ARCHITECTURE.md
  README.md
  plan.md
```

## Main Features

### Tickets

- tao phieu bao hanh
- list/search/detail ticket
- state transition theo workflow
- rollback
- deadline extend
- notify late

### Supplier flow

- phieu gui NCC
- xac nhan gui NCC co evidence image
- phieu nhan NCC tra ve
- in phieu NCC

### Checklists

- checklist templates
- mapping checklist theo stage/item
- checklist run
- evidence upload
- finalize conclusion

### Return slips

- lap phieu tra khach
- candidate items tu C2/C3
- pack image
- delivered image
- confirm pack / confirm delivered
- print phieu tra khach

### Finance

- thu/chi
- bao cao tong hop

### Admin

- user management
- checklist template management
- role-based navigation

## Frontend Conventions

Hau het page dung shell layout sau:

```html
<div class="shell">
  <aside class="sidebar"></aside>
  <div class="main">...</div>
</div>
```

Khong hardcode sidebar tren tung page nua.

Sidebar duoc render tu:

- `apps/web/assets/layout.js`

API/auth helpers nam trong:

- `apps/web/assets/api.js`

Hai page khong dung shell nay:

- `login.html`
- `checklists/run.html`

## Master Data Notes

He thong hien dang theo huong Odoo-first cho customer/product master data.

Luu y quan trong:

- `phone` duoc xem la customer identity trong van hanh noi bo
- `customer_code` (`KHxxxxxx`) la ma reference nghiep vu/master
- neu trung `phone` thi customer co the duoc merge
- khi merge/sync, du lieu Odoo duoc uu tien

Code lien quan nam o:

- `apps/server/odoo/client.py`
- `apps/server/services/odoo_sync.py`
- `apps/server/routers/masters.py`

## Developer Notes

### Backend environment

Virtualenv hien tai:

- `apps/server/.venv`

Neu can cai package moi:

```bash
apps/server/.venv/bin/pip install <package>
```

### Test API quickly

- mo `http://localhost:8001/docs`
- hoac goi truc tiep cac endpoint `/api/...`

### Data / processed artifacts

Neu can tai tao processed data:

```bash
python3 scripts/prepare_data.py
```

## Current Technical Priorities

- Alembic migration cho PostgreSQL
- sieu chat workflow validation o backend
- permission chi tiet theo role
- chuan hoa env/sample script theo runtime hien tai
- giam debt compatibility tu schema legacy
