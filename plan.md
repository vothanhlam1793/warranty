# Plan — Warranty Management System

## Tổng quan dự án

Phần mềm quản lý bảo hành nội bộ cho CRETA.
- Backend: Python FastAPI + SQLite (`apps/server/warranty.db`)
- Frontend: HTML/CSS/JS thuần, multi-page (`apps/web/`)
- Master data: Hàng hoá + Khách hàng từ KiotViet (hiện mock, cắm token thật sau)
- In phiếu: HTML → `window.print()` qua browser

---

## Cấu trúc thư mục (đã cập nhật)

```text
Warranty/
  apps/
    server/
      main.py              ← FastAPI app entry, CORS, serve web + uploads
      database.py          ← SQLite engine + get_db
      models.py            ← ORM models
      routers/
        tickets.py         ← CRUD phiếu, chuyển trạng thái, log, deadline/gia hạn
        masters.py         ← customers, products, suppliers CRUD + KiotViet search
        supplier_orders.py ← phiếu gửi NCC, in phiếu HTML
        transactions.py    ← thu/chi, báo cáo, in phiếu trả khách HTML
        tasks.py           ← dashboard việc cần làm + quick-state + upload evidence
      uploads/             ← ảnh bằng chứng B1/C5
      kiotviet/
        client.py          ← mock search KH + SP, chờ cắm token thật
      warranty.db          ← SQLite database
      .venv/
    web/
      assets/
        app.css
        api.js
      index.html           ← Dashboard + Việc cần làm
      tickets/
        list.html
        new.html
        detail.html        ← deadline, gia hạn, báo khách trễ, upload evidence
      supplier-orders/
        list.html
        new.html
      masters/
        suppliers.html
        customers.html
        products.html
      finance/
        report.html
  data/
    raw/
    processed/
    schema/
  scripts/
    prepare_data.py
    seed_db.py
  start.sh
  README.md
  plan.md
```

---

## Database hiện tại

### Bảng chính

| Bảng | Mô tả |
|---|---|
| `suppliers` | Nhà cung cấp |
| `customers` | Khách hàng |
| `products` | Hàng hoá |
| `tickets` | Phiếu bảo hành |
| `ticket_items` | Mã hàng trong phiếu |
| `workflow_logs` | Audit log chuyển trạng thái |
| `supplier_orders` | Phiếu gửi NCC |
| `supplier_order_items` | Mã hàng trong phiếu NCC |
| `transactions` | Thu/chi nội bộ |

### Cột quan trọng đã bổ sung

- `ticket_items.item_no` (INTEGER)
- `ticket_items.item_code` (TEXT, ví dụ `742-1`)
- `ticket_items.evidence_url` (TEXT, ảnh bằng chứng B1/C5)
- `tickets.deadline_date` (DATE, mặc định = `received_date + 14`)
- `tickets.extension_days` (INTEGER, tổng số ngày gia hạn)
- `tickets.notified_late` (BOOLEAN, đã gọi báo khách trễ hay chưa)

---

## Workflow chuẩn (A1 → C6)

```text
A1  Tiếp nhận / Test hàng
A2  Liên hệ khách chốt xử lý
A3  Chuẩn bị chuyển NCC
B1  Đã đóng bịch / chờ gửi NCC
B2  NCC đang xử lý (theo dõi tối đa 7 ngày từ B1)
C1  NCC trả về — kiểm tra lại
C2  PASS — chờ trả khách
C3  NO PASS — xử lý tiếp
C4  Cần thu tiền khách
C5  Đóng gói / đã xuất phiếu
C6  HOÀN THÀNH — đã trả khách
```

---

## SLA / deadline nghiệp vụ

- Từ ngày nhận A1 đến C6: tối đa 14 ngày.
- `deadline_date` được set tự động khi tạo phiếu: `received_date + 14`.
- Nếu trễ deadline:
  - Gắn cờ khẩn trên dashboard.
  - Bắt buộc gọi báo khách (ghi nhận `notified_late = true`).
  - Có thể gia hạn bằng lý do + số ngày.

---

## Tình trạng hiện tại

### Đã hoàn thành

- [x] Migrate DB + seed lại dữ liệu theo `item_no`/`item_code`.
- [x] Thống nhất `ticket_no` dạng số nguyên thuần (bỏ prefix `BH-`).
- [x] Hiển thị `item_code` nổi bật trên UI:
  - `tickets/new.html` (preview `?-1`, `?-2`)
  - `tickets/detail.html`
  - `tickets/list.html` (kèm search theo `item_code`)
  - `supplier-orders/new.html`
- [x] In phiếu thêm `item_code`:
  - Phiếu gửi NCC
  - Phiếu trả khách
- [x] Dashboard việc cần làm theo nhóm trạng thái.
- [x] Upload ảnh bằng chứng cho B1/C5, hiển thị thumbnail trên dashboard/detail.
- [x] Deadline 14 ngày + API gia hạn + API ghi nhận đã báo khách trễ.
- [x] `start.sh` đã chỉnh chạy backend đúng thư mục để tránh lỗi DB path/CORS giả.

### Đang triển khai (ưu tiên cao)

- [ ] Siết chặt quy tắc chuyển trạng thái (backend validation bắt buộc):
  - Bắt buộc có `actor` + `note` cho mọi lần chuyển.
  - Chỉ cho chuyển tuần tự theo luồng workflow, không nhảy cóc.
  - A3 → B1: bắt buộc đã có phiếu gửi NCC.
  - C4 → C5: bắt buộc đã có transaction `thu`.
  - C5 → C6: bắt buộc đã có ảnh bằng chứng (`evidence_url`).
- [ ] Đồng bộ UI frontend để ép nhập đủ dữ liệu trước khi cho chuyển.

---

## Cách khởi động

```bash
cd /Users/macos/Documents/Warranty
./start.sh

# Backend:  http://localhost:8000
# Frontend: http://localhost:3000
# API docs: http://localhost:8000/docs
```

### Khi cần reset dữ liệu

```bash
cd /Users/macos/Documents/Warranty
rm apps/server/warranty.db
cd apps/server
PYTHONPATH=/Users/macos/Documents/Warranty/apps /Users/macos/Documents/Warranty/apps/server/.venv/bin/python /Users/macos/Documents/Warranty/scripts/seed_db.py
```

---

## API chính (đã có)

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/api/tickets` | Tạo phiếu mới (sinh `item_code`, set `deadline_date`) |
| GET | `/api/tickets` | List phiếu, filter/search (`ticket_no`, khách, `item_code`, serial) |
| GET | `/api/tickets/{id}` | Chi tiết phiếu + items + thông tin deadline |
| GET | `/api/tickets/by-item-code/{code}` | Tìm phiếu theo mã xử lý |
| PATCH | `/api/tickets/{id}/items/{item_id}/state` | Chuyển trạng thái chi tiết |
| PATCH | `/api/tickets/{id}/items/{item_id}/quick-state` | Chuyển trạng thái nhanh từ dashboard |
| GET | `/api/tickets/{id}/items/{item_id}/logs` | Lịch sử log |
| POST | `/api/tickets/{id}/items/{item_id}/evidence` | Upload ảnh bằng chứng |
| POST | `/api/tickets/{id}/extend-deadline` | Gia hạn deadline (lý do + số ngày) |
| POST | `/api/tickets/{id}/notify-late` | Ghi nhận đã gọi báo khách trễ |
| GET | `/api/tasks/pending` | Danh sách việc cần làm + overdue/urgent/deadline flags |
| POST | `/api/supplier-orders` | Tạo phiếu gửi NCC |
| POST | `/api/supplier-orders/{id}/send` | Gửi NCC (items → B1) |
| POST | `/api/supplier-orders/{id}/receive-back` | Nhận hàng từ NCC về (items → C1) |
| GET | `/api/supplier-orders/{id}/print` | In phiếu gửi NCC |
| GET | `/api/transactions/{ticket_id}/print` | In phiếu trả khách |
| GET | `/api/transactions/report` | Báo cáo thu/chi + dashboard stats |

---

## KiotViet — cắm token thật sau

File: `apps/server/kiotviet/client.py`

Khi có token thật:
1. Set env: `KIOTVIET_TOKEN=xxx`, `KIOTVIET_RETAILER=your_retailer`
2. Mở phần real API trong `client.py`
3. Tắt mock section

---

## Backlog tiếp theo

- [ ] Hoàn tất backend validation chuyển trạng thái theo quy định CRETA.
- [ ] Phân quyền user (tiếp nhận / kỹ thuật / kế toán / quản lý).
- [ ] Global search theo `item_code` từ sidebar.
- [ ] Xuất báo cáo Excel / CSV.
- [ ] Kết nối KiotViet API thật.
