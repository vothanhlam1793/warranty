# Plan

## Role of This File

File này không lặp lại setup guide hay architecture reference.

Nó được dùng để ghi:

- current state sau release `1.3.0`
- các quyết định nghiệp vụ/kỹ thuật đã chốt
- backlog ưu tiên tiếp theo

## Current State

### Release baseline

- current release line: `1.3.0`
- default working branch sau release: `main`
- backend runtime: FastAPI + SQLAlchemy
- frontend runtime: static multi-page HTML/CSS/JS
- primary DB: PostgreSQL
- legacy fallback DB: SQLite
- master data direction: Odoo-first
- production deploy: Docker Compose + reverse proxy

### What is working now

#### Auth and admin

- login/logout/me theo session cookie
- admin user management
- role-based menu rendering

#### Ticket workflow

- tạo ticket
- list/search/detail
- state transition
- rollback
- deadline extension
- notify late

#### Ticket-item workflow

- item-first detail page theo `item_code`
- checklist, lịch sử, ảnh minh chứng và liên kết nghiệp vụ theo từng item

#### Supplier workflow

- phiếu gửi NCC
- xác nhận gửi NCC có evidence image
- phiếu nhận NCC trả về
- in phiếu NCC
- legacy backfill phiếu NCC cho item imported ở B1/B2

#### Checklist workflow

- checklist templates
- template mapping theo stage/item
- checklist run
- evidence upload tự động khi chọn file
- finalize conclusion

#### Return workflow

- tạo phiếu trả khách
- candidate items từ C2/C3
- confirm pack C4 -> C5
- confirm delivered C5 -> C6
- image evidence cho pack/delivered
- print return slip

#### Master data and legacy import

- customer/product/supplier pages
- customer/product sync theo Odoo
- import legacy CSV theo snapshot state
- backfill expected/returned dates theo rule `received_date + 14 ngày`

## Confirmed Business Rules

### Customer identity

- `phone` là ID gốc của customer trong vận hành nội bộ
- `customer_code` là external/master reference
- trùng `phone` thì có thể merge customer
- khi merge/sync, ưu tiên dữ liệu Odoo

### Evidence-driven transitions

- gửi NCC phải có ảnh bằng chứng
- return slip C4/C5 theo UX `chọn ảnh -> bấm xác nhận -> hệ thống upload và chuyển bước`
- checklist run evidence hiện auto-upload khi chọn file

### Legacy import

- import theo snapshot state hiện tại của item
- không replay lại lịch sử workflow cũ
- deadline/expected return/returned date theo quy tắc `Ngày nhận + 14 ngày` nếu thiếu dữ liệu rõ ràng hơn

### Actor handling

- backend có thể resolve actor từ session
- frontend nên ưu tiên auto-fill actor theo user đang đăng nhập
- không bắt user nhập tên thủ công ở các step thông thường nếu không cần thiết

## Active Technical Debt

### High priority

- chưa có Alembic migrations chuẩn
- `database.py` vẫn còn schema patch logic cho compatibility
- permission model chưa đủ chi tiết theo endpoint/action
- `.env.example` chưa khớp hoàn toàn runtime thật

### Medium priority

- còn khá nhiều naming legacy `kiotviet_*`
- nên tiếp tục đẩy item-level actions vào `ticket-items/detail.html`
- cần review lại toàn bộ UI để bắt các chỗ còn sót sau khi migrate sang `layout.js`

## Next Priorities

### P1

1. Đưa schema migration sang Alembic.
2. Chốt permission matrix theo role và action.
3. Siết chặt workflow validation ở backend.
4. Chuẩn hóa `.env.example` và startup/proxy scripts cho đúng runtime hiện tại.

### P2

1. Giảm debt compatibility schema legacy.
2. Chuẩn hóa naming field external/master data.
3. Hoàn thiện item-detail thành màn thao tác chính cho từng mã.
4. Hoàn thiện docs còn lại theo đúng role từng file.

### P3

1. Chốt migration strategy từ SQLite nếu cần giữ dữ liệu cũ.
2. Xem lại integration boundary giữa Odoo data và local runtime data.
3. Cân nhắc tách reusable frontend patterns cho modal/form-heavy pages.

## Working Notes

### Hotfix Notes

- hotfix branch `hotfix/a2-to-a3-action` bổ sung lại action `A2 -> A3` trên `ticket-items/detail.html`
- nguyên nhân: sau khi mở rộng item detail cho checklist workflow, UI detail page bị sót nút chuyển `A2 -> A3` dù backend vẫn cho phép transition này
- đã deploy lại Docker Compose trên runtime hiện tại để bản chạy ở cổng `3001` nhận hotfix

Khi có release mới, file này nên được cập nhật theo hướng:

- bổ sung current state mới
- bỏ những backlog đã xong
- không chèn lại setup guide hay architecture detail
