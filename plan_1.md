# Plan 1 — Warranty Management System: Thiết kế chi tiết phase 2

> Ngày: 06/05/2026  
> Trạng thái: Đang triển khai (Hoàn thành 70%)  
> Dev phụ trách: Opencode (AI Agent)

---

## Tổng quan thay đổi

10 yêu cầu từ review, chia thành:
- **Sửa lỗi ngay** (items 3, 4): ✅ Hoàn thành
- **Tính năng nhỏ** (items 1, 2, 3): ✅ Hoàn thành
- **Tính năng lớn** (items 2, 5, 6, 7, 8, 9, 10): 🔄 Đã xong Auth/NCC, còn Checklist & Phiếu trả khách.

---

## 1. Dự kiến trả mặc định (✅ Xong)
...
## 2. Đăng nhập (Authentication) (✅ Xong)
...
## 3. Fix lỗi [object Object] — api.js (✅ Xong)
...
## 4. Fix supplier-orders/new.html (✅ Xong)
...
## 5. Nút Rollback trạng thái (✅ Xong)
...
## 6. Xác nhận gửi NCC + bằng chứng (✅ Xong)
...
## 7. Phiếu nhận hàng từ NCC (✅ Xong)
...

---

## 8. Checklist kiểm tra tại C1 (⏳ Chờ triển khai)
...
## 9. Phiếu trả khách (⏳ Chờ triển khai)
...
## 10. C5 → C6 (⏳ Chờ triển khai)
...

---

## Tổng hợp — Danh sách việc cần làm cho dev

### Ưu tiên 1 — Sửa lỗi ngay (ĐÃ XONG)

| # | File | Việc | Trạng thái |
|---|---|---|---|
| 1a | `apps/web/assets/api.js` | Fix error handling 422 | ✅ Done |
| 1b | `apps/web/supplier-orders/new.html` | Filter A3, actor input, try/catch | ✅ Done |
| 1c | `apps/web/tickets/new.html` | Auto-fill expected_return_date | ✅ Done |
| 1d | `apps/web/tickets/detail.html` | Default expected in modal A1 | ✅ Done |

### Ưu tiên 2 — Tính năng nhỏ (ĐÃ XONG)

| # | File | Việc | Trạng thái |
|---|---|---|---|
| 2a | `apps/server/routers/tickets.py` | Endpoint `/rollback` | ✅ Done |
| 2b | `apps/web/tickets/detail.html` | Nút "Hoàn tác" + modal | ✅ Done |
| 2c | `apps/web/supplier-orders/detail.html` | UI gửi NCC + bằng chứng | ✅ Done |

### Ưu tiên 3 — Tính năng trung bình (ĐÃ XONG)

| # | File | Việc | Trạng thái |
|---|---|---|---|
| 3a | `apps/server/models.py` | User, Session models | ✅ Done |
| 3b | `apps/server/routers/auth.py` | Login/Logout/Me | ✅ Done |
| 3c | `apps/server/main.py` | Auth middleware | ✅ Done |
| 3d | `apps/web/login.html` | Trang đăng nhập | ✅ Done |
| 3e | `apps/web/assets/api.js` | checkAuth(), currentUser | ✅ Done |
| 3f | `apps/web/supplier-orders/receive.html` | Phiếu nhận NCC | ✅ Done |

### Ưu tiên 4 — Tính năng lớn (TIẾP THEO)

| # | File | Việc | Trạng thái |
|---|---|---|---|
| 4a | `apps/server/models.py` | Checklist, ReturnSlip models | ⏳ Pending |
| 4b | `apps/server/routers/checklist.py` | Router Checklist | ⏳ Pending |
| 4c | `apps/server/routers/return_slips.py` | Router Phiếu trả | ⏳ Pending |
| 4d | `apps/web/tickets/checklist.html` | Trang kiểm tra C1 | ⏳ Pending |
| 4e | `apps/web/return-slips/new.html` | Lập phiếu trả khách | ⏳ Pending |
| 4f | `apps/web/tickets/detail.html` | Nút C1→Checklist, C2/C3→Phiếu trả | ⏳ Pending |


### Ưu tiên 4 — Tính năng lớn (1-2 tuần)

| # | File | Việc |
|---|---|---|
| 4a | `apps/server/models.py` | Thêm ChecklistTemplate, ChecklistResult, ReturnSlip, ReturnSlipItem |
| 4b | `apps/server/routers/checklist.py` | Tạo mới |
| 4c | `apps/server/routers/return_slips.py` | Tạo mới |
| 4d | `apps/server/main.py` | Mount 2 router mới |
| 4e | `apps/web/tickets/checklist.html` | Tạo mới: trang kiểm tra C1 |
| 4f | `apps/web/return-slips/new.html` | Tạo mới: lập phiếu trả khách |
| 4g | `apps/web/return-slips/list.html` | Tạo mới: danh sách phiếu trả |
| 4h | `apps/web/tickets/detail.html` | Cập nhật nút C1→checklist, C2/C3→return-slip |

---

## Ghi chú kỹ thuật

### Password hashing
Dùng `passlib[bcrypt]`: `pip install passlib[bcrypt]`

### Session storage
Lưu trong SQLite (bảng `sessions`) — đủ đơn giản cho nội bộ, không cần Redis.

### Checklist template seed
Tạo 1 template mặc định (áp dụng cho mọi sản phẩm) khi seed DB:
```json
[
  {"label": "Kiểm tra ngoại quan (trầy, bể, cong vênh)", "required": true},
  {"label": "Bật nguồn được", "required": true},
  {"label": "Chức năng chính hoạt động bình thường", "required": true},
  {"label": "Phụ kiện đầy đủ theo phiếu", "required": false},
  {"label": "Serial khớp với phiếu", "required": true}
]
```

### Return slip numbering
Format: `TK-{year}{month}-{seq:04d}` — VD: `TK-202605-0001`

### Migration DB
Vì dùng SQLite không có Alembic, mỗi lần thêm bảng cần:
```bash
# Cách 1: Reset hoàn toàn (dev)
rm apps/server/warranty.db && python scripts/seed_db.py

# Cách 2: Migrate thủ công (production — giữ data)
sqlite3 apps/server/warranty.db < scripts/migrate_phase2.sql
```
→ Dev cần tạo file `scripts/migrate_phase2.sql` với các lệnh `ALTER TABLE` và `CREATE TABLE`.
