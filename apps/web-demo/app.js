const DATA_PATHS = {
  summary: "../../data/processed/warranty_dashboard.summary.json",
  states: "../../data/processed/warranty_report.states.json",
  items: "../../data/processed/warranty_items.normalized.json",
  products: "../../data/processed/products.catalog.json",
  customers: "../../data/processed/customers.catalog.json",
};

const CORE_STATES = [
  "A1",
  "A2",
  "A3",
  "B1",
  "B2",
  "B3",
  "B4",
  "C1",
  "C2",
  "C3",
  "C4",
  "C5",
  "C6",
  "C7",
  "C8",
];

const state = {
  items: [],
  filtered: [],
  summary: null,
  states: [],
  products: [],
  customers: [],
};

const els = {
  metrics: document.getElementById("metrics"),
  lastUpdate: document.getElementById("lastUpdate"),
  searchInput: document.getElementById("searchInput"),
  stateFilter: document.getElementById("stateFilter"),
  actionFilter: document.getElementById("actionFilter"),
  kanban: document.getElementById("kanban"),
  tableBody: document.getElementById("tableBody"),
  tableSummary: document.getElementById("tableSummary"),
  detailContent: document.getElementById("detailContent"),
};

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value ?? 0);
}

function clean(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return value;
}

function metricCard(label, value, delayMs = 0) {
  const node = document.createElement("article");
  node.className = "metric-card";
  node.style.animationDelay = `${delayMs}ms`;
  node.innerHTML = `<p class="label">${label}</p><p class="value">${value}</p>`;
  return node;
}

function renderMetrics() {
  const summary = state.summary;
  const cards = [
    ["Total warranty items", formatNumber(summary.total_items)],
    ["Open items", formatNumber(summary.open_items)],
    ["Closed items", formatNumber(summary.closed_items)],
    ["Product masters", formatNumber(state.products.length)],
    ["Customer masters", formatNumber(state.customers.length)],
    ["Master source", "KiotViet"],
  ];

  els.metrics.innerHTML = "";
  cards.forEach(([label, value], idx) => {
    els.metrics.appendChild(metricCard(label, value, idx * 45));
  });
}

function renderFilters() {
  const stateOptions = ["<option value=''>All states</option>"];
  state.states
    .filter((entry) => CORE_STATES.includes(entry.code))
    .forEach((entry) => {
      stateOptions.push(`<option value="${entry.code}">${entry.code} - ${entry.title}</option>`);
    });
  els.stateFilter.innerHTML = stateOptions.join("");

  const actionSet = new Set();
  state.items.forEach((item) => {
    if (item.requested_action) {
      actionSet.add(item.requested_action);
    }
  });
  const actions = [...actionSet].sort();
  const actionOptions = ["<option value=''>All actions</option>"];
  actions.forEach((name) => {
    actionOptions.push(`<option value="${name}">${name}</option>`);
  });
  els.actionFilter.innerHTML = actionOptions.join("");
}

function applyFilters() {
  const keyword = els.searchInput.value.trim().toLowerCase();
  const selectedState = els.stateFilter.value;
  const selectedAction = els.actionFilter.value;

  state.filtered = state.items.filter((item) => {
    if (selectedState && item.workflow_state !== selectedState) {
      return false;
    }

    if (selectedAction && item.requested_action !== selectedAction) {
      return false;
    }

    if (!keyword) {
      return true;
    }

    const searchText = [
      item.ticket_item_id,
      item.serial_number,
      item.customer_name,
      item.product_name,
      item.ticket_no,
      item.item_no,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return searchText.includes(keyword);
  });

  renderTable();
  renderKanban();
}

function renderKanban() {
  const buckets = new Map();
  CORE_STATES.forEach((code) => buckets.set(code, []));

  state.filtered.forEach((item) => {
    if (buckets.has(item.workflow_state)) {
      buckets.get(item.workflow_state).push(item);
    }
  });

  const stateTitle = new Map(state.states.map((x) => [x.code, x.title || ""]));

  const columns = [];
  CORE_STATES.forEach((code) => {
    const items = buckets.get(code);
    if (!items.length) {
      return;
    }

    const miniItems = items
      .slice(0, 4)
      .map(
        (row) => `
        <article class="mini-item">
          <p><b>${clean(row.ticket_item_id)}</b> - ${clean(row.product_name)}</p>
          <p>${clean(row.customer_name)}</p>
        </article>
      `
      )
      .join("");

    columns.push(`
      <article class="kanban-col">
        <div class="head">
          <strong>${code}</strong>
          <span class="state-badge">${items.length}</span>
        </div>
        <p class="subtitle">${clean(stateTitle.get(code))}</p>
        ${miniItems}
      </article>
    `);
  });

  els.kanban.innerHTML = columns.join("") || "<p class='muted'>No items in selected filters.</p>";
}

function statusPill(item) {
  if (item.returned_date) {
    return '<span class="status-pill done">Closed</span>';
  }
  return '<span class="status-pill open">Open</span>';
}

function renderTable() {
  const previewRows = state.filtered.slice(0, 150);
  els.tableSummary.textContent = `Showing ${formatNumber(previewRows.length)} / ${formatNumber(
    state.filtered.length
  )} rows`;

  if (!previewRows.length) {
    els.tableBody.innerHTML =
      '<tr><td colspan="8" class="muted">No rows found for current filters.</td></tr>';
    return;
  }

  els.tableBody.innerHTML = previewRows
    .map(
      (row, idx) => `
      <tr data-index="${idx}">
        <td>${clean(row.ticket_item_id)}<br />${statusPill(row)}</td>
        <td>${clean(row.product_name)}</td>
        <td>${clean(row.customer_name)}</td>
        <td>${clean(row.requested_action)}</td>
        <td>${clean(row.workflow_state)}</td>
        <td>${clean(row.current_location)}</td>
        <td>${clean(row.received_date)}</td>
        <td>${clean(row.returned_date)}</td>
      </tr>
    `
    )
    .join("");

  const rows = els.tableBody.querySelectorAll("tr[data-index]");
  rows.forEach((row) => {
    row.addEventListener("click", () => {
      const index = Number(row.getAttribute("data-index"));
      renderDetail(previewRows[index]);
    });
  });
}

function detailBlock(label, value) {
  return `
    <div class="detail-box">
      <h3>${label}</h3>
      <p>${clean(value)}</p>
    </div>
  `;
}

function renderDetail(item) {
  if (!item) {
    els.detailContent.textContent = "No item selected.";
    return;
  }

  els.detailContent.innerHTML = `
    <div class="detail-grid">
      ${detailBlock("Ticket", item.ticket_item_id)}
      ${detailBlock("Product", item.product_name)}
      ${detailBlock("Product key", item.product_key)}
      ${detailBlock("Customer", item.customer_name)}
      ${detailBlock("Customer key", item.customer_key)}
      ${detailBlock("Serial", item.serial_number)}
      ${detailBlock("State", item.workflow_state)}
      ${detailBlock("Action", item.requested_action)}
      ${detailBlock("Location", item.current_location)}
      ${detailBlock("Received", item.received_date)}
      ${detailBlock("Expected return", item.expected_return_date)}
      ${detailBlock("Returned", item.returned_date)}
      ${detailBlock("Customer request", item.customer_request)}
      ${detailBlock("Processing notes", item.processing_notes)}
      ${detailBlock("Return assessment", item.return_assessment)}
      ${detailBlock("Master source", item.master_data_source)}
    </div>
  `;
}

async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Unable to fetch ${path}`);
  }
  return response.json();
}

async function boot() {
  const [summary, states, items, products, customers] = await Promise.all([
    loadJson(DATA_PATHS.summary),
    loadJson(DATA_PATHS.states),
    loadJson(DATA_PATHS.items),
    loadJson(DATA_PATHS.products),
    loadJson(DATA_PATHS.customers),
  ]);

  state.summary = summary;
  state.states = states.states || [];
  state.items = items;
  state.products = products;
  state.customers = customers;
  state.filtered = items;

  renderMetrics();
  renderFilters();
  renderKanban();
  renderTable();
  renderDetail(items[0]);

  els.lastUpdate.textContent = `Loaded ${formatNumber(items.length)} items`;

  els.searchInput.addEventListener("input", applyFilters);
  els.stateFilter.addEventListener("change", applyFilters);
  els.actionFilter.addEventListener("change", applyFilters);
}

boot().catch((err) => {
  els.lastUpdate.textContent = "Error while loading data";
  els.detailContent.textContent = err.message;
});
