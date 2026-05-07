# Architecture

## Purpose

Warranty Management System là hệ thống quản lý bảo hành nội bộ cho CRETA.

Tài liệu này mô tả:

- cac thanh phan chinh cua he thong
- ranh gioi giua frontend, backend, database, file storage
- cau truc module hien tai
- một số quyết định kỹ thuật quan trọng của bản `1.3.4`

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

Frontend là multi-page app dùng HTML/CSS/JS thuần.

Nó không sử dụng SPA framework. Mỗi trang tự tải dữ liệu qua API và tự quản lý state cần thiết của chính nó.

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
- `ticket-items/`: item-first detail pages
- `supplier-orders/`: phieu gui NCC
- `supplier-receives/`: phieu nhan NCC tra ve
- `return-slips/`: phieu tra khach
- `checklists/`: checklist run page
- `masters/`: suppliers, customers, products
- `finance/`: transaction report
- `admin/`: user management, checklist template management

#### Layout rule

Hầu hết frontend pages dùng shell sau:

```html
<div class="shell">
  <aside class="sidebar"></aside>
  <div class="main">...</div>
</div>
```

Hai ngoại lệ hiện tại:

- `apps/web/login.html`
- `apps/web/checklists/run.html`

## Backend

Thu muc: `apps/server`

Backend dùng FastAPI + SQLAlchemy.

Nó phụ trách:

- nghiep vu warranty workflow
- auth va session
- CRUD va search master data
- sync Odoo
- upload va serve evidence files
- in phiếu HTML

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

Hệ thống dùng cookie-based session auth.

Flow tong quan:

1. frontend goi `/api/auth/login`
2. backend tao record trong `user_sessions`
3. backend set cookie `session_id`
4. request sau do duoc backend doc cookie de resolve current user khi can

Lưu ý: middleware auth hiện tại chủ yếu inject context session. Việc endpoint nào bắt buộc auth/actor được quyết định trong từng router.

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

Quyết định nghiệp vụ hiện tại:

- `phone` được xem là ID gốc của customer trong vận hành nội bộ
- `customer_code` là mã reference nghiệp vụ/master (`KHxxxxxx`)
- nếu trùng `phone` thì customer sẽ được merge
- khi sync Odoo, thông tin Odoo được ưu tiên áp lên record cuối cùng

### Legacy field note

Một số field tên `kiotviet_*` vẫn còn được giữ lại trong schema để tránh migration lớn ngay lập tức.

Chúng đang đóng vai trò compatibility layer, không còn phản ánh chiến lược master data chính nữa.

## File Storage

Thu muc uploads:

- `apps/server/uploads`

Dùng để lưu:

- ticket item evidence
- checklist evidence
- supplier order evidence
- return slip pack image
- return slip delivered image

Backend mount uploads qua route:

- `/uploads/...`

## Workflow Model

Workflow item-level hiện tại:

```text
A1 -> A2 -> A3 -> B1 -> B2 -> B4 -> B2 -> C1 -> C2/C3 -> C4 -> C5 -> C6
```

Hệ thống hỗ trợ thêm:

- rollback workflow
- checklist A2/C1
- supplier send/receive flow
- return slip flow

### B4 quote flow

`B4` là state item-level dùng cho trường hợp NCC đã báo giá sửa chữa và cần chờ khách chốt.

Rule hiện tại:

- từ `B2` có thể tạo báo giá để chuyển sang `B4`
- khi vào `B4`, hệ thống tạo 2 transaction `draft` ở mức `ticket_item`:
  - `chi`: chi phí dự kiến cho NCC
  - `thu`: số tiền dự kiến thu khách
- nếu khách đồng ý:
  - giữ nguyên 2 transaction `draft`
  - set `ticket_items.requires_customer_payment = true`
  - quay lại `B2`
- nếu khách không đồng ý:
  - chuyển 2 transaction sang `cancelled`
  - set `ticket_items.requires_customer_payment = false`
  - quay lại `B2`
- khi hàng về từ NCC (`B2 -> C1`), transaction `chi` nháp gần nhất của item sẽ được chuyển sang `posted`
- ở `C4 -> C5`, chỉ bắt buộc có transaction `thu posted` nếu item có `requires_customer_payment = true`

### Transaction state model

`transactions` hiện có 3 trạng thái nghiệp vụ:

- `draft`: đã ghi nhận dự kiến, còn cho phép sửa số tiền / ghi chú
- `posted`: đã chốt và được tính vào báo cáo tài chính
- `cancelled`: giao dịch dự kiến bị hủy, không tính vào báo cáo
- transaction ghi thu/chi

## Runtime Configuration

Runtime config được đọc từ `.env` ở root project.

Biến quan trọng:

- `BACKEND_PORT`
- `FRONTEND_PORT`
- `BACKEND_URL`
- `FRONTEND_URL`
- `DATABASE_URL`
- `ODOO_BASE_URL`
- `ODOO_DB`
- `ODOO_USERNAME`
- `ODOO_PASSWORD`

Scripts chính đang được dùng:

- `start.sh`
- `start_windows.bat`
- `stop_windows.bat`

## Known Constraints

- chưa có Alembic migrations chuẩn
- `database.py` vẫn còn patch logic để hỗ trợ schema legacy
- permission model mới ở mức cơ bản, chưa thiết kế matrix role/action đầy đủ
- SQLite fallback còn tồn tại nên một số quyết định code vẫn phải giữ tính compatibility
- `.env.example` và một số script cũ chưa theo kịp hoàn toàn runtime hiện tại

## Architectural Priorities After 1.3.0

1. Đưa schema migration sang Alembic.
2. Tách schema bootstrap/seed khỏi startup runtime.
3. Chốt permission model theo role và action.
4. Giảm dần compatibility code legacy `kiotviet_*` khi schema migration sẵn sàng.
5. Chuẩn hóa lại env/sample scripts theo runtime thật đang dùng.
