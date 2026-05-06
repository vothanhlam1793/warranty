# Plan 4 — SLA B1/B2 theo ngày làm việc + Luồng nhận về qua phiếu NCC

> Ngày: 06/05/2026  
> Trạng thái: Planning  
> Mục tiêu: Chuẩn hoá vận hành nhóm B theo SLA cố định trước, mở rộng admin-config sau.

---

## 1) Scope chốt theo yêu cầu

- `B1` quá hạn khi > **2 ngày làm việc**
- `B2` quá hạn khi > **7 ngày làm việc**
- **Không tính Chủ nhật**
- Trước mắt fix cứng các ngưỡng
- Tương lai thêm trang Admin để chỉnh rule SLA
- Chuyển trạng thái `B -> C1` chỉ qua **phiếu nhận về NCC**

---

## 2) Nghiệp vụ chuẩn sau khi áp dụng

### 2.1 Nhóm gửi NCC

1. Tạo phiếu gửi NCC (bulk item)  
   - Item đủ điều kiện: `A3`  
   - Sau tạo phiếu: item `A3 -> B1`  
   - Phiếu NCC: `draft` (chờ gửi)

2. Xác nhận gửi NCC  
   - Bắt buộc có ảnh bằng chứng  
   - Phiếu NCC: `draft -> sent`  
   - Item trong phiếu: `B1 -> B2`

### 2.2 Nhóm nhận về NCC

3. Lập phiếu nhận về NCC (bulk)  
   - Chỉ nhận item đang `B2` (khuyến nghị chuẩn)  
   - Cùng NCC theo chứng từ nhận hàng  
   - Sau xác nhận phiếu nhận: item `B2 -> C1`

4. Không cho đổi tay `B -> C1` qua quick-state.

---

## 3) Thiết kế kỹ thuật

## 3.1 SLA calculator (backend)

Tạo helper tính **ngày làm việc** (working days):

- Input: `from_date`, `to_date`
- Rule: bỏ qua Chủ nhật (`weekday == 6`)
- Output: số ngày làm việc chờ xử lý

Áp dụng vào dữ liệu task pending và các điểm hiển thị overdue:

- `B1`: overdue nếu `working_days > 2`
- `B2`: overdue nếu `working_days > 7`

File dự kiến:
- `apps/server/utils/sla.py` (mới)
- `apps/server/routers/tasks.py` (dùng helper thay cách tính cũ)

## 3.2 Rule transition locking

Siết endpoint quick-state:

- Chặn `A3 -> B1` (đi qua tạo phiếu NCC)
- Chặn `B1 -> B2` (đi qua xác nhận gửi)
- Chặn `B2 -> C1` (đi qua phiếu nhận về)

File:
- `apps/server/routers/tasks.py`

## 3.3 Phiếu nhận về NCC (mới)

Thêm model/route cho phiếu nhận về:

- `SupplierReceive` (header)
  - `receive_no`, `supplier_id`, `received_date`, `actor`, `note`, `created_at`
- `SupplierReceiveItem` (detail)
  - `receive_id`, `ticket_item_id`, `result`, `result_note`

Endpoint dự kiến:

- `POST /api/supplier-receives`  
  Tạo phiếu nhận + bulk move `B2 -> C1` + workflow logs
- `GET /api/supplier-receives`  
  Danh sách phiếu nhận
- `GET /api/supplier-receives/{id}`  
  Chi tiết phiếu nhận

Validation:

- Item phải thuộc NCC tương ứng
- Item phải đang ở `B2`
- Không cho nhận trùng item đã qua `C1+`

Files:
- `apps/server/models.py`
- `apps/server/routers/supplier_receives.py` (mới)
- `apps/server/main.py` (mount router)

## 3.4 Dashboard/UI

Trên dashboard (`apps/web/index.html`):

- Tách rõ nhóm `B1` và `B2`
- Badge overdue dựa trên working day SLA mới
- Bỏ đường tắt state trực tiếp cho các bước bị khoá
- Hành động thay thế:
  - B1: mở phiếu NCC để xác nhận gửi
  - B2: mở trang phiếu nhận về NCC

## 3.5 Trang phiếu nhận về NCC

Tạo mới frontend:

- `apps/web/supplier-receives/new.html`
  - Chọn NCC
  - Load item đang `B2` của NCC
  - Chọn nhiều item -> lập phiếu nhận
- `apps/web/supplier-receives/list.html`
  - Danh sách phiếu nhận
- `apps/web/supplier-receives/detail.html`
  - Xem chi tiết item nhận về

---

## 4) Data migration & compatibility

- Vì SQLite + create_all, thêm bảng mới theo model mới
- Không xoá flow cũ ngay; deprecate endpoint nhận về cũ theo soft-path
- Với dữ liệu đang ở B-state cũ: vẫn hiển thị bình thường, chỉ khóa chuyển tay dần

---

## 5) QA checklist

1. Item `B1` sau 2 ngày làm việc hiển thị overdue đúng (bỏ Chủ nhật)
2. Item `B2` sau 7 ngày làm việc hiển thị overdue đúng (bỏ Chủ nhật)
3. Quick-state bị chặn đúng các cặp trạng thái đã khoá
4. Tạo phiếu gửi NCC: `A3 -> B1` đúng cho tất cả item trong phiếu
5. Xác nhận gửi NCC có evidence: `B1 -> B2` đúng bulk
6. Tạo phiếu nhận về NCC: chỉ nhận item `B2`, nhận xong `B2 -> C1`
7. Workflow log có actor/note đúng ngữ nghĩa hành động

---

## 6) Roadmap triển khai

### Phase 1 (ưu tiên cao)
- Helper SLA working days
- Áp dụng SLA B1/B2 trong tasks dashboard
- Khóa quick-state cho các bước bắt buộc nghiệp vụ

### Phase 2
- Backend phiếu nhận về NCC (model + API)
- Frontend new/list/detail cho supplier-receives

### Phase 3
- Polish UI dashboard nhóm B
- Regression full luồng ticket -> NCC -> nhận về -> C1

### Phase 4 (tương lai admin setup)
- Tạo bảng cấu hình `system_settings` hoặc `sla_settings`
- Mặc định:
  - `sla_b1_days = 2`
  - `sla_b2_days = 7`
  - `exclude_sunday = true`
- Sau đó thêm trang admin CRUD setting

---

## 7) Kết quả mong đợi

- KPI vận hành rõ ràng cho nhóm B
- Phân biệt được “chờ gửi nội bộ” (B1) và “NCC giữ hàng” (B2)
- Không còn chuyển trạng thái thiếu chứng từ
- Luồng nhận về chuẩn hóa bằng phiếu nhận NCC
- Sẵn nền tảng để mở trang admin cấu hình SLA sau này
