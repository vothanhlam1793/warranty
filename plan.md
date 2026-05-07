# Plan — Warranty Management System

## Tong quan du an

Phan mem quan ly bao hanh noi bo cho CRETA.

- Backend: Python FastAPI + SQLAlchemy
- Frontend: HTML/CSS/JS thuan, multi-page app (`apps/web/`)
- Auth: Cookie session, luu trong PostgreSQL/SQLite qua bang `user_sessions`
- Database hien tai: PostgreSQL remote la chinh, SQLite la fallback legacy/dev
- In phieu: HTML -> `window.print()` hoac endpoint HTML print
- Master data: khach hang + san pham theo huong Odoo-first

---

## Kien truc hien tai

### Backend

- `apps/server/main.py`: FastAPI app, CORS, auth middleware, mount uploads/static
- `apps/server/database.py`: load `.env`, tao engine theo `DATABASE_URL`, ho tro PostgreSQL va SQLite
- `apps/server/models.py`: ORM models cho warranty workflow, user/session, checklist, return slip
- `apps/server/routers/`:
  - `auth.py`: login, logout, me, seed/create user co ban
  - `admin.py`: CRUD user danh cho admin
  - `tickets.py`: CRUD phiếu, chuyển trạng thái, rollback, deadline, notify-late
  - `masters.py`: customers/products/suppliers CRUD + search
  - `supplier_orders.py`: phiếu gửi NCC
  - `supplier_receives.py`: phiếu nhận NCC
  - `checklists.py`: template, mapping, run, evidence, finalize
  - `return_slips.py`: phiếu trả khách, pack/delivered flow
  - `transactions.py`: thu/chi, báo cáo, in phiếu
  - `tasks.py`: dashboard việc cần làm, nhóm trạng thái, quick actions

### Frontend

- `apps/web/assets/api.js`: API wrapper, auth helper, toast, formatter
- `apps/web/assets/layout.js`: sidebar component dung chung
- `apps/web/index.html`: dashboard + viec can lam
- `apps/web/login.html`: login page
- `apps/web/admin/users.html`: quan ly user
- `apps/web/admin/checklist-templates.html`: quan ly checklist template
- `apps/web/tickets/*`: danh sach, tao moi, chi tiet phieu
- `apps/web/supplier-orders/*`: gui NCC
- `apps/web/supplier-receives/*`: nhan hang NCC tra ve
- `apps/web/return-slips/*`: danh sach + chi tiet phieu tra khach
- `apps/web/finance/report.html`: bao cao thu/chi

### Runtime configuration

Tat ca cong va env chinh duoc tap trung qua file `.env`:

- `BACKEND_PORT`
- `FRONTEND_PORT`
- `BACKEND_URL`
- `FRONTEND_URL`
- `DATABASE_URL`

Script da doc `.env`:

- `start.sh`
- `start_windows.bat`
- `stop_windows.bat`

---

## Database hien tai

### He quan tri CSDL

- Production/runtime chinh: PostgreSQL remote tren `svr3.camerangochoang.com`
- Fallback/dev cu: SQLite

### Bang chinh

| Bang | Mo ta |
|---|---|
| `users` | Tai khoan nguoi dung |
| `user_sessions` | Session dang nhap |
| `suppliers` | Nha cung cap |
| `customers` | Khach hang |
| `products` | San pham |
| `tickets` | Phieu bao hanh |
| `ticket_items` | Tung ma hang trong phieu |
| `workflow_logs` | Nhat ky chuyen trang thai |
| `supplier_orders` | Phieu gui NCC |
| `supplier_order_items` | Items trong phieu gui NCC |
| `supplier_receives` | Phieu nhan hang NCC |
| `supplier_receive_items` | Items trong phieu nhan NCC |
| `checklist_templates` | Mau checklist |
| `checklist_template_items` | Item cua template |
| `checklist_template_changes` | Lich su doi mapping checklist |
| `checklist_runs` | Lan chay checklist |
| `checklist_run_items` | Ket qua tung item checklist |
| `checklist_evidences` | Anh minh chung checklist |
| `return_slips` | Phieu tra khach |
| `return_slip_items` | Items trong phieu tra |
| `transactions` | Thu/chi |
| `sync_states` | Trang thai dong bo |

---

## Workflow nghiep vu hien tai

```text
A1  Tiep nhan / Test hang
A2  Lien he khach chot xu ly
A3  Chuan bi chuyen NCC
B1  Da gui / dang chuyen NCC
B2  NCC dang xu ly
C1  NCC tra ve - kiem tra lai
C2  PASS - cho tra khach
C3  NO PASS - xu ly tiep
C4  Can thu tien / lap phieu tra
C5  Dong goi / giao tra khach
C6  Hoan thanh
```

---

## Tinh trang hien tai

### Da hoan thanh

- [x] Chuyen runtime config sang `.env`
- [x] Dong bo script start/stop cho macOS va Windows
- [x] Chuyen backend runtime tu port 8000 sang 8001 theo cau hinh
- [x] Chuyen he thong sang PostgreSQL remote
- [x] Refactor `database.py` de ho tro PostgreSQL va SQLite
- [x] Bo sung model `ReturnSlip`, `ReturnSlipItem` va cac field lien quan
- [x] Hoan thanh auth co session cookie
- [x] Tao tai khoan admin mac dinh
- [x] Tao trang quan ly user cho admin
- [x] Hoan thanh checklist template, mapping, run, finalize
- [x] Hoan thanh flow phieu tra khach C4 -> C5 -> C6
- [x] Hoan thanh phieu gui NCC va phieu nhan NCC
- [x] Dashboard viec can lam theo workflow
- [x] Sidebar frontend da duoc chuan hoa bang component `layout.js`

### Da cap nhat moi nhat

- [x] Loai bo sidebar hardcode tren cac trang frontend
- [x] Tap trung menu dieu huong vao `apps/web/assets/layout.js`
- [x] Them menu admin co dieu kien theo role
- [x] Dong bo docs voi runtime PostgreSQL va auth/user management

### Con ton / backlog gan

- [ ] Sieu chat validation workflow o backend theo quy dinh nghiep vu
- [ ] Tach migration schema chuyen nghiep (Alembic) thay cho create_all + patch logic
- [ ] Chot chinh sach role chi tiet hon tren tung endpoint
- [ ] Chot Odoo credential production va mapping field/model chinh xac
- [ ] Import/migrate du lieu cu tu SQLite neu can

---

## Cach khoi dong

```bash
./start.sh
```

Mac dinh:

- Backend: `http://localhost:8001`
- Frontend: `http://localhost:3000`
- API docs: `http://localhost:8001/docs`

---

## API chinh dang co

| Method | Endpoint | Mo ta |
|---|---|---|
| POST | `/api/auth/login` | Dang nhap |
| POST | `/api/auth/logout` | Dang xuat |
| GET | `/api/auth/me` | User hien tai |
| GET | `/api/admin/users` | Danh sach user |
| POST | `/api/admin/users` | Tao user |
| PATCH | `/api/admin/users/{id}` | Sua user |
| DELETE | `/api/admin/users/{id}` | Xoa user |
| POST | `/api/tickets` | Tao phieu moi |
| GET | `/api/tickets` | List/search phieu |
| GET | `/api/tickets/{id}` | Chi tiet phieu |
| POST | `/api/tickets/{id}/extend-deadline` | Gia han deadline |
| POST | `/api/tickets/{id}/notify-late` | Ghi nhan da bao khach |
| GET | `/api/tasks/pending` | Viec can lam |
| GET | `/api/checklists/templates` | Danh sach template |
| POST | `/api/checklists/runs` | Tao run checklist |
| GET | `/api/checklists/runs/{id}` | Chi tiet run |
| POST | `/api/return-slips` | Tao phieu tra |
| GET | `/api/return-slips/list` | Danh sach phieu tra |
| POST | `/api/return-slips/{id}/confirm-pack` | Xac nhan dong goi |
| POST | `/api/return-slips/{id}/confirm-delivered` | Xac nhan giao khach |

---

## Ghi chu quan trong

- `apps/web/checklists/run.html` la trang full-page rieng, khong dung sidebar component
- `login.html` khong dung sidebar component
- Sidebar app da duoc tap trung 100% vao `apps/web/assets/layout.js`
- Master data search/sync backend da duoc doi sang Odoo-first, nhung van giu field legacy de tranh migration lon ngay lap tuc
