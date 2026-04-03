/* UI enhancement layer: top-nav SAP-like shell, collapsible cards, dashboard widgets, PDF print helpers. */
(function () {
  const $$ = (s, p = document) => Array.from(p.querySelectorAll(s));
  const $ = (s, p = document) => p.querySelector(s);

  function getHeaders() {
    const fallback = {};
    try {
      const fromSession = JSON.parse(sessionStorage.getItem("erpAuthHeaders") || "{}");
      if (fromSession && fromSession["x-user-id"]) return { ...fallback, ...fromSession };
    } catch {}
    const pre = $("#authHeaders");
    if (!pre) return fallback;
    try {
      const parsed = JSON.parse(pre.textContent || "{}");
      return { ...fallback, ...parsed };
    } catch {
      return fallback;
    }
  }

  async function api(path) {
    const res = await fetch(path, { headers: { ...getHeaders() } });
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) throw new Error(data.error || `Request failed: ${path}`);
    return data;
  }

  function makeCardsCollapsible() {
    $$(".card").forEach((card) => {
      if (card.dataset.collapsible === "true") return;
      const title = $("h3", card);
      if (!title) return;

      const body = document.createElement("div");
      body.className = "card-body";
      const rest = Array.from(card.children).filter((el) => el !== title);
      rest.forEach((el) => body.appendChild(el));
      card.appendChild(body);

      title.classList.add("card-title-toggle");
      title.insertAdjacentHTML(
        "beforeend",
        '<button type="button" class="collapse-btn" aria-label="Collapse section">▾</button>'
      );
      $(".collapse-btn", title).addEventListener("click", () => {
        card.classList.toggle("collapsed");
      });

      card.dataset.collapsible = "true";
    });
  }

  function setupSemanticDropdowns() {
    // Search dropdown enhancement removed; keep native selects only.
  }

  function alignFieldLabels() {
    $$("label").forEach((label) => {
      const existingSpan = $(".field-label-text", label);
      const textNodes = Array.from(label.childNodes).filter((node) => node.nodeType === Node.TEXT_NODE);
      const meaningfulTextNode = textNodes.find((node) => node.textContent && node.textContent.trim());

      if (!existingSpan && !meaningfulTextNode) {
        label.dataset.labelAligned = "true";
        return;
      }

      if (!existingSpan && meaningfulTextNode) {
        const span = document.createElement("span");
        span.className = "field-label-text";
        span.textContent = meaningfulTextNode.textContent.trim();
        label.insertBefore(span, label.firstChild);
      }

      textNodes.forEach((node) => {
        node.textContent = "";
      });

      label.dataset.labelAligned = "true";
    });
  }

  function decorateShell() {
    const sessionUser = $("#sessionUser");
    const connectionPill = $(".connection-pill");
    if (connectionPill) {
      const isLoggedIn = sessionUser && sessionUser.textContent && sessionUser.textContent.trim() !== "Not logged in";
      connectionPill.textContent = isLoggedIn ? "Role session active" : "Operational workspace";
      connectionPill.classList.toggle("online", true);
    }
  }

  function decorateModules() {
    const moduleMeta = {
      dashboard: {
        eyebrow: "Overview",
        copy: "Live operational metrics and reports across the entire printing workflow.",
      },
      procurement: {
        eyebrow: "Stage one",
        copy: "Control vendor onboarding, requisitions, purchase orders, GRN processing, and reorder monitoring.",
      },
      inventory: {
        eyebrow: "Stage two",
        copy: "Track item masters, warehouse balances, internal issues, transfers, and wastage with one visual system.",
      },
      sales: {
        eyebrow: "Stage three",
        copy: "Keep customer setup, quotations, and order conversion aligned with the rest of the ERP.",
      },
      production: {
        eyebrow: "Stage four",
        copy: "Plan jobs, allocate machines, and push shop-floor status updates through a clearer operator workspace.",
      },
      logistics: {
        eyebrow: "Stage five",
        copy: "Coordinate challans, dispatch status, transporter details, and delivery visibility.",
      },
      accounts: {
        eyebrow: "Stage six",
        copy: "Handle HSN setup, invoicing, payables, receivables, and ledger summaries in the same Athena-inspired surface.",
      },
      hrmPayroll: {
        eyebrow: "Stage seven",
        copy: "Manage employee records, attendance, leave, and payroll inside the shared control center.",
      },
    };

    $$(".module").forEach((module) => {
      const title = $("h2", module);
      const meta = moduleMeta[module.id];
      if (!title || !meta || title.dataset.decorated === "true") return;
      const label = (title.textContent || "").trim();
      title.innerHTML = `<p class="eyebrow">${meta.eyebrow}</p><span>${label}</span><p class="hero-copy">${meta.copy}</p>`;
      title.dataset.decorated = "true";
    });
  }

  function bindLoginPasswordToggle() {
    const input = $("#loginPassword");
    const button = $("#toggleLoginPassword");
    if (!input || !button || button.dataset.bound === "true") return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => {
      const isHidden = input.type === "password";
      input.type = isHidden ? "text" : "password";
      button.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
      button.setAttribute("aria-pressed", isHidden ? "true" : "false");
    });
  }

  function barRows(title, map) {
    const rows = Object.entries(map || {});
    if (!rows.length) return "";
    const max = Math.max(...rows.map(([, v]) => Number(v) || 0), 1);
    const html = rows
      .map(([k, v]) => {
        const w = Math.max(8, Math.round(((Number(v) || 0) / max) * 100));
        return `<div class="pro-row"><span>${k}</span><div class="pro-track"><i style="width:${w}%"></i></div><b>${v}</b></div>`;
      })
      .join("");
    return `<div class="card pro-panel"><h3>${title}</h3><div class="pro-bars">${html}</div></div>`;
  }

  function asNum(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }

  function fmtMoney(v) {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
      asNum(v)
    );
  }

  function kpiCard(label, value, tone = "") {
    return `
      <div class="dashboard-kpi ${tone ? `dashboard-kpi-${tone}` : ""}">
        <span>${label}</span>
        <strong>${value}</strong>
      </div>
    `;
  }

  function statListCard(title, rows) {
    return `
      <div class="card report-card compact-report-card">
        <h3>${title}</h3>
        <div class="compact-stat-list">
          ${rows.map((r) => `<div><span>${r.label}</span><b>${r.value}</b></div>`).join("")}
        </div>
      </div>
    `;
  }

  function reportRows(title, rows) {
    if (!rows || !rows.length) {
      return `<div class="card report-card"><h3>${title}</h3><div class="table-empty">No records found.</div></div>`;
    }
    const body = rows
      .map((r) => `<tr><td>${r.label}</td><td>${r.value}</td></tr>`)
      .join("");
    return `
      <div class="card report-card">
        <h3>${title}</h3>
        <table class="data-table report-table">
          <tbody>${body}</tbody>
        </table>
      </div>
    `;
  }

  async function renderProfessionalDashboard() {
    const cardsHost = $("#dashboardCards");
    const host = $("#dashboardPro");
    const reportsHost = $("#dashboardReports");
    if (!host) return;
    try {
      const safeApi = async (path, fallback) => {
        try {
          return await api(path);
        } catch {
          return fallback;
        }
      };

      const [summary, procurement, reqs, grns, quotes, stock, items, vendors, customers, machines, taxes, salesOrders, jobs, challans, pinv, sinv, ap, ar] =
        await Promise.all([
          safeApi("/api/reports/dashboard", {
            purchaseOrders: 0,
            salesOrders: 0,
            openReorderAlerts: 0,
            jobCardsOpen: 0,
            totalPayable: 0,
            totalReceivable: 0,
          }),
          safeApi("/api/reports/procurement", {
            ordersByApprovalStatus: {},
            grnQualityStatus: {},
            invoiceMatchStatus: {},
          }),
          safeApi("/api/procurement/requisitions", []),
          safeApi("/api/procurement/grns", []),
          safeApi("/api/sales/quotations", []),
          safeApi("/api/inventory/stock", []),
          safeApi("/api/masters/items", []),
          safeApi("/api/masters/vendors", []),
          safeApi("/api/masters/customers", []),
          safeApi("/api/masters/machines", []),
          safeApi("/api/masters/taxes", []),
          safeApi("/api/sales/sales-orders", []),
          safeApi("/api/production/job-cards", []),
          safeApi("/api/logistics/challans", []),
          safeApi("/api/accounts/purchase-invoices", []),
          safeApi("/api/accounts/sales-invoices", []),
          safeApi("/api/accounts/payables", []),
          safeApi("/api/accounts/receivables", []),
        ]);

      const reqOpen = reqs.filter((x) => x.status === "OPEN").length;
      const grnPass = grns.filter((x) => x.qualityStatus === "PASS").length;
      const grnFail = grns.filter((x) => x.qualityStatus === "FAIL").length;
      const quoteOpen = quotes.filter((x) => x.status === "OPEN").length;
      const stockByItem = stock.reduce((acc, s) => {
        const key = String(s.itemId || "");
        acc[key] = (acc[key] || 0) + asNum(s.qty);
        return acc;
      }, {});
      const lowStock = items
        .map((i) => ({
          code: i.sku,
          name: i.name,
          qty: stockByItem[String(i.id)] || 0,
          reorder: asNum(i.reorderLevel),
        }))
        .filter((x) => x.qty <= x.reorder)
        .sort((a, b) => a.qty - b.qty)
        .slice(0, 6);

      const soOpen = salesOrders.filter((x) => String(x.status || "").toUpperCase() === "OPEN").length;
      const soValue = salesOrders.reduce((s, x) => s + asNum(x.totalAmount), 0);
      const jobsOpen = jobs.filter((x) => !["COMPLETED", "CLOSED"].includes(String(x.status || "").toUpperCase())).length;
      const jobsCompleted = jobs.filter((x) => String(x.status || "").toUpperCase() === "COMPLETED").length;
      const inDispatch = challans.filter((x) => String(x.dispatchStatus || "").toUpperCase() !== "PENDING").length;
      const pendingDispatch = challans.filter((x) => String(x.dispatchStatus || "").toUpperCase() === "PENDING").length;
      const payableDue = ap.reduce((s, x) => s + Math.max(0, asNum(x.amountDue) - asNum(x.amountPaid)), 0);
      const receivableDue = ar.reduce((s, x) => s + Math.max(0, asNum(x.amountDue) - asNum(x.amountReceived)), 0);
      const pinvValue = pinv.reduce((s, x) => s + asNum(x.totalAmount), 0);
      const sinvValue = sinv.reduce((s, x) => s + asNum(x.totalAmount), 0);
      const matchPending = pinv.filter((x) => String(x.matchStatus || "").toUpperCase() !== "MATCHED").length;
      const totalStockQty = stock.reduce((s, x) => s + asNum(x.qty), 0);
      const grnPassRate = grns.length ? `${Math.round((grnPass / grns.length) * 100)}%` : "0%";

      if (cardsHost) {
        cardsHost.innerHTML = `
          <div class="dashboard-kpi-grid">
            ${kpiCard("Purchase Orders", summary.purchaseOrders || 0)}
            ${kpiCard("Sales Orders", summary.salesOrders || 0)}
            ${kpiCard("Open Requisitions", reqOpen, reqOpen ? "alert" : "")}
            ${kpiCard("Open Jobs", jobsOpen, jobsOpen ? "active" : "")}
            ${kpiCard("Receivables", fmtMoney(receivableDue), receivableDue ? "alert" : "")}
            ${kpiCard("Payables", fmtMoney(payableDue), payableDue ? "muted" : "")}
            ${kpiCard("Low Stock", lowStock.length, lowStock.length ? "alert" : "good")}
            ${kpiCard("GRN Pass Rate", grnPassRate, grnPass ? "good" : "")}
          </div>
        `;
      }

      host.innerHTML = `
        <div class="card pro-hero dashboard-hero-compact">
          <div class="dashboard-hero-head">
            <div>
              <h3>Operations Snapshot</h3>
              <p class="hero-copy">A tighter live view of procurement, inventory, production, dispatch, and cash movement.</p>
            </div>
            <div class="dashboard-mini-pills">
              <span>${items.length} items</span>
              <span>${vendors.length} vendors</span>
              <span>${customers.length} customers</span>
              <span>${machines.length} machines</span>
            </div>
          </div>
          <div class="compact-stat-list compact-stat-list-wide">
            <div><span>Open Quotations</span><b>${quoteOpen}</b></div>
            <div><span>Open Sales Orders</span><b>${soOpen}</b></div>
            <div><span>Completed Jobs</span><b>${jobsCompleted}</b></div>
            <div><span>In Dispatch</span><b>${inDispatch}</b></div>
            <div><span>Purchase Invoice Value</span><b>${fmtMoney(pinvValue)}</b></div>
            <div><span>Sales Invoice Value</span><b>${fmtMoney(sinvValue)}</b></div>
          </div>
        </div>
        <div class="dashboard-split-grid">
          <div class="card report-card compact-report-card">
            <h3>Priority Watchlist</h3>
            <div class="compact-stat-list">
              <div><span>Pending PO Approval</span><b>${asNum(procurement.ordersByApprovalStatus?.PENDING || 0)}</b></div>
              <div><span>Pending Dispatch</span><b>${pendingDispatch}</b></div>
              <div><span>GRN Failures</span><b>${grnFail}</b></div>
              <div><span>3-Way Match Pending</span><b>${matchPending}</b></div>
              <div><span>Reorder Alerts</span><b>${summary.openReorderAlerts || 0}</b></div>
              <div><span>Total Stock Qty</span><b>${totalStockQty}</b></div>
            </div>
          </div>
          <div class="dashboard-bar-grid">
            ${barRows("PO Approval", procurement.ordersByApprovalStatus)}
            ${barRows("GRN Quality", procurement.grnQualityStatus)}
            ${barRows("Invoice Match", procurement.invoiceMatchStatus)}
          </div>
        </div>
      `;

      if (reportsHost) {
        reportsHost.innerHTML = `
          ${statListCard("Inventory", [
            { label: "Stock Qty", value: totalStockQty },
            { label: "Low Stock", value: lowStock.length },
            ...lowStock.slice(0, 3).map((x) => ({ label: x.code, value: `${x.qty} / RL ${x.reorder}` })),
          ])}
          ${statListCard("Sales & Production", [
            { label: "Quotes Open", value: quoteOpen },
            { label: "SO Open", value: soOpen },
            { label: "SO Value", value: fmtMoney(soValue) },
            { label: "Jobs Open", value: jobsOpen },
            { label: "Jobs Completed", value: jobsCompleted },
          ])}
          ${statListCard("Finance", [
            { label: "Receivable", value: fmtMoney(receivableDue) },
            { label: "Payable", value: fmtMoney(payableDue) },
            { label: "Purchase Invoices", value: pinv.length },
            { label: "Sales Invoices", value: sinv.length },
            { label: "GRN Pass Rate", value: grnPassRate },
          ])}
          ${statListCard("Master Data", [
            { label: "Items", value: items.length },
            { label: "Vendors", value: vendors.length },
            { label: "Customers", value: customers.length },
            { label: "Machines", value: machines.length },
            { label: "HSN Codes", value: taxes.length },
          ])}
        `;
      }
      makeCardsCollapsible();
    } catch {
      host.innerHTML = '<div class="card"><h3>Dashboard</h3><div class="table-empty">Unable to load dashboard metrics.</div></div>';
      if (reportsHost) {
        reportsHost.innerHTML =
          '<div class="card"><h3>Reports</h3><div class="table-empty">Unable to load reports at the moment.</div></div>';
      }
    }
  }

  window.renderProfessionalDashboard = renderProfessionalDashboard;

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function buildPrintDocument(title, subtitle, rows) {
    const r = rows
      .map(
        (x) =>
          `<tr><td>${escapeHtml(x.label)}</td><td>${escapeHtml(x.value ?? "-")}</td></tr>`
      )
      .join("");
    return `
      <!doctype html>
      <html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
      <style>
        body{font-family:Segoe UI,Tahoma,sans-serif;margin:28px;color:#0b1220;position:relative}
        .wm{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;font-size:84px;font-weight:800;color:rgba(14,165,233,.09);transform:rotate(-24deg);pointer-events:none;user-select:none}
        h1{margin:0 0 4px;font-size:24px} h2{margin:0 0 16px;font-size:14px;color:#334155;font-weight:600}
        table{width:100%;border-collapse:collapse} td{border:1px solid #cbd5e1;padding:10px;font-size:13px}
        td:first-child{width:42%;background:#f8fafc;font-weight:600}
      </style></head>
      <body>
        <div class="wm">PRINTCO ERP</div>
        <h1>${escapeHtml(title)}</h1><h2>${escapeHtml(subtitle)}</h2>
        <table>${r}</table>
      </body></html>
    `;
  }

  function buildTablePrintDocument(title, subtitle, sections) {
    const cards = sections
      .map((section, idx) => {
        const head = section.headers
          .map((cell) => `<th>${escapeHtml(cell)}</th>`)
          .join("");
        const body = section.rows
          .map(
            (row) =>
              `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`
          )
          .join("");
        const sectionTitle = sections.length > 1 ? `<h3>${escapeHtml(section.title || `Table ${idx + 1}`)}</h3>` : "";
        return `
          <section class="table-section">
            ${sectionTitle}
            <table>
              <thead><tr>${head}</tr></thead>
              <tbody>${body}</tbody>
            </table>
          </section>
        `;
      })
      .join("");

    return `
      <!doctype html>
      <html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
      <style>
        body{font-family:Segoe UI,Tahoma,sans-serif;margin:28px;color:#0b1220;position:relative}
        .wm{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;font-size:84px;font-weight:800;color:rgba(14,165,233,.09);transform:rotate(-24deg);pointer-events:none;user-select:none}
        h1{margin:0 0 4px;font-size:24px}
        h2{margin:0 0 18px;font-size:14px;color:#334155;font-weight:600}
        h3{margin:0 0 10px;font-size:15px;color:#0f172a}
        .table-section + .table-section{margin-top:24px}
        table{width:100%;border-collapse:collapse;margin:0}
        th,td{border:1px solid #cbd5e1;padding:10px;font-size:12.5px;text-align:left;vertical-align:top}
        th{background:#f8fafc;font-weight:700}
        tbody tr:nth-child(even) td{background:#fcfdfd}
      </style></head>
      <body>
        <div class="wm">PRINTCO ERP</div>
        <h1>${escapeHtml(title)}</h1><h2>${escapeHtml(subtitle)}</h2>
        ${cards}
      </body></html>
    `;
  }

  function openPrint(html) {
    const win = window.open("", "_blank");
    if (!win) return;
    win.document.open();
    win.document.write(html);
    win.document.close();
    win.focus();
    setTimeout(() => win.print(), 350);
  }

  function slugifyFilePart(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "export";
  }

  function downloadTextFile(filename, content, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function csvCell(value) {
    const safe = String(value ?? "").replace(/"/g, '""');
    return /[",\r\n]/.test(safe) ? `"${safe}"` : safe;
  }

  function csvFromPairs(rows) {
    if (!rows?.length) return "";
    return [
      "Field,Value",
      ...rows.map((row) => `${csvCell(row.label || "")},${csvCell(row.value || "")}`),
    ].join("\r\n");
  }

  function shouldIgnoreExportColumn(header) {
    const text = (header?.textContent || "").trim().toLowerCase();
    return (
      header?.dataset?.exportIgnore === "true" ||
      header?.classList?.contains("row-actions-head") ||
      text === "action" ||
      text === "actions"
    );
  }

  function tableColumns(table) {
    const headers = $$("thead th", table);
    if (!headers.length) return [];
    return headers
      .map((header, idx) => ({
        idx,
        label: (header.textContent || "").trim(),
        ignore: shouldIgnoreExportColumn(header),
      }))
      .filter((column) => !column.ignore)
      .map((column, columnIndex) => ({
        idx: column.idx,
        label: column.label || `Column ${columnIndex + 1}`,
      }));
  }

  function rowCells(row, columns = null) {
    const table = row?.closest("table");
    if (!table) return [];
    const sourceColumns = columns || tableColumns(table);
    const cells = $$("td", row);
    if (!sourceColumns.length) {
      return cells
        .filter(
          (cell) =>
            cell.dataset.exportIgnore !== "true" &&
            !cell.classList.contains("row-actions-cell")
        )
        .map((cell) => (cell.textContent || "").trim());
    }
    return sourceColumns.map(({ idx }) => (cells[idx]?.textContent || "").trim());
  }

  function rowFieldPairs(row) {
    const table = row?.closest("table");
    if (!table) return [];
    const columns = tableColumns(table);
    const cells = rowCells(row, columns);
    const safeColumns = columns.length
      ? columns
      : cells.map((_, idx) => ({ idx, label: `Column ${idx + 1}` }));
    return safeColumns.map((column, idx) => ({
      label: column.label,
      value: cells[idx] || "-",
    }));
  }

  function csvFromTable(table) {
    const data = tableDataFromTable(table);
    if (!data) return "";
    return [
      data.headers.map(csvCell).join(","),
      ...data.rows.map((cells) => cells.map(csvCell).join(",")),
    ].join("\r\n");
  }

  function csvFromCard(card) {
    const tables = $$("table.data-table", card);
    const sections = tables
      .map((table) => csvFromTable(table))
      .filter(Boolean);
    if (!sections.length) return "";
    if (sections.length === 1) return sections[0];
    return sections
      .map((section, idx) => [`${csvCell(`Table ${idx + 1}`)}`, section].join("\r\n"))
      .join("\r\n\r\n");
  }

  function csvFromTableRow(row) {
    const table = row?.closest("table");
    if (!table) return "";
    const columns = tableColumns(table);
    const cells = rowCells(row, columns);
    const safeHeaders = columns.length
      ? columns.map((column) => column.label)
      : cells.map((_, idx) => `Column ${idx + 1}`);
    if (!safeHeaders.length && !cells.length) return "";
    return [
      safeHeaders.map(csvCell).join(","),
      cells.map(csvCell).join(","),
    ].join("\r\n");
  }

  function tableDataFromTable(table) {
    if (!table) return null;
    const bodyRows = $$("tbody tr", table);
    const columns = tableColumns(table);
    const rows = bodyRows.map((tr) => rowCells(tr, columns));
    const columnCount = Math.max(
      columns.length,
      ...rows.map((cells) => cells.length),
      0
    );
    if (!columnCount) return null;
    const safeHeaders = columns.length
      ? columns.map((column) => column.label)
      : Array.from({ length: columnCount }, (_, idx) => `Column ${idx + 1}`);
    return {
      headers: safeHeaders,
      rows: rows.map((cells) =>
        Array.from({ length: safeHeaders.length }, (_, idx) => cells[idx] || "")
      ),
    };
  }

  function tableExportsFromCard(card) {
    return $$("table.data-table", card)
      .map((table, idx) => {
        const data = tableDataFromTable(table);
        if (!data) return null;
        return {
          title: `Table ${idx + 1}`,
          headers: data.headers,
          rows: data.rows,
        };
      })
      .filter(Boolean);
  }

  function notify(message) {
    const t = document.getElementById("toast");
    if (!t) return;
    t.textContent = message;
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 1800);
  }

  function clearRowExportArmed() {
    $$(".card[data-row-export-armed='true']").forEach((card) => {
      card.dataset.rowExportArmed = "false";
      card.dataset.rowExportFormat = "";
      card.classList.remove("row-export-armed");
      $$(".row-export-btn", card).forEach((btn) => {
        btn.classList.remove("is-active");
        btn.setAttribute("aria-pressed", "false");
      });
    });
  }

  function addRowExportButtons() {
    $$(".card").forEach((card) => {
      const isOutputTableCard = card.tagName !== "FORM" && !!$("table.data-table", card);
      if (!isOutputTableCard) {
        $(".export-action-row", card)?.remove();
        card.dataset.rowExportReady = "false";
        card.dataset.rowExportArmed = "false";
        card.dataset.rowExportFormat = "";
        card.classList.remove("row-export-armed");
        return;
      }
      if (card.dataset.rowExportReady === "true") return;
      const body = $(".card-body", card) || card;
      body.insertAdjacentHTML(
        "beforeend",
        `<div class="export-action-row">
          <button type="button" class="row-export-btn csv-export-btn" data-export-format="csv" aria-label="Export table to CSV" aria-pressed="false">Export as CSV</button>
          <button type="button" class="row-export-btn pdf-export-btn" data-export-format="pdf" aria-label="Export table to PDF" aria-pressed="false">Export as PDF</button>
        </div>`
      );
      card.dataset.rowExportReady = "true";
      card.dataset.rowExportArmed = "false";
      card.dataset.rowExportFormat = "";
    });
  }

  function extractRowForPdf(row) {
    return rowFieldPairs(row);
  }

  function rowAsMap(row) {
    const out = {};
    rowFieldPairs(row).forEach(({ label, value }) => {
      out[label] = value || "";
    });
    return out;
  }

  function itemMap(items) {
    const map = new Map();
    (items || []).forEach((it) => map.set(String(it.id), it));
    return map;
  }

  async function buildDocExportFromRow(row) {
    const m = rowAsMap(row);
    const poNo = m["PO No"] || "";
    const soNo = m["SO No"] || "";
    const invoiceNo = m["Invoice No"] || "";
    if (!poNo && !soNo && !invoiceNo) return null;

    const [items, purchaseOrders, salesOrders, pinv, sinv] = await Promise.all([
      api("/api/masters/items").catch(() => []),
      api("/api/procurement/purchase-orders").catch(() => []),
      api("/api/sales/sales-orders").catch(() => []),
      api("/api/accounts/purchase-invoices").catch(() => []),
      api("/api/accounts/sales-invoices").catch(() => []),
    ]);
    const itemById = itemMap(items);

    if (poNo) {
      const po = (purchaseOrders || []).find((x) => String(x.poNo) === String(poNo));
      if (!po) return null;
      const rows = [
        { label: "PO No", value: po.poNo },
        { label: "Date", value: po.date || "-" },
        { label: "Vendor ID", value: po.vendorId || "-" },
        { label: "Approval", value: po.approvalStatus || "-" },
        { label: "Status", value: po.status || "-" },
      ];
      (po.lines || []).forEach((l, i) => {
        const it = itemById.get(String(l.itemId)) || {};
        const qty = Number(l.qty || 0);
        const rate = Number(l.unitRate || 0);
        const gst = Number(l.taxRate || 0);
        const base = qty * rate;
        const tax = (base * gst) / 100;
        rows.push({ label: `Item ${i + 1}`, value: `${it.sku || "-"} | ${it.name || `#${l.itemId}`}` });
        rows.push({ label: `Item ${i + 1} Qty`, value: String(l.qty || 0) });
        rows.push({ label: `Item ${i + 1} Rate`, value: String(l.unitRate || 0) });
        rows.push({ label: `Item ${i + 1} GST %`, value: String(l.taxRate || 0) });
        rows.push({ label: `Item ${i + 1} Line Total`, value: (base + tax).toFixed(2) });
      });
      rows.push({ label: "Document Base", value: po.baseAmount || "-" });
      rows.push({ label: "Document GST", value: po.taxAmount || "-" });
      rows.push({ label: "Document Grand Total", value: po.totalAmount || "-" });
      return { title: "Purchase Order", subtitle: po.poNo, rows };
    }

    if (soNo) {
      const so = (salesOrders || []).find((x) => String(x.soNo) === String(soNo));
      if (!so) return null;
      const rows = [
        { label: "SO No", value: so.soNo },
        { label: "Date", value: so.date || "-" },
        { label: "Customer ID", value: so.customerId || "-" },
        { label: "Credit", value: so.creditStatus || "-" },
        { label: "Status", value: so.status || "-" },
      ];
      (so.lines || []).forEach((l, i) => {
        const it = itemById.get(String(l.itemId)) || {};
        const qty = Number(l.qty || 0);
        const rate = Number(l.unitPrice || 0);
        const gst = Number(l.taxRate || 0);
        const base = qty * rate;
        const tax = (base * gst) / 100;
        rows.push({ label: `Item ${i + 1}`, value: `${it.sku || "-"} | ${it.name || `#${l.itemId}`}` });
        rows.push({ label: `Item ${i + 1} Qty`, value: String(l.qty || 0) });
        rows.push({ label: `Item ${i + 1} Rate`, value: String(l.unitPrice || 0) });
        rows.push({ label: `Item ${i + 1} GST %`, value: String(l.taxRate || 0) });
        rows.push({ label: `Item ${i + 1} Line Total`, value: (base + tax).toFixed(2) });
      });
      rows.push({ label: "Document Base", value: so.baseAmount || "-" });
      rows.push({ label: "Document GST", value: so.taxAmount || "-" });
      rows.push({ label: "Document Grand Total", value: so.totalAmount || "-" });
      return { title: "Sales Order", subtitle: so.soNo, rows };
    }

    if (invoiceNo) {
      const p = (pinv || []).find((x) => String(x.invoiceNo) === String(invoiceNo));
      if (p) {
        const po = (purchaseOrders || []).find((x) => String(x.id) === String(p.poId));
        const rows = [
          { label: "Invoice No", value: p.invoiceNo },
          { label: "PO ID", value: p.poId || "-" },
          { label: "GRN ID", value: p.grnId || "-" },
          { label: "Vendor ID", value: p.vendorId || "-" },
          { label: "Status", value: p.status || "-" },
          { label: "3-Way Match", value: p.matchStatus || "-" },
        ];
        (po?.lines || []).forEach((l, i) => {
          const it = itemById.get(String(l.itemId)) || {};
          const qty = Number(l.qty || 0);
          const rate = Number(l.unitRate || 0);
          const gst = Number(l.taxRate || 0);
          const base = qty * rate;
          const tax = (base * gst) / 100;
          rows.push({ label: `Item ${i + 1}`, value: `${it.sku || "-"} | ${it.name || `#${l.itemId}`}` });
          rows.push({ label: `Item ${i + 1} Qty`, value: String(l.qty || 0) });
          rows.push({ label: `Item ${i + 1} Rate`, value: String(l.unitRate || 0) });
          rows.push({ label: `Item ${i + 1} GST %`, value: String(l.taxRate || 0) });
          rows.push({ label: `Item ${i + 1} Line Total`, value: (base + tax).toFixed(2) });
        });
        rows.push({ label: "Document Base", value: p.baseAmount || "-" });
        rows.push({ label: "Document GST", value: p.taxAmount || "-" });
        rows.push({ label: "Document Grand Total", value: p.totalAmount || "-" });
        return { title: "Purchase Invoice", subtitle: p.invoiceNo, rows };
      }
      const s = (sinv || []).find((x) => String(x.invoiceNo) === String(invoiceNo));
      if (s) {
        const so = (salesOrders || []).find((x) => String(x.id) === String(s.soId));
        const rows = [
          { label: "Invoice No", value: s.invoiceNo },
          { label: "SO ID", value: s.soId || "-" },
          { label: "Customer ID", value: s.customerId || "-" },
          { label: "Status", value: s.status || "-" },
        ];
        (so?.lines || []).forEach((l, i) => {
          const it = itemById.get(String(l.itemId)) || {};
          const qty = Number(l.qty || 0);
          const rate = Number(l.unitPrice || 0);
          const gst = Number(l.taxRate || 0);
          const base = qty * rate;
          const tax = (base * gst) / 100;
          rows.push({ label: `Item ${i + 1}`, value: `${it.sku || "-"} | ${it.name || `#${l.itemId}`}` });
          rows.push({ label: `Item ${i + 1} Qty`, value: String(l.qty || 0) });
          rows.push({ label: `Item ${i + 1} Rate`, value: String(l.unitPrice || 0) });
          rows.push({ label: `Item ${i + 1} GST %`, value: String(l.taxRate || 0) });
          rows.push({ label: `Item ${i + 1} Line Total`, value: (base + tax).toFixed(2) });
        });
        rows.push({ label: "Document Base", value: s.baseAmount || "-" });
        rows.push({ label: "Document GST", value: s.taxAmount || "-" });
        rows.push({ label: "Document Grand Total", value: s.totalAmount || "-" });
        return { title: "Sales Invoice", subtitle: s.invoiceNo, rows };
      }
    }
    return null;
  }

  function rowActionButton(label, action, icon) {
    return `
      <button
        type="button"
        class="ghost-button icon-action-button row-icon-action"
        data-row-action="${action}"
        aria-label="${escapeHtml(label)}"
        title="${escapeHtml(label)}"
      >
        ${icon}
      </button>
    `;
  }

  function rowPrimaryText(row) {
    return rowCells(row).find((value) => value && value !== "-") || "Selected record";
  }

  function rowSectionTitle(row) {
    return (
      $("h3", row.closest(".card"))?.textContent ||
      $("h2", row.closest(".module"))?.textContent ||
      "Record"
    )
      .replace("Export as PDF", "")
      .replace("Export as CSV", "")
      .trim();
  }

  function ensureRowActionButtons() {
    const viewIcon =
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.8"></circle></svg>';
    const csvIcon =
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zm0 0v5h5M8 14h8M8 10h3M8 18h8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"></path></svg>';
    const pdfIcon =
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm7 0v5h5M8.5 15h2a1.5 1.5 0 0 0 0-3h-2zm0 0v3m5-3h2m-2 1.5h1.5m-1.5 1.5h2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"></path></svg>';

    $$(".data-table").forEach((table) => {
      if (table.closest("#rowDetailOverlay")) return;
      if (table.classList.contains("no-row-actions-table")) return;
      const rows = $$("tbody tr", table);
      if (!rows.length) return;

      const headRow = $("thead tr", table);
      if (headRow && !$(".row-actions-head", headRow)) {
        headRow.insertAdjacentHTML(
          "beforeend",
          '<th class="row-actions-head" data-export-ignore="true">Actions</th>'
        );
      }

      rows.forEach((row) => {
        if ($(".row-actions-cell", row)) return;
        const labelBase = `${rowSectionTitle(row)} ${rowPrimaryText(row)}`.trim();
        row.insertAdjacentHTML(
          "beforeend",
          `
            <td class="row-actions-cell" data-export-ignore="true">
              <div class="action-row table-action-row row-table-action-row">
                ${rowActionButton(`${labelBase} view details`, "view", viewIcon)}
                ${rowActionButton(`${labelBase} export csv`, "csv", csvIcon)}
                ${rowActionButton(`${labelBase} export pdf`, "pdf", pdfIcon)}
              </div>
            </td>
          `
        );
      });
    });
  }

  function sectionizeRowDetails(rows) {
    const overview = [];
    const totals = [];
    const itemGroups = new Map();

    (rows || []).forEach((row) => {
      const label = String(row?.label || "").trim();
      const itemMatch = /^Item\s+(\d+)(?:\s+(.*))?$/i.exec(label);
      if (itemMatch) {
        const title = `Item ${itemMatch[1]}`;
        const fieldLabel = (itemMatch[2] || "Detail").trim() || "Detail";
        if (!itemGroups.has(title)) itemGroups.set(title, []);
        itemGroups.get(title).push({ label: fieldLabel, value: row?.value ?? "-" });
        return;
      }

      if (/^Document\s+/i.test(label)) {
        totals.push({
          label: label.replace(/^Document\s+/i, "").trim() || label,
          value: row?.value ?? "-",
        });
        return;
      }

      overview.push({ label, value: row?.value ?? "-" });
    });

    const sections = [];
    if (overview.length) {
      sections.push({
        title: "Record Snapshot",
        meta: `${overview.length} field${overview.length === 1 ? "" : "s"}`,
        rows: overview,
      });
    }

    itemGroups.forEach((groupRows, title) => {
      sections.push({
        title,
        meta: `${groupRows.length} field${groupRows.length === 1 ? "" : "s"}`,
        rows: groupRows,
      });
    });

    if (totals.length) {
      sections.push({
        title: "Document Totals",
        meta: `${totals.length} field${totals.length === 1 ? "" : "s"}`,
        rows: totals,
      });
    }

    if (!sections.length && rows?.length) {
      sections.push({
        title: "Record Snapshot",
        meta: `${rows.length} field${rows.length === 1 ? "" : "s"}`,
        rows,
      });
    }

    return sections;
  }

  function renderRowDetailSections(rows) {
    const sections = sectionizeRowDetails(rows);
    if (!sections.length) {
      return '<div class="table-empty">No details available for this row.</div>';
    }

    return sections
      .map(
        (section) => `
          <section class="row-detail-section">
            <div class="row-detail-section-head">
              <h3>${escapeHtml(section.title)}</h3>
              <span>${escapeHtml(section.meta)}</span>
            </div>
            <div class="detail-grid row-detail-grid">
              ${section.rows
                .map(
                  (row) => `
                    <p>
                      <strong>${escapeHtml(row.label)}</strong>
                      <span>${escapeHtml(row.value ?? "-")}</span>
                    </p>
                  `
                )
                .join("")}
            </div>
          </section>
        `
      )
      .join("");
  }

  function ensureRowDetailDrawer() {
    if ($("#rowDetailOverlay")) return;
    document.body.insertAdjacentHTML(
      "beforeend",
      `
        <div id="rowDetailOverlay" class="row-detail-overlay" data-row-detail-backdrop="true" hidden>
          <div class="row-detail-panel" role="dialog" aria-modal="true" aria-labelledby="rowDetailTitle">
            <p class="eyebrow">Record Detail</p>
            <div class="row-detail-head">
              <div class="row-detail-copy">
                <h2 id="rowDetailTitle">Record</h2>
                <span id="rowDetailSubtitle" class="row-detail-subtitle"></span>
              </div>
              <div class="action-row row-detail-actions">
                <button type="button" class="ghost-button" data-row-detail-close="true">Close</button>
              </div>
            </div>
            <div id="rowDetailBody" class="row-detail-body"></div>
          </div>
        </div>
      `
    );
  }

  function showRowDetailDrawer(title, subtitle, rows) {
    ensureRowDetailDrawer();
    const overlay = $("#rowDetailOverlay");
    const body = $("#rowDetailBody");
    const titleEl = $("#rowDetailTitle");
    const subtitleEl = $("#rowDetailSubtitle");
    if (!overlay || !body || !titleEl || !subtitleEl) return;
    titleEl.textContent = title || "Record";
    subtitleEl.textContent = subtitle || "";
    body.innerHTML = renderRowDetailSections(rows);
    overlay.hidden = false;
    requestAnimationFrame(() => overlay.classList.add("is-open"));
  }

  function hideRowDetailDrawer() {
    const overlay = $("#rowDetailOverlay");
    if (!overlay) return;
    overlay.classList.remove("is-open");
    setTimeout(() => {
      if (!overlay.classList.contains("is-open")) {
        overlay.hidden = true;
      }
    }, 180);
  }

  async function buildRowPayload(row) {
    const rich = await buildDocExportFromRow(row).catch(() => null);
    const rows = rich?.rows?.length ? rich.rows : extractRowForPdf(row);
    return {
      title: rich?.title || rowSectionTitle(row),
      subtitle: rich?.subtitle || rowPrimaryText(row),
      rows,
    };
  }

  function bindRowActionFlow() {
    if (document.body.dataset.rowActionBound === "true") return;
    document.body.dataset.rowActionBound = "true";

    document.addEventListener("click", async (e) => {
      const closeTrigger = e.target.closest("[data-row-detail-close]");
      if (closeTrigger || e.target.hasAttribute("data-row-detail-backdrop")) {
        hideRowDetailDrawer();
        return;
      }

      const btn = e.target.closest(".row-icon-action");
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();

      const row = btn.closest("tr");
      if (!row) return;
      const action = btn.dataset.rowAction || "view";

      if (action === "view") {
        const detail = await buildRowPayload(row);
        showRowDetailDrawer(detail.title, detail.subtitle, detail.rows);
        return;
      }

      if (action === "csv") {
        const detail = await buildDocExportFromRow(row).catch(() => null);
        const csv = detail?.rows?.length ? csvFromPairs(detail.rows) : csvFromTableRow(row);
        if (!csv) {
          notify("No row data to export");
          return;
        }
        const fileBase = [detail?.title || rowSectionTitle(row), detail?.subtitle || rowPrimaryText(row)]
          .filter(Boolean)
          .map(slugifyFilePart)
          .join("-");
        downloadTextFile(
          `${fileBase || "row-export"}-${new Date().toISOString().slice(0, 10)}.csv`,
          `\ufeff${csv}`,
          "text/csv;charset=utf-8"
        );
        notify("Row CSV exported");
        return;
      }

      const detail = await buildRowPayload(row);
      if (!detail.rows.length) {
        notify("No row data to export");
        return;
      }
      const html = buildPrintDocument(
        detail.title || "Row Export",
        `${detail.subtitle || rowSectionTitle(row)} | ${new Date().toLocaleString()}`,
        detail.rows
      );
      openPrint(html);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") hideRowDetailDrawer();
    });
  }

  function bindTableEnhancerObserver() {
    if (document.body.dataset.tableEnhancerObserved === "true") return;
    document.body.dataset.tableEnhancerObserved = "true";
    let queued = false;
    const sync = () => {
      queued = false;
      addRowExportButtons();
      ensureRowActionButtons();
    };
    const observer = new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(sync);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  window.printCoEnhanceTables = () => {
    addRowExportButtons();
    ensureRowActionButtons();
  };

  function bindRowExportFlow() {
    if (document.body.dataset.rowExportBound === "true") return;
    document.body.dataset.rowExportBound = "true";

    document.addEventListener("click", async (e) => {
      const btn = e.target.closest(".row-export-btn");
      if (btn) {
        const card = btn.closest(".card");
        if (!card) return;
        const format = btn.dataset.exportFormat || "pdf";
        const title = ($("h3", card)?.textContent || "Data Export")
          .replace("Export as PDF", "")
          .replace("Export as CSV", "")
          .trim();

        if (format === "csv") {
          clearRowExportArmed();
          const csv = csvFromCard(card);
          if (!csv) {
            notify("No table data to export");
            return;
          }
          downloadTextFile(
            `${slugifyFilePart(title || "table-export")}-${new Date().toISOString().slice(0, 10)}.csv`,
            `\ufeff${csv}`,
            "text/csv;charset=utf-8"
          );
          notify("CSV exported");
          return;
        }

        clearRowExportArmed();
        const tables = tableExportsFromCard(card);
        if (!tables.length) {
          notify("No table data to export");
          return;
        }
        const html = buildTablePrintDocument(
          title || "Table Export",
          new Date().toLocaleString(),
          tables
        );
        openPrint(html);
        return;
      }

      const row = e.target.closest(".data-table tbody tr");
      if (!row) return;
      const card = row.closest(".card");
      if (!card || card.dataset.rowExportArmed !== "true") return;
      const format = card.dataset.rowExportFormat || "pdf";
      const title = ($("h3", card)?.textContent || "Data Row")
        .replace("Export as PDF", "")
        .replace("Export as CSV", "")
        .trim();

      try {
        const rich = await buildDocExportFromRow(row);
        const rows = rich?.rows?.length ? rich.rows : extractRowForPdf(row);
        if (!rows.length) {
          clearRowExportArmed();
          return;
        }
        const html = buildPrintDocument(rich?.title || "Row Export", `${rich?.subtitle || title} | ${new Date().toLocaleString()}`, rows);
        clearRowExportArmed();
        openPrint(html);
      } catch {
        const rows = extractRowForPdf(row);
        if (!rows.length) {
          clearRowExportArmed();
          return;
        }
        const html = buildPrintDocument("Row Export", `${title} | ${new Date().toLocaleString()}`, rows);
        clearRowExportArmed();
        openPrint(html);
      }
    });
  }

  function addPdfTools() {
    const accounts = $("#accounts");
    if (accounts && !$("#pdfToolsAccounts")) {
      accounts.insertAdjacentHTML(
        "beforeend",
        `
        <div id="pdfToolsAccounts" class="card">
          <h3>Export Invoice PDFs</h3>
          <div class="pdf-section">
            <label>Purchase Invoice <select id="pdfPinvId"></select></label>
            <button id="printPinvBtn" class="pdf-export-btn" type="button">Save Purchase Invoice as PDF</button>
          </div>
          <div class="pdf-section">
            <label>Sales Invoice <select id="pdfSinvId"></select></label>
            <button id="printSinvBtn" class="pdf-export-btn" type="button">Save Sales Invoice as PDF</button>
          </div>
        </div>
      `
      );
    }
    $("#pdfToolsProduction")?.remove();
  }

  function fillSelect(id, rows, labelFn) {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = rows
      .map((r) => `<option value="${r.id}">${labelFn(r)}</option>`)
      .join("");
  }

  async function loadPdfOptions() {
    try {
      const [pinv, sinv] = await Promise.all([
        api("/api/accounts/purchase-invoices"),
        api("/api/accounts/sales-invoices"),
      ]);
      fillSelect("pdfPinvId", pinv, (x) => `${x.invoiceNo} | PO ${x.poId} | ${x.status}`);
      fillSelect("pdfSinvId", sinv, (x) => `${x.invoiceNo} | SO ${x.soId} | ${x.status}`);
    } catch {
      // Keep quiet; app itself may still load later.
    }
  }

  async function bindPdfActions() {
    $("#printPinvBtn")?.addEventListener("click", async () => {
      const id = $("#pdfPinvId")?.value;
      if (!id) return;
      const rows = await api("/api/accounts/purchase-invoices");
      const inv = rows.find((x) => String(x.id) === String(id));
      if (!inv) return;
      const html = buildPrintDocument("Purchase Invoice", inv.invoiceNo, [
        { label: "Invoice No", value: inv.invoiceNo },
        { label: "PO ID", value: inv.poId },
        { label: "GRN ID", value: inv.grnId },
        { label: "Vendor ID", value: inv.vendorId },
        { label: "Total Amount", value: inv.totalAmount },
        { label: "Status", value: inv.status },
      ]);
      openPrint(html);
    });

    $("#printSinvBtn")?.addEventListener("click", async () => {
      const id = $("#pdfSinvId")?.value;
      if (!id) return;
      const rows = await api("/api/accounts/sales-invoices");
      const inv = rows.find((x) => String(x.id) === String(id));
      if (!inv) return;
      const html = buildPrintDocument("Sales Invoice", inv.invoiceNo, [
        { label: "Invoice No", value: inv.invoiceNo },
        { label: "SO ID", value: inv.soId },
        { label: "Customer ID", value: inv.customerId },
        { label: "Total Amount", value: inv.totalAmount },
        { label: "Status", value: inv.status },
      ]);
      openPrint(html);
    });

  }

  function init() {
    decorateShell();
    decorateModules();
    alignFieldLabels();
    bindLoginPasswordToggle();
    makeCardsCollapsible();
    setupSemanticDropdowns();
    ensureRowDetailDrawer();
    addRowExportButtons();
    ensureRowActionButtons();
    bindRowExportFlow();
    bindRowActionFlow();
    bindTableEnhancerObserver();
    addPdfTools();
    bindPdfActions();
    loadPdfOptions();
    renderProfessionalDashboard();
    setInterval(() => {
      decorateShell();
      decorateModules();
      alignFieldLabels();
      bindLoginPasswordToggle();
      makeCardsCollapsible();
      setupSemanticDropdowns();
      addRowExportButtons();
      ensureRowActionButtons();
      loadPdfOptions();
      renderProfessionalDashboard();
    }, 12000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
