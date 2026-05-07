# Warranty Management System

Hệ thống quản lý bảo hành nội bộ cho CRETA.

Phiên bản `1.3.2` hiện có:

- backend FastAPI + SQLAlchemy
- frontend multi-page HTML/CSS/JS
- đăng nhập theo session cookie
- workflow ticket, NCC, checklist, return slip, finance
- runtime database PostgreSQL
- đồng bộ master data customer/product theo hướng Odoo-first
- deploy Docker Compose với frontend/backend tách riêng
- import dữ liệu legacy từ `data/raw/warranty_items.csv`
- màn chi tiết riêng cho từng `ticket_item`

## Docs Map

- `README.md`: setup, runbook, sử dụng nhanh
- `ARCHITECTURE.md`: kiến trúc và module structure
- `plan.md`: current state, backlog, roadmap
- `plan_1.md`: historical phase-2 snapshot
- `docs/data-design.md`: data design và runtime data notes
- `DEPLOY.md`: ghi chú deploy Docker/Reverse Proxy

## Quick Start

### Requirements

- macOS hoặc Windows
- Python 3
- backend virtualenv có sẵn trong `apps/server/.venv`
- file `.env` ở root project
- nếu dùng PostgreSQL remote thì cần kết nối mạng tới DB server

### Configure `.env`

Cần ít nhất các biến sau:

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

Lưu ý:

- nếu không set `DATABASE_URL`, app sẽ fallback về SQLite legacy/dev
- runtime chính hiện tại là PostgreSQL, không phải SQLite

### Start the app

macOS / Linux:

```bash
./start.sh
```

Windows:

```bat
start_windows.bat
```

Mặc định:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8001`
- API docs: `http://localhost:8001/docs`

### Login

Trang đăng nhập:

- `http://localhost:3000/login.html`

Tài khoản admin mặc định:

- username: `admin`
- password: `admin123`

## Stop the app

Windows:

```bat
stop_windows.bat
```

macOS / Linux:

- nếu đang chạy foreground qua `./start.sh` thì dùng `Ctrl+C`
- nếu cần, kill process theo `BACKEND_PORT` và `FRONTEND_PORT`

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
    nginx/
      Dockerfile
      nginx.conf
    web/
      admin/
      assets/
      checklists/
      finance/
      masters/
      return-slips/
      supplier-orders/
      supplier-receives/
      ticket-items/
      tickets/
      index.html
      login.html
  data/
    raw/
    processed/
  docs/
    data-design.md
  scripts/
    prepare_data.py
    import_warranty_legacy.py
  ARCHITECTURE.md
  DEPLOY.md
  README.md
  plan.md
  plan_1.md
  docker-compose.yml
```

## Main Features

### Tickets

- tạo phiếu bảo hành
- list/search/detail ticket
- state transition theo workflow
- rollback
- deadline extend
- notify late

### Ticket-item detail

- mở trực tiếp theo `item_code`
- xem trạng thái, lịch sử, ảnh minh chứng, checklist và quan hệ nghiệp vụ của từng mã
- hỗ trợ tạo báo giá sửa chữa từ `B2 -> B4`, chốt khách đồng ý / không đồng ý ngay trên item detail
- cho phép sửa số tiền transaction nháp trước khi chuyển sang `posted`
- phù hợp cho mô hình vận hành item-first

### Supplier flow

- phiếu gửi NCC
- xác nhận gửi NCC có evidence image
- phiếu nhận NCC trả về
- in phiếu NCC

### Checklists

- checklist templates
- mapping checklist theo stage/item
- checklist run
- evidence upload tự động khi chọn file
- finalize conclusion

### Return slips

- lập phiếu trả khách
- candidate items từ C2/C3
- pack image
- delivered image
- confirm pack / confirm delivered
- print phiếu trả khách

### Finance

- thu/chi
- transaction có `draft` / `posted` / `cancelled`
- báo cáo tổng hợp

### Admin

- user management
- checklist template management
- role-based navigation

## Frontend Conventions

Hầu hết page dùng shell layout sau:

```html
<div class="shell">
  <aside class="sidebar"></aside>
  <div class="main">...</div>
</div>
```

Sidebar được render từ:

- `apps/web/assets/layout.js`

API/auth helpers nằm trong:

- `apps/web/assets/api.js`

Hai page không dùng shell này:

- `login.html`
- `checklists/run.html`

## Docker Deploy

Production hiện tại hỗ trợ mô hình:

- `svr12`: public Nginx + SSL
- `orion`: Docker Compose chạy `frontend` và `backend`

Các file chính:

- `docker-compose.yml`
- `apps/server/Dockerfile`
- `apps/nginx/Dockerfile`
- `apps/nginx/nginx.conf`
- `DEPLOY.md`

## Legacy Import

Dữ liệu legacy CRETA hiện được import bằng:

```bash
apps/server/.venv/bin/python scripts/import_warranty_legacy.py --dry-run
apps/server/.venv/bin/python scripts/import_warranty_legacy.py --commit
```

Importer này hoạt động theo kiểu snapshot state, không replay workflow cũ.

## Current Technical Priorities

- Alembic migration cho PostgreSQL
- siết chặt workflow validation ở backend
- permission chi tiết theo role
- chuẩn hóa env/sample script theo runtime hiện tại
- giảm debt compatibility từ schema legacy
