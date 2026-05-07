/**
 * Shared Layout Component
 * Tự động tạo Sidebar và Topbar User
 */

async function initLayout() {
    const user = await checkAuth().catch(() => null);
    if (!user) return;

    renderSidebar(user);
    renderTopbarUser(user);
    markActiveNav();
}

function renderSidebar(user) {
    const sidebarEl = document.querySelector('.sidebar');
    if (!sidebarEl) return;

    const isAdmin = user.role === 'admin';
    const path = window.location.pathname;

    sidebarEl.innerHTML = `
        <div class="sidebar-brand">
            <div class="logo">⚙ WARRANTY</div>
            <div class="sub">Quản lý bảo hành</div>
        </div>
        <nav>
            <div class="nav-group-label">Vận hành</div>
            <a class="nav-item ${path === '/' || path.endsWith('index.html') ? 'active' : ''}" href="/index.html">
                <span class="icon">▦</span>Dashboard
            </a>
            <a class="nav-item ${path.includes('/tickets/') ? 'active' : ''}" href="/tickets/list.html">
                <span class="icon">📋</span>Phiếu bảo hành
            </a>
            <a class="nav-item ${path.includes('/supplier-orders/') ? 'active' : ''}" href="/supplier-orders/list.html">
                <span class="icon">🚚</span>Phiếu gửi NCC
            </a>
            <a class="nav-item ${path.includes('/supplier-receives/') ? 'active' : ''}" href="/supplier-receives/list.html">
                <span class="icon">📥</span>Phiếu nhận NCC
            </a>
            <a class="nav-item ${path.includes('/return-slips/') ? 'active' : ''}" href="/return-slips/list.html">
                <span class="icon">🧾</span>Phiếu trả khách
            </a>
            
            ${isAdmin ? `
            <div class="nav-group-label">Hệ thống</div>
            <a class="nav-item ${path.includes('/admin/users') ? 'active' : ''}" href="/admin/users.html">
                <span class="icon">👤</span>Người dùng
            </a>
            <a class="nav-item ${path.includes('/admin/checklist-templates') ? 'active' : ''}" href="/admin/checklist-templates.html">
                <span class="icon">🧪</span>Mẫu checklist
            </a>
            ` : ''}

            <div class="nav-group-label">Danh mục</div>
            <a class="nav-item ${path.includes('/masters/suppliers') ? 'active' : ''}" href="/masters/suppliers.html">
                <span class="icon">🏭</span>Nhà cung cấp
            </a>
            <a class="nav-item ${path.includes('/masters/customers') ? 'active' : ''}" href="/masters/customers.html">
                <span class="icon">👤</span>Khách hàng
            </a>
            <a class="nav-item ${path.includes('/masters/products') ? 'active' : ''}" href="/masters/products.html">
                <span class="icon">📦</span>Sản phẩm
            </a>
            
            <div class="nav-group-label">Tài chính</div>
            <a class="nav-item ${path.includes('/finance/') ? 'active' : ''}" href="/finance/report.html">
                <span class="icon">💰</span>Thu / Chi
            </a>
        </nav>
    `;
}

function renderTopbarUser(user) {
    const el = document.getElementById("topbarUser");
    if (!el) return;
    el.innerHTML = `
        <span style="font-size:.85rem;color:var(--ink-3)">👤 ${user.display_name} (${user.role})</span>
        <button class="btn btn-ghost btn-sm" onclick="logout()" style="font-size:.8rem">Đăng xuất</button>
    `;
}

function markActiveNav() {
    // Logic highlight đã được tích hợp vào renderSidebar bằng path.includes
}

// Khởi tạo layout khi trang load
document.addEventListener('DOMContentLoaded', () => {
    // Chỉ chạy nếu không phải trang login
    if (!window.location.pathname.endsWith('login.html')) {
        initLayout();
    }
});
