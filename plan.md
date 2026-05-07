# Plan

## Role of This File

File nay khong lap lai setup guide hay architecture reference.

No duoc dung de ghi:

- current state sau release `1.2.0`
- cac quyet dinh nghiep vu/ky thuat da chot
- backlog uu tien tiep theo

## Current State

### Release baseline

- current release line: `1.2.0`
- default working branch sau release: `main`
- backend runtime: FastAPI + SQLAlchemy
- frontend runtime: static multi-page HTML/CSS/JS
- primary DB: PostgreSQL
- legacy fallback DB: SQLite
- master data direction: Odoo-first

### What is working now

#### Auth and admin

- login/logout/me theo session cookie
- admin user management
- role-based menu rendering

#### Ticket workflow

- tao ticket
- list/search/detail
- state transition
- rollback
- deadline extension
- notify late

#### Supplier workflow

- phieu gui NCC
- xac nhan gui NCC co evidence image
- phieu nhan NCC tra ve
- in phieu NCC

#### Checklist workflow

- checklist templates
- template mapping theo stage/item
- checklist run
- evidence upload
- finalize conclusion

#### Return workflow

- tao phieu tra khach
- candidate items tu C2/C3
- confirm pack C4 -> C5
- confirm delivered C5 -> C6
- image evidence cho pack/delivered
- print return slip

#### Master data

- customer/product/supplier pages
- customer/product sync theo Odoo
- customer merge theo phone
- customer_code support (`KHxxxxxx`)

#### Frontend structure

- shared sidebar qua `layout.js`
- shared API/auth helpers qua `api.js`
- da loai bo phan lon sidebar hardcode cu

## Confirmed Business Rules

### Customer identity

- `phone` la ID goc cua customer trong van hanh noi bo
- `customer_code` la external/master reference
- trung `phone` thi co the merge customer
- khi merge/sync, uu tien du lieu Odoo

### Evidence-driven transitions

- gui NCC phai co anh bang chung
- return slip C4/C5 da theo UX `chon anh -> bam xac nhan -> he thong upload va chuyen buoc`

### Actor handling

- backend co the resolve actor tu session
- frontend nen uu tien auto-fill actor theo user dang nhap
- khong bat user nhap ten thu cong o cac step thong thuong neu khong can thiet

## Active Technical Debt

### High priority

- chua co Alembic migrations chuan
- `database.py` van con schema patch logic cho compatibility
- permission model chua du chi tiet theo endpoint/action
- `.env.example` chua khop hoan toan runtime that
- con mot so script/tooling cu chua theo runtime hien tai

### Medium priority

- con kha nhieu naming legacy `kiotviet_*`
- docs phu can tiep tuc don dep them (`plan_1.md`, mot so note cu)
- can review lai toan bo UI de bat cac cho con sot sau khi migrate sang `layout.js`

## Next Priorities

### P1

1. Dua schema migration sang Alembic.
2. Chot permission matrix theo role va action.
3. Sieu chat workflow validation o backend.
4. Chuan hoa `.env.example` va startup/proxy scripts cho dung runtime hien tai.

### P2

1. Giam debt compatibility schema legacy.
2. Chuan hoa naming field external/master data.
3. Review va polish UX cac flow co upload evidence.
4. Hoan thien docs con lai de theo dung role tung file.

### P3

1. Chot migration strategy tu SQLite neu can giu du lieu cu.
2. Xem lai integration boundary giua Odoo data va local runtime data.
3. Can nhac tach reusable frontend patterns cho modal/form-heavy pages.

## Working Notes

Khi co release moi, file nay nen duoc cap nhat theo huong:

- bo sung current state moi
- bo nhung backlog da xong
- khong chen lai setup guide hay architecture detail
