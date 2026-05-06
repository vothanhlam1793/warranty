# Plan 5 — Checklist kiểm tra A2 (Pre-check) + C1 (Return-check)

> Ngày: 06/05/2026  
> Trạng thái: Planning  
> Mục tiêu: Tổ chức hệ thống checklist kiểm tra 2 tầng (A2 trước gửi NCC, C1 sau nhận về) với audit đầy đủ, ảnh minh chứng, lịch sử mapping template.

---

## 1) Tổng quan nghiệp vụ đã chốt

### 1.1 A2 Pre-check (kiểm tra sơ bộ trước gửi NCC)
- **Mục tiêu:** Ghi nhận hiện trạng sản phẩm trước khi gửi NCC, tránh tranh cãi sau B1/B2.
- **Ảnh minh chứng:** Optional
- **Kết luận:** Không cần PASS/FAIL — chỉ cần hoàn thành checklist (ghi nhận lỗi, đánh giá sơ bộ).
- **Bắt buộc hay không:** Theo từng sản phẩm (`a2_required = true/false`).
  - `a2_required=true`: phải có run A2 `completed` mới cho đi A2 -> A3.
  - `a2_required=false`: có thể bỏ qua, nhưng vẫn cho làm nếu muốn.

### 1.2 C1 Return-check (kiểm tra sau khi NCC trả về)
- **Mục tiêu:** Kiểm tra toàn diện, đưa ra kết luận chính thức PASS/FAIL.
- **Ảnh minh chứng:** Bắt buộc tối thiểu 1 ảnh.
- **Kết luận:** Bắt buộc PASS hoặc FAIL.
  - `PASS` -> C2 (chờ trả khách)
  - `FAIL` -> C3 (xử lý tiếp)
- **Bắt buộc:** Không cho C1 -> C2/C3 nếu chưa có run C1 finalized.

### 1.3 Mapping template
- Chọn template từ bước A1/A2.
- Cho phép điều chỉnh mapping TRƯỚC khi bắt đầu run checklist.
- Sau khi đã tạo run thì `locked = true`, không được đổi.
- Mọi lần đổi mapping đều phải có `actor` + `reason` + ghi audit.

### 1.4 Template theo nhóm sản phẩm
- Bắt đầu theo **nhóm sản phẩm** (Camera, Đầu ghi, Switch, POE...).
- Sau cho override theo model cụ thể nếu cần.
- Mỗi template thuộc `stage`: `A2_PRECHECK` hoặc `C1_RETURN`.
- Có thể tạo nhiều template cho mỗi stage.

---

## 2) Mô hình dữ liệu (models.py)

### 2.1 ChecklistTemplate
```
id, name, stage (A2_PRECHECK|C1_RETURN), description, is_active, created_at
```

### 2.2 ChecklistTemplateItem
```
id, template_id (FK), label, required (bool), sort_order,
input_type (boolean|text|note_only), created_at
```

### 2.3 Trên TicketItem (bổ sung field)
```
a2_template_id (FK nullable)
c1_template_id (FK nullable)
a2_template_locked (bool, default False)
c1_template_locked (bool, default False)
```

### 2.4 ChecklistTemplateChange (audit mapping)
```
id, ticket_item_id (FK), stage (A2|C1),
from_template_id (nullable), to_template_id (nullable),
changed_by, reason, changed_at
```

### 2.5 ChecklistRun (phiên kiểm tra)
```
id, ticket_item_id (FK), template_id (FK), stage,
inspector, note, conclusion (completed|pass|fail|draft),
created_at, finalized_at
```

### 2.6 ChecklistRunItem (kết quả từng mục)
```
id, run_id (FK), template_item_id (FK),
checked (bool), value_text (nullable), note (nullable)
```

### 2.7 ChecklistEvidence (ảnh minh chứng)
```
id, run_id (FK), file_url, caption (nullable), created_at
```

---

## 3) API Endpoints (router mới: /api/checklists)

### 3.1 Template CRUD
- `GET /api/checklists/templates` — Danh sách template
- `POST /api/checklists/templates` — Tạo template mới
- `GET /api/checklists/templates/{id}` — Chi tiết template + items
- `PUT /api/checklists/templates/{id}` — Sửa template
- `POST /api/checklists/templates/{id}/items` — Thêm item vào template
- `DELETE /api/checklists/templates/{id}/items/{item_id}` — Xóa item

### 3.2 Mapping template cho ticket item
- `GET /api/checklists/mapping/{ticket_item_id}` — Xem mapping hiện tại + lịch sử
- `POST /api/checklists/mapping/{ticket_item_id}` — Đặt/đổi template (kèm actor + reason)

### 3.3 Checklist run
- `POST /api/checklists/runs` — Tạo run mới (stage + ticket_item_id)
- `GET /api/checklists/runs/{run_id}` — Chi tiết run + items + evidence
- `GET /api/checklists/runs?ticket_item_id=...` — Tất cả run của 1 item
- `PATCH /api/checklists/runs/{run_id}/items` — Cập nhật kết quả từng mục
- `POST /api/checklists/runs/{run_id}/evidence` — Upload ảnh minh chứng
- `DELETE /api/checklists/runs/{run_id}/evidence/{ev_id}` — Xóa ảnh
- `POST /api/checklists/runs/{run_id}/finalize` — Finalize run
  - A2: `conclusion = completed` -> cập nhật `a2_template_locked = true`
  - C1: `conclusion = pass|fail` -> chuyển trạng thái C2/C3 + `c1_template_locked = true`

---

## 4) Rule validate backend

### 4.1 Mapping
- Chỉ đổi template khi `locked = false`.
- Phải có `actor` + `reason` mỗi lần đổi.
- Ghi audit vào `ChecklistTemplateChange`.

### 4.2 A2 Run
- Chỉ tạo run A2 khi item đang ở `A2` state.
- `a2_template_id` phải có trước khi tạo run.
- Nếu `a2_required = true`:
  - quick-state A2->A3 bị chặn nếu chưa có run `completed`.
- Ảnh optional.

### 4.3 C1 Run
- Chỉ tạo run C1 khi item đang ở `C1` state.
- `c1_template_id` phải có trước khi tạo run.
- Finalize phải có `conclusion = pass|fail`.
- Phải có tối thiểu 1 ảnh evidence trước khi finalize.
- Quick-state C1->C2/C3 bị chặn nếu chưa có run finalized.

### 4.4 Duplicate run
- Mỗi item chỉ có 1 run `active` (not finalized) tại 1 thời điểm.
- Sau finalize vẫn cho tạo run mới (trường hợp kiểm lại).

---

## 5) Frontend

### 5.1 Trang quản lý template (admin)
- `apps/web/admin/checklist-templates.html`
  - Danh sách template theo stage
  - Nút tạo mới, sửa, deactivate
  - Inline edit checklist items (label, required, sort_order)

### 5.2 Ticket detail — mapping + run
- `apps/web/tickets/detail.html` (bổ sung):
  - Section "Checklist" trên mỗi item:
    - Hiển thị template đang map (A2 / C1)
    - Nút "Chọn template" (nếu chưa lock)
    - Nút "🧪 Test nhanh A2" (nếu item ở A2, có template)
    - Nút "🔍 Kiểm tra C1" (nếu item ở C1, có template)
    - Xem kết quả run gần nhất (inline summary)

### 5.3 Trang thực hiện kiểm tra
- `apps/web/checklists/run.html?run_id=...` hoặc modal lớn
  - Hiển thị từng mục checklist với checkbox + note
  - Section upload ảnh minh chứng
  - Note tổng + tên người kiểm
  - Nút Lưu nháp / Hoàn thành
  - Với C1: 2 nút kết luận `PASS -> C2`, `FAIL -> C3`

### 5.4 Xem hồ sơ kiểm tra
- Trên ticket detail:
  - Tab / accordion "Hồ sơ A2" + "Hồ sơ C1"
  - Hiển thị: ai kiểm, lúc nào, từng mục tick, note, ảnh
  - Nếu có nhiều run: xem theo thứ tự thời gian

---

## 6) Seed data mẫu template

### Template: Camera (A2_PRECHECK)
1. Ngoại quan: vỏ máy không trầy, bể, biến dạng
2. Nguồn: bật nguồn được
3. Hình ảnh: có tín hiệu hình ảnh
4. Lỗi mô tả của khách: đã tái hiện được / không tái hiện
5. Serial: khớp với phiếu

### Template: Camera (C1_RETURN)
1. Ngoại quan sau bảo hành
2. Bật nguồn được
3. Hình ảnh rõ, đúng thông số
4. Chức năng chính hoạt động bình thường
5. Lỗi cũ đã được xử lý
6. Serial khớp với phiếu
7. Phụ kiện đầy đủ

### Template: Đầu ghi (C1_RETURN)
1. Ngoại quan sau bảo hành
2. Bật nguồn, boot bình thường
3. Nhận đủ camera theo cấu hình cũ
4. Ghi hình được
5. Playback bình thường
6. HDD nhận đúng dung lượng
7. Lỗi cũ đã được xử lý
8. Serial khớp với phiếu

---

## 7) Migration & compatibility

- Thêm bảng mới, không xóa bảng cũ.
- Thêm 4 field nullable vào `ticket_items` (SQLite: thêm via CREATE TABLE mới hoặc ALTER).
- Seed template mẫu khi khởi động lần đầu nếu bảng trống.

---

## 8) Files cần tạo/sửa

### Backend
- `apps/server/models.py` — Thêm 7 model mới
- `apps/server/routers/checklists.py` — Router mới (tất cả endpoints)
- `apps/server/routers/tasks.py` — Chặn thêm: A2->A3 nếu a2_required, C1->C2/C3 nếu chưa run
- `apps/server/main.py` — Mount router checklist

### Frontend
- `apps/web/admin/checklist-templates.html` — Tạo mới
- `apps/web/checklists/run.html` — Tạo mới (trang thực hiện kiểm tra)
- `apps/web/tickets/detail.html` — Bổ sung section checklist per item

---

## 9) QA Checklist sau implement

1. Tạo template Camera A2 + C1, template Đầu ghi C1 thành công
2. Map template vào ticket item ở A2:
   - Đổi mapping 2 lần → lịch sử audit đầy đủ
3. Item `a2_required=true`:
   - Chưa có run A2 → chặn A2->A3
   - Có run A2 completed → cho đi
4. Run A2:
   - tick checklist + note + optional ảnh → finalize thành công
   - Xem hồ sơ A2 trên ticket detail
5. Run C1:
   - tick checklist + upload ảnh → finalize PASS → item sang C2
   - tick checklist + upload ảnh → finalize FAIL → item sang C3
   - Chưa có ảnh → chặn finalize C1
6. Không có run C1 finalized → chặn quick C1->C2/C3
7. Xem hồ sơ kiểm tra đầy đủ (A2 + C1) trên ticket detail

---

## 10) Roadmap triển khai

### Phase 1 — Backend core
- Models + migration
- Router template CRUD
- Router mapping + audit
- Router run + evidence
- Finalize logic + state transition

### Phase 2 — Frontend
- Admin trang quản lý template
- Ticket detail: section checklist mapping + run
- Trang thực hiện kiểm tra (run.html)

### Phase 3 — Polish
- Seed template mẫu Camera + Đầu ghi
- Lock/audit enforcement đầy đủ
- Xem hồ sơ kiểm tra theo timeline
- Regression full luồng A1->A2->A3->B1->B2->C1->C2/C3

---

## 11) Kết quả mong đợi

- Mỗi mã hàng có "hồ sơ kiểm tra" đầy đủ 2 tầng (A2 pre-check + C1 return-check).
- Không còn tranh cãi trước/sau NCC (ảnh hiện trạng A2 là bằng chứng).
- C2/C3 chỉ đạt khi kiểm tra C1 đã hoàn chỉnh + có ảnh.
- Admin tạo/chỉnh template linh hoạt không cần code.
- Audit đầy đủ: ai làm, lúc nào, đổi gì, vì sao.
