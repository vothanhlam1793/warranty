/* global API wrapper + helpers */
const API = "http://localhost:8000";

let currentUser = null;

const STATE_LABELS = {
  A1:"Tiếp nhận / Test", A2:"Liên hệ khách", A3:"Chuyển NCC",
  B1:"NCC đang xử lý", B2:"Xử lý dài hạn",
  C1:"NCC trả về - kiểm tra", C2:"PASS - chờ trả", C3:"NO PASS",
  C4:"Cần thu tiền", C5:"Đã xuất phiếu", C6:"Hoàn thành",
};
const ACTION_LABELS = {
  bao_hanh:"Bảo hành", sua_chua:"Sửa chữa", tra_hang:"Trả hàng",
  doi_moi:"Đổi mới", hang_muon:"Hàng mượn", khong_ro:"Không rõ",
};

async function apiFetch(path, opts = {}) {
  const r = await fetch(API + path, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    const msg = Array.isArray(err.detail)
      ? err.detail.map(e => `${e.loc?.slice(-1)[0] ?? ''}: ${e.msg}`).join("; ")
      : (typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
    throw new Error(msg || r.statusText);
  }
  return r.json();
}

const api = {
  get:    (path)         => apiFetch(path),
  post:   (path, body)   => apiFetch(path, { method:"POST",  body }),
  put:    (path, body)   => apiFetch(path, { method:"PUT",   body }),
  patch:  (path, body)   => apiFetch(path, { method:"PATCH", body }),
  delete: (path)         => apiFetch(path, { method:"DELETE" }),
};

/* ── Toast ── */
function toast(msg, type = "success", duration = 3000) {
  let c = document.getElementById("toast-container");
  if (!c) { c = document.createElement("div"); c.id = "toast-container"; document.body.appendChild(c); }
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), duration);
}

/* ── Modal helpers ── */
function openModal(id)  { document.getElementById(id)?.classList.remove("hidden"); }
function closeModal(id) { document.getElementById(id)?.classList.add("hidden"); }

/* ── Format helpers ── */
function fmtDate(iso) {
  if (!iso) return "—";
  const [y,m,d] = iso.split("-");
  return `${d}/${m}/${y}`;
}
function fmtMoney(n) {
  if (!n && n !== 0) return "—";
  return Number(n).toLocaleString("vi-VN") + "đ";
}
function stateBadge(s) {
  return `<span class="badge state-${s}">${s} ${STATE_LABELS[s] || ""}</span>`;
}
function actionBadge(a) {
  const colors = {
    bao_hanh:"badge-teal", sua_chua:"badge-blue", tra_hang:"badge-gray",
    doi_moi:"badge-yellow", hang_muon:"badge-gray", khong_ro:"badge-red",
  };
  return `<span class="badge ${colors[a]||'badge-gray'}">${ACTION_LABELS[a]||a}</span>`;
}

/* ── Autocomplete ── */
function setupAutocomplete({ input, listEl, fetchFn, onSelect }) {
  let active = false;
  input.addEventListener("input", async () => {
    const q = input.value.trim();
    if (q.length < 1) { listEl.innerHTML = ""; listEl.style.display = "none"; return; }
    const results = await fetchFn(q).catch(() => []);
    listEl.innerHTML = "";
    if (!results.length) { listEl.style.display = "none"; return; }
    listEl.style.display = "block";
    results.forEach(item => {
      const div = document.createElement("div");
      div.className = "autocomplete-item";
      div.innerHTML = onSelect.renderItem(item);
      div.addEventListener("click", () => {
        onSelect.pick(item);
        listEl.style.display = "none";
      });
      listEl.appendChild(div);
    });
  });
  document.addEventListener("click", e => {
    if (!input.contains(e.target) && !listEl.contains(e.target)) {
      listEl.style.display = "none";
    }
  });
}

/* ── Auth helpers ── */
async function checkAuth() {
  try {
    const data = await api.get("/api/auth/me");
    currentUser = data.user;
    _renderUserTopbar();
    return currentUser;
  } catch(_) {
    const next = encodeURIComponent(location.pathname + location.search);
    location.href = `/login.html?next=${next}`;
    throw new Error("Chưa đăng nhập");
  }
}

async function logout() {
  try { await api.post("/api/auth/logout", {}); } catch(_) {}
  location.href = "/login.html";
}

function _renderUserTopbar() {
  if (!currentUser) return;
  // Hiển thị tên user ở topbar nếu có element
  const el = document.getElementById("topbarUser");
  if (el) {
    el.innerHTML = `<span style="font-size:.85rem;color:var(--ink-3)">👤 ${currentUser.display_name}</span>
      <button class="btn btn-ghost btn-sm" onclick="logout()" style="font-size:.8rem">Đăng xuất</button>`;
  }
}

/* ── Mark active nav ── */
function markActiveNav() {
  const path = location.pathname;
  document.querySelectorAll(".nav-item").forEach(a => {
    const href = a.getAttribute("href") || "";
    a.classList.toggle("active", path.endsWith(href) || (href !== "/" && path.includes(href.replace(".html",""))));
  });
}
document.addEventListener("DOMContentLoaded", markActiveNav);
