# Plan 1 — Warranty Management System: Phase 2 Status Update

> Ngay: 06/05/2026
> Trang thai: Da vuot qua phase 2 co ban, dang chuyen sang hoan thien va chuan hoa
> Dev phu trach: Opencode (AI Agent)

---

## Tong quan phase 2

Muc tieu phase 2 ban dau la hoan thien cac khoi nghiep vu lon sau:

- Authentication va session
- Checklist A2/C1
- Phiếu gui NCC / nhận NCC
- Phiếu tra khach
- Rollback va audit log
- C5 -> C6 co xac nhan, anh minh chung

Trang thai hien tai:

- Auth: xong
- NCC send/receive: xong
- Checklist: xong
- Return slip: xong
- User management admin: moi them xong
- Frontend shared sidebar: moi chuan hoa xong
- PostgreSQL runtime: moi chuyen xong

---

## Hang muc da hoan thanh

### 1. Authentication (xong)

- [x] Model `User`, `UserSession`
- [x] Router `auth.py` cho login/logout/me
- [x] Middleware auth trong `main.py`
- [x] Trang `apps/web/login.html`
- [x] `checkAuth()` va auth helper trong `api.js`

### 2. Rollback workflow (xong)

- [x] Endpoint rollback trong `tickets.py`
- [x] UI rollback trong `tickets/detail.html`
- [x] Ghi log workflow day du

### 3. Supplier order / send / receive (xong)

- [x] Tao phiếu gui NCC
- [x] In phiếu gui NCC
- [x] Xac nhan gui NCC
- [x] Upload bang chung
- [x] Phiếu nhận NCC tra ve
- [x] Chuyen item sang C1 sau khi nhan hang ve

### 4. Checklist system (xong)

- [x] Model checklist templates
- [x] Model checklist run, run items, evidences
- [x] Router checklist
- [x] Template admin page
- [x] Mapping A2/C1 cho tung item
- [x] Run checklist va finalize conclusion

### 5. Return slip system (xong)

- [x] Model `ReturnSlip`, `ReturnSlipItem`
- [x] Router `return_slips.py`
- [x] Candidate items tu C2/C3
- [x] Tao phieu tra khach
- [x] Pack image / delivered image
- [x] Confirm pack: C4 -> C5
- [x] Confirm delivered: C5 -> C6
- [x] Print return slip

### 6. Admin user management (xong)

- [x] Router `admin.py`
- [x] CRUD user chi danh cho admin
- [x] Tao tai khoan admin mac dinh
- [x] Trang `apps/web/admin/users.html`

### 7. Frontend shared layout (xong)

- [x] Tao `apps/web/assets/layout.js`
- [x] Chuyen tat ca page shell ve sidebar component dung chung
- [x] Xoa sidebar hardcode khoi cac page
- [x] Role-based menu cho admin

### 8. Config/runtime (xong)

- [x] Dua port/config vao `.env`
- [x] Dong bo `start.sh`, `start_windows.bat`, `stop_windows.bat`
- [x] Chuyen backend ve port 8001 theo config
- [x] Chuyen runtime DB sang PostgreSQL remote

---

## Dieu da cap nhat moi so voi plan cu

Nhung muc truoc day con danh dau `Pending`, hien nay da xong:

- `apps/server/models.py`: checklist + return slip models
- `apps/server/routers/checklists.py`: checklist router
- `apps/server/routers/return_slips.py`: return slip router
- `apps/web/return-slips/list.html`: danh sach phieu tra
- `apps/web/return-slips/detail.html`: chi tiet phieu tra
- `apps/web/checklists/run.html`: checklist run page
- `apps/web/tickets/detail.html`: da gan checklist/return slip actions

---

## Cong viec tiep theo de nang cap phase 3

### Uu tien cao

- [ ] Alembic migration cho PostgreSQL
- [ ] Chot validation workflow o backend theo rule nghiep vu that su
- [ ] Chinh sach role/permission chi tiet theo endpoint va action
- [ ] Seed user/role du lieu chuan cho production

### Uu tien trung binh

- [ ] Quan ly cau hinh bang admin page thay vi sua `.env` tay
- [ ] Global search theo `item_code`, serial, ticket_no
- [ ] Export Excel/CSV
- [ ] Logging operational/deployment ro rang hon

### Uu tien sau

- [ ] Dong bo KiotViet that
- [ ] Import du lieu legacy tu SQLite
- [ ] Tach frontend component dung chung them cho topbar/modal/form patterns

---

## Ket luan

Phase 2 khong con o muc "dang trien khai 70%" nua. Theo trang thai code hien tai, nhung khoi nghiep vu lon cua phase 2 da duoc hoan thanh. Viec tiep theo la chuan hoa deployment, migration, permission, va dong bo du lieu production.
