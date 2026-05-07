# Warranty Management System

He thong quan ly bao hanh noi bo cho CRETA.

Du an hien tai da hoan thien backend FastAPI, frontend multi-page HTML/CSS/JS, auth theo session, workflow NCC, checklist, phieu tra khach, va database runtime PostgreSQL.

## Quick Start

### 1. Yeu cau moi truong

- macOS hoac Windows
- Python 3
- Virtual environment cho backend da duoc tao trong `apps/server/.venv`
- Co file `.env` o root project

Neu chay voi PostgreSQL remote, can co ket noi mang toi database server.

### 2. Cau hinh `.env`

Vi du:

```env
BACKEND_PORT=8001
FRONTEND_PORT=3000
BACKEND_URL=http://localhost:8001
FRONTEND_URL=http://localhost:3000
DATABASE_URL=postgresql://warranty_user:***@svr3.camerangochoang.com:5432/warranty
ODOO_BASE_URL=https://odoo.creta.vn
ODOO_DB=<ten_database_odoo>
ODOO_USERNAME=<tai_khoan_odoo>
ODOO_PASSWORD=<mat_khau_odoo>
```

Neu khong set `DATABASE_URL`, he thong se fallback ve SQLite legacy/dev.

### 3. Chay he thong

macOS / Linux:

```bash
./start.sh
```

Windows:

```bat
start_windows.bat
```

Mac dinh:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8001`
- API docs: `http://localhost:8001/docs`

### 4. Dang nhap

Tai khoan admin hien tai:

- Username: `admin`
- Password: `admin123`

Trang dang nhap:

- `http://localhost:3000/login.html`

## Developer Onboarding

## Cau truc thu muc

```text
Warranty/
  apps/
    server/
      main.py
      database.py
      models.py
      routers/
      uploads/
      .venv/
    web/
      assets/
        api.js
        app.css
        layout.js
      admin/
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
  .env
  ARCHITECTURE.md
  plan.md
  plan_1.md
```

## Kien truc ngan gon

- Frontend static files trong `apps/web`
- Backend FastAPI trong `apps/server`
- Shared sidebar frontend trong `apps/web/assets/layout.js`
- Shared API/auth helpers trong `apps/web/assets/api.js`
- Primary DB la PostgreSQL, fallback la SQLite

Tai lieu kien truc chi tiet hon:

- `ARCHITECTURE.md`

## Database

### Runtime hien tai

- Primary: PostgreSQL remote
- Fallback: SQLite

### Luu y

- `apps/server/database.py` se uu tien `DATABASE_URL`
- Neu khong co `DATABASE_URL`, no se fallback sang file DB local
- Mot so logic patch schema legacy van con trong `database.py` de ho tro SQLite cu

## Runbook cho dev

### Khoi dong app

```bash
./start.sh
```

### Dung app

Windows:

```bat
stop_windows.bat
```

macOS/Linux:

- Dung process bang `Ctrl+C` neu chay foreground
- Hoac kill port theo `BACKEND_PORT` / `FRONTEND_PORT`

### Backend dependency

Virtual environment hien tai:

- `apps/server/.venv`

Neu can cai them package:

```bash
apps/server/.venv/bin/pip install <package>
```

### Test API nhanh

Mo docs:

- `http://localhost:8001/docs`

## Cac module nghiep vu da co

### Tickets

- Tao phieu bao hanh
- Search/list/detail ticket
- Workflow state transition
- Rollback
- Deadline extend
- Notify late

### Supplier

- Phieu gui NCC
- Phieu nhan NCC tra ve
- In phieu NCC

### Checklist

- Checklist templates
- Mapping template theo item/stage
- Checklist runs
- Evidence upload
- Finalize conclusion

### Return slips

- Tao phieu tra khach
- Candidate items tu C2/C3
- Pack image
- Delivered image
- Confirm pack / confirm delivered
- Print phieu tra

### Finance

- Thu/chi
- Bao cao tong hop

### Admin

- Quan ly user
- Role-based menu

## Frontend conventions

- Cac page thong thuong dung shell layout:

```html
<div class="shell">
  <aside class="sidebar"></aside>
  <div class="main">...</div>
</div>
```

- Sidebar duoc render tu `layout.js`, khong hardcode lai tren tung page
- Hai ngoai le hien tai:
  - `login.html`
  - `checklists/run.html`

## Odoo master data

- Master data khach hang va san pham dang duoc chuyen sang huong Odoo-first
- Backend se uu tien lay du lieu tu `odoo.creta.vn` neu da cau hinh `ODOO_*` trong `.env`
- Ma khach hang nghiep vu quan trong nhat tai CRETA la `KHxxxxxx`, hien duoc lay tu field Odoo `res.partner.x_kiotviet_1`
- Neu chua co credential hop le, backend se fallback sang mock/local de khong lam vo luong nghiep vu hien tai
- Cac field va ten bien legacy co tu `kiotviet_*` van duoc giu tam de tranh migration lon ngay lap tuc

## Tai lieu quan trong

- `ARCHITECTURE.md`: kien truc he thong
- `plan.md`: tong quan tinh trang hien tai va backlog
- `plan_1.md`: cap nhat phase 2
- `docs/data-design.md`: thiet ke du lieu va runtime data layout

## Backlog ky thuat uu tien cao

- Alembic migration cho PostgreSQL
- Sieu chat workflow validation
- Permission chi tiet theo role
- Migrate du lieu legacy neu can
- Dong bo Odoo production that va chot mapping model/field
