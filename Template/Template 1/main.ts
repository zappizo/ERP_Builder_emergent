import './style.css'

import { api } from './api'
import { registerPwa } from './pwa'
import { renderApp } from './templates'
import type { AppState, Company, CompanyFilters, Section } from './types'

const rootElement = document.querySelector<HTMLDivElement>('#app')

if (!rootElement) {
  throw new Error('Application root element not found.')
}

const root = rootElement

const defaultFilters: CompanyFilters = {
  search: '',
  status: '',
  sortBy: 'updated_at',
  direction: 'desc',
}

const state: AppState = {
  activeSection: 'dashboard',
  crmOpenSection: null,
  salesOpenSection: 'pipeline',
  projectsOpenSection: 'intake',
  hrmOpenSection: 'setup',
  accountingOpenSection: 'billing',
  investmentOpenSection: 'capture',
  crmCompanyColumnFilters: {
    name: '',
    contact: '',
    email: '',
    phone: '',
    website: '',
    industry: '',
    location: '',
  },
  crmCompanyStatusFilter: '',
  crmCallerSelectedCompanyId: null,
  crmCallerSelectedLeadId: null,
  crmLeadColumnFilters: {
    company: '',
    contact: '',
    requirement: '',
    budget: '',
  },
  crmLeadStatusFilter: '',
  crmModalCompanyId: null,
  crmModalMode: null,
  crmOpenCompanyStatusId: null,
  salesQuotationCompanyId: null,
  salesQuotationServicePreset: null,
  salesOpenQuotationStatusId: null,
  salesModalQuotationId: null,
  loading: false,
  saving: false,
  message: '',
  error: '',
  apiAvailable: false,
  filters: { ...defaultFilters },
  dashboard: null,
  companies: [],
  leads: [],
  clients: [],
  existingCustomers: [],
  quotations: [],
  orders: [],
  invoices: [],
  projects: [],
  tasks: [],
  employees: [],
  assignments: [],
  ledger: [],
  expenses: [],
  financeSummary: null,
  investments: [],
  events: [],
}

const tableColumnFilters: Record<string, string[]> = {}

function resetCompanyTableFilters(): void {
  state.crmCompanyColumnFilters = {
    name: '',
    contact: '',
    email: '',
    phone: '',
    website: '',
    industry: '',
    location: '',
  }
  state.crmCompanyStatusFilter = ''
}

function resetLeadTableFilters(): void {
  state.crmLeadColumnFilters = {
    company: '',
    contact: '',
    requirement: '',
    budget: '',
  }
  state.crmLeadStatusFilter = ''
}

function companySortValue(company: Company, sortBy: CompanyFilters['sortBy']): string | number {
  switch (sortBy) {
    case 'name':
      return company.name.toLowerCase()
    case 'status':
      return company.status.toLowerCase()
    case 'industry':
      return String(company.industry ?? '').toLowerCase()
    case 'created_at':
      return company.created_at
    case 'updated_at':
    default:
      return company.updated_at
  }
}

function sortCompanies(companies: Company[]): Company[] {
  return [...companies].sort((left, right) => {
    const leftValue = companySortValue(left, state.filters.sortBy)
    const rightValue = companySortValue(right, state.filters.sortBy)
    const direction = state.filters.direction === 'asc' ? 1 : -1

    if (leftValue < rightValue) return -1 * direction
    if (leftValue > rightValue) return 1 * direction
    return 0
  })
}

function upsertCompanyInState(company: Company): void {
  const existingIndex = state.companies.findIndex((item) => item.id === company.id)
  if (existingIndex === -1) {
    state.companies = sortCompanies([company, ...state.companies])
    return
  }

  const nextCompanies = [...state.companies]
  nextCompanies[existingIndex] = company
  state.companies = sortCompanies(nextCompanies)
}

function render(): void {
  root.innerHTML = renderApp(state)
  attachTableExportToolbars(root)
  enhanceTableColumnFilters(root)
  renumberCompanyContacts(root)
}

function value(formData: FormData, key: string): string {
  return (formData.get(key)?.toString().trim() ?? '')
}

function optional(formData: FormData, key: string): string | undefined {
  const currentValue = value(formData, key)
  return currentValue ? currentValue : undefined
}

function numberValue(formData: FormData, key: string): number | undefined {
  const currentValue = value(formData, key)
  return currentValue ? Number(currentValue) : undefined
}

function gstAmount(baseAmount: number | undefined, rateValue: string): number {
  const rate = Number(rateValue || '0')
  const amount = baseAmount ?? 0
  return Number((amount * rate / 100).toFixed(2))
}

function listValues(formData: FormData, key: string): string[] {
  return formData.getAll(key).map((entry) => entry.toString().trim())
}

function csvList(input: string): string[] {
  return input
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function normalizeTableSearchText(value: string | number | null | undefined): string {
  return String(value ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9\s]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function renumberCompanyContacts(form: ParentNode): void {
  const rows = Array.from(form.querySelectorAll<HTMLElement>('[data-company-contact-row="true"]'))
  rows.forEach((row, index) => {
    const heading = row.querySelector<HTMLElement>('[data-contact-index="true"]')
    if (heading) {
      heading.textContent = String(index + 1)
    }
    const eyebrow = row.querySelector<HTMLElement>('.eyebrow')
    if (eyebrow) {
      eyebrow.textContent = index === 0 ? 'Primary contact' : 'Additional contact'
    }
    const removeButton = row.querySelector<HTMLButtonElement>('[data-remove-company-contact="true"]')
    if (removeButton) {
      removeButton.disabled = rows.length === 1
    }
  })
}

function companyContactRowMarkup(index: number): string {
  return `
    <article class="crm-contact-card" data-company-contact-row="true">
      <div class="crm-contact-card-head">
        <div>
          <p class="eyebrow">${index === 0 ? 'Primary contact' : 'Additional contact'}</p>
          <h4>Contact <span data-contact-index="true">${index + 1}</span></h4>
        </div>
        <button type="button" class="ghost-button" data-remove-company-contact="true">Remove</button>
      </div>
      <div class="crm-contact-fields">
        <input name="contact_full_name" placeholder="Contact Person" required />
        <input name="contact_email" placeholder="Email ID of Contact Person" type="email" required />
        <input name="contact_phone" placeholder="Phone Number" required />
      </div>
    </article>
  `
}

function leadIdForCompany(companyId: string | null | undefined): string | null {
  if (!companyId) {
    return null
  }

  return state.leads.find((lead) => lead.company_id === companyId)?.id ?? null
}

function setCallerContext(companyId: string | null | undefined): void {
  const normalizedCompanyId = companyId?.trim() || null
  state.activeSection = 'crm'
  state.crmOpenSection = 'caller-workspace'
  state.crmCallerSelectedCompanyId = normalizedCompanyId
  state.crmCallerSelectedLeadId = leadIdForCompany(normalizedCompanyId)
  state.crmModalCompanyId = null
  state.crmModalMode = null
  state.message = ''
  state.error = ''
}

function focusLeadEnrichment(): void {
  requestAnimationFrame(() => {
    const field = root.querySelector<HTMLElement>('[data-lead-focus="true"]')
    field?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    if (field instanceof HTMLTextAreaElement || field instanceof HTMLInputElement) {
      field.focus()
    }
  })
}

function focusSalesQuotationDesk(): void {
  requestAnimationFrame(() => {
    const field = root.querySelector<HTMLElement>('[data-sales-quotation-focus="true"]')
    field?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    if (field instanceof HTMLSelectElement || field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) {
      field.focus()
    }
  })
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function activeModuleStageKey(): string {
  switch (state.activeSection) {
    case 'crm':
      return state.crmOpenSection ?? 'default'
    case 'sales':
      return state.salesOpenSection ?? 'default'
    case 'projects':
      return state.projectsOpenSection ?? 'default'
    case 'hrm':
      return state.hrmOpenSection ?? 'default'
    case 'accounting':
      return state.accountingOpenSection ?? 'default'
    case 'investment':
      return state.investmentOpenSection ?? 'default'
    case 'dashboard':
    default:
      return 'default'
  }
}

function tableFilterKey(table: HTMLTableElement, index: number): string {
  const stageTitle =
    table.closest<HTMLElement>('.crm-stage-card')?.querySelector<HTMLElement>('.crm-stage-header h3')?.textContent?.trim() ??
    state.activeSection
  const panelTitle =
    table.closest<HTMLElement>('.panel')?.querySelector<HTMLElement>('.panel-head h2')?.textContent?.trim() ??
    `table-${index + 1}`
  return slugify(`${state.activeSection} ${activeModuleStageKey()} ${stageTitle} ${panelTitle} ${index + 1}`)
}

function applyTableColumnFilters(table: HTMLTableElement): void {
  const tbody = table.tBodies.item(0)
  const filterKey = table.dataset.columnFilterKey ?? ''
  if (!tbody || !filterKey) {
    return
  }

  const filters = tableColumnFilters[filterKey] ?? []
  const rows = Array.from(tbody.rows).filter((row) => !row.dataset.filterEmptyRow)
  const dataRows = rows.filter((row) => !(row.cells.length === 1 && (row.cells.item(0)?.colSpan ?? 0) > 1))
  const activeFilters = filters.some((filterValue) => filterValue?.trim())

  dataRows.forEach((row) => {
    const visible = filters.every((filterValue, columnIndex) => {
      const normalizedFilter = filterValue?.trim()
      if (!normalizedFilter) {
        return true
      }
      const cellValue = row.cells.item(columnIndex)?.innerText ?? ''
      return normalizeTableSearchText(cellValue).includes(normalizeTableSearchText(normalizedFilter))
    })
    row.hidden = !visible
  })

  const existingEmptyRow = tbody.querySelector<HTMLTableRowElement>('[data-filter-empty-row="true"]')
  if (existingEmptyRow) {
    existingEmptyRow.remove()
  }

  const visibleDataRows = dataRows.filter((row) => !row.hidden)
  if (activeFilters && dataRows.length > 0 && visibleDataRows.length === 0) {
    const emptyRow = document.createElement('tr')
    emptyRow.dataset.filterEmptyRow = 'true'
    const cell = document.createElement('td')
    cell.colSpan = table.querySelectorAll('thead th').length || 1
    cell.textContent = 'No matching records found.'
    emptyRow.appendChild(cell)
    tbody.appendChild(emptyRow)
  }
}

function enhanceTableColumnFilters(container: ParentNode): void {
  const tables = Array.from(container.querySelectorAll<HTMLTableElement>('.table-wrap table'))
  tables.forEach((table, index) => {
    const headerRow = table.querySelector<HTMLTableRowElement>('thead tr')
    if (!headerRow) {
      return
    }

    const headerCells = Array.from(headerRow.cells)
    if (!headerCells.length || headerCells.some((cell) => cell.querySelector('.crm-table-column-filter'))) {
      return
    }

    const filterKey = tableFilterKey(table, index)
    table.dataset.columnFilterKey = filterKey
    table.classList.add('crm-filterable-table')
    const savedFilters = tableColumnFilters[filterKey] ?? []

    headerCells.forEach((cell, columnIndex) => {
      const label = cell.textContent?.trim() ?? ''
      if (!label || /^actions?$/i.test(label)) {
        return
      }

      const wrapper = document.createElement('label')
      wrapper.className = 'crm-table-column-filter'

      const title = document.createElement('span')
      title.textContent = label

      const input = document.createElement('input')
      input.className = 'crm-table-filter-input'
      input.type = 'search'
      input.placeholder = 'Filter'
      input.value = savedFilters[columnIndex] ?? ''
      input.setAttribute('data-table-column-filter', filterKey)
      input.setAttribute('data-table-column-index', String(columnIndex))
      input.setAttribute('aria-label', `Filter ${label}`)

      wrapper.append(title, input)
      cell.textContent = ''
      cell.appendChild(wrapper)
    })

    applyTableColumnFilters(table)
  })
}

function attachTableExportToolbars(container: ParentNode): void {
  const wraps = Array.from(container.querySelectorAll<HTMLElement>('.table-wrap'))
  wraps.forEach((wrap, index) => {
    const table = wrap.querySelector<HTMLTableElement>('table')
    if (!table) {
      return
    }
    const panel = wrap.closest<HTMLElement>('.panel')
    const title =
      panel?.querySelector<HTMLElement>('.panel-head h2')?.textContent?.trim() ||
      panel?.querySelector<HTMLElement>('h2')?.textContent?.trim() ||
      `table-${index + 1}`
    const encodedTitle = encodeURIComponent(title)
    const exportId = `table-export-${index + 1}`
    table.dataset.exportId = exportId
    table.dataset.exportLabel = title
    wrap.insertAdjacentHTML(
      'beforebegin',
      `
        <div class="table-export-bar">
          <span class="table-export-title">Export</span>
          <div class="action-row">
            <button type="button" class="ghost-button table-export-button" data-export-table="${exportId}" data-export-format="excel" data-export-label="${encodedTitle}">Export Excel</button>
            <button type="button" class="ghost-button table-export-button" data-export-table="${exportId}" data-export-format="pdf" data-export-label="${encodedTitle}">Export PDF</button>
          </div>
        </div>
      `,
    )
  })
}

function extractTableData(table: HTMLTableElement, row?: HTMLTableRowElement): { headers: string[]; rows: string[][] } {
  const headerCells = Array.from(table.querySelectorAll('thead th'))
  const includedIndexes = headerCells
    .map((cell, index) => ({ text: cell.textContent?.trim() ?? '', index }))
    .filter(({ text }) => !/^actions?$/i.test(text))
  const headers = includedIndexes.map(({ text }) => text)
  const sourceRows: HTMLTableRowElement[] = row ?
    [row] :
    Array.from(table.querySelectorAll<HTMLTableRowElement>('tbody tr')).filter(
      (currentRow) => !currentRow.hidden && !currentRow.dataset.filterEmptyRow,
    )
  const rows = sourceRows
    .map((currentRow) =>
      includedIndexes.map(({ index }) => {
        const cell = currentRow.cells.item(index)
        return cell?.innerText.replace(/\s+/g, ' ').trim() ?? ''
      }),
    )
    .filter((cells) => cells.some((cell) => cell))
  return { headers, rows }
}

function downloadFile(filename: string, content: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function exportTableAsExcel(label: string, table: HTMLTableElement, row?: HTMLTableRowElement): void {
  const { headers, rows } = extractTableData(table, row)
  const tableHtml = `
    <table>
      <thead><tr>${headers.map((header) => `<th>${header}</th>`).join('')}</tr></thead>
      <tbody>${rows.map((cells) => `<tr>${cells.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>
    </table>
  `
  const workbook = `
    <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">
      <head><meta charset="utf-8" /></head>
      <body>${tableHtml}</body>
    </html>
  `
  downloadFile(`${slugify(label)}.xls`, workbook, 'application/vnd.ms-excel;charset=utf-8')
}

function exportTableAsPdf(label: string, table: HTMLTableElement, row?: HTMLTableRowElement): void {
  const { headers, rows } = extractTableData(table, row)
  const iframe = document.createElement('iframe')
  iframe.style.position = 'fixed'
  iframe.style.right = '0'
  iframe.style.bottom = '0'
  iframe.style.width = '0'
  iframe.style.height = '0'
  iframe.style.border = '0'
  iframe.setAttribute('aria-hidden', 'true')
  document.body.appendChild(iframe)

  const cleanup = () => {
    window.setTimeout(() => iframe.remove(), 300)
  }

  const html = `
    <html>
      <head>
        <title>${label}</title>
        <style>
          @page { size: auto; margin: 14mm; }
          body { font-family: Arial, sans-serif; padding: 24px; color: #111827; }
          h1 { font-size: 20px; margin-bottom: 16px; }
          table { width: 100%; border-collapse: collapse; }
          th, td { border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }
          th { background: #f3f4f6; text-transform: uppercase; font-size: 12px; letter-spacing: 0.08em; }
        </style>
      </head>
      <body>
        <h1>${label}</h1>
        <table>
          <thead><tr>${headers.map((header) => `<th>${header}</th>`).join('')}</tr></thead>
          <tbody>${rows.map((cells) => `<tr>${cells.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>
        </table>
      </body>
    </html>
  `
  const frameWindow = iframe.contentWindow
  const frameDocument = iframe.contentDocument ?? frameWindow?.document
  if (!frameWindow || !frameDocument) {
    cleanup()
    state.error = 'PDF export could not start.'
    render()
    return
  }

  frameDocument.open()
  frameDocument.write(html)
  frameDocument.close()

  const triggerPrint = () => {
    frameWindow.onafterprint = cleanup
    frameWindow.focus()
    frameWindow.print()
    window.setTimeout(cleanup, 1500)
  }

  if (frameDocument.readyState === 'complete') {
    window.setTimeout(triggerPrint, 150)
  } else {
    iframe.onload = () => {
      window.setTimeout(triggerPrint, 150)
    }
  }
}

function exportElementAsExcel(label: string, element: HTMLElement): void {
  const clone = element.cloneNode(true) as HTMLElement
  clone.querySelectorAll('button').forEach((button) => button.remove())
  const workbook = `
    <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">
      <head><meta charset="utf-8" /></head>
      <body>${clone.innerHTML}</body>
    </html>
  `
  downloadFile(`${slugify(label)}.xls`, workbook, 'application/vnd.ms-excel;charset=utf-8')
}

function exportElementAsPdf(label: string, element: HTMLElement): void {
  const clone = element.cloneNode(true) as HTMLElement
  clone.querySelectorAll('button').forEach((button) => button.remove())
  const iframe = document.createElement('iframe')
  iframe.style.position = 'fixed'
  iframe.style.right = '0'
  iframe.style.bottom = '0'
  iframe.style.width = '0'
  iframe.style.height = '0'
  iframe.style.border = '0'
  iframe.setAttribute('aria-hidden', 'true')
  document.body.appendChild(iframe)

  const cleanup = () => {
    window.setTimeout(() => iframe.remove(), 300)
  }

  const frameWindow = iframe.contentWindow
  const frameDocument = iframe.contentDocument ?? frameWindow?.document
  if (!frameWindow || !frameDocument) {
    cleanup()
    state.error = 'PDF export could not start.'
    render()
    return
  }

  frameDocument.open()
  frameDocument.write(`
    <html>
      <head>
        <title>${label}</title>
        <style>
          @page { size: auto; margin: 14mm; }
          body { font-family: Arial, sans-serif; padding: 24px; color: #111827; }
          h1, h2, h3 { margin: 0 0 12px; }
          .detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 16px; }
          .detail-grid p { margin: 0; }
          .detail-grid strong { display: block; margin-bottom: 4px; }
          .crm-contact-view-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
          .crm-contact-view-card { border: 1px solid #d1d5db; padding: 10px; border-radius: 8px; }
          .status-chip { display: inline-block; padding: 4px 8px; border-radius: 999px; border: 1px solid #d1d5db; }
        </style>
      </head>
      <body>
        <h1>${label}</h1>
        ${clone.innerHTML}
      </body>
    </html>
  `)
  frameDocument.close()

  const triggerPrint = () => {
    frameWindow.onafterprint = cleanup
    frameWindow.focus()
    frameWindow.print()
    window.setTimeout(cleanup, 1500)
  }

  if (frameDocument.readyState === 'complete') {
    window.setTimeout(triggerPrint, 150)
  } else {
    iframe.onload = () => {
      window.setTimeout(triggerPrint, 150)
    }
  }
}

async function loadAllData(): Promise<void> {
  state.loading = true
  state.error = ''
  render()

  try {
    await api.health()
    state.apiAvailable = true

    const results = await Promise.allSettled([
      api.dashboard(),
      api.companies(state.filters),
      api.leads(),
      api.clients(),
      api.existingCustomers(),
      api.quotations(),
      api.orders(),
      api.invoices(),
      api.projects(),
      api.tasks(),
      api.employees(),
      api.assignments(),
      api.ledger(),
      api.expenses(),
      api.financeSummary(),
      api.partnerInvestments(),
      api.events(),
    ])

    const [
      dashboardResult,
      companiesResult,
      leadsResult,
      clientsResult,
      existingCustomersResult,
      quotationsResult,
      ordersResult,
      invoicesResult,
      projectsResult,
      tasksResult,
      employeesResult,
      assignmentsResult,
      ledgerResult,
      expensesResult,
      financeSummaryResult,
      investmentsResult,
      eventsResult,
    ] = results

    if (dashboardResult.status === 'fulfilled') state.dashboard = dashboardResult.value
    if (companiesResult.status === 'fulfilled') state.companies = companiesResult.value
    if (leadsResult.status === 'fulfilled') state.leads = leadsResult.value
    if (clientsResult.status === 'fulfilled') state.clients = clientsResult.value
    if (existingCustomersResult.status === 'fulfilled') state.existingCustomers = existingCustomersResult.value
    if (quotationsResult.status === 'fulfilled') state.quotations = quotationsResult.value
    if (ordersResult.status === 'fulfilled') state.orders = ordersResult.value
    if (invoicesResult.status === 'fulfilled') state.invoices = invoicesResult.value
    if (projectsResult.status === 'fulfilled') state.projects = projectsResult.value
    if (tasksResult.status === 'fulfilled') state.tasks = tasksResult.value
    if (employeesResult.status === 'fulfilled') state.employees = employeesResult.value
    if (assignmentsResult.status === 'fulfilled') state.assignments = assignmentsResult.value
    if (ledgerResult.status === 'fulfilled') state.ledger = ledgerResult.value
    if (expensesResult.status === 'fulfilled') state.expenses = expensesResult.value
    if (financeSummaryResult.status === 'fulfilled') state.financeSummary = financeSummaryResult.value
    if (investmentsResult.status === 'fulfilled') state.investments = investmentsResult.value
    if (eventsResult.status === 'fulfilled') state.events = eventsResult.value

    const failedRefreshes = results
      .filter((result): result is PromiseRejectedResult => result.status === 'rejected')
      .map((result) => result.reason instanceof Error ? result.reason.message : 'Unknown refresh failure')

    if (failedRefreshes.length) {
      state.error = failedRefreshes[0]
    }
  } catch (error) {
    state.apiAvailable = false
    state.error = error instanceof Error ? error.message : 'Unable to reach the Athena API.'
  } finally {
    state.loading = false
    render()
  }
}

async function runAction<T>(action: () => Promise<T>, successMessage: string): Promise<T | undefined> {
  state.saving = true
  state.error = ''
  state.message = ''
  render()

  try {
    const result = await action()
    state.message = successMessage
    await loadAllData()
    return result
  } catch (error) {
    state.error = error instanceof Error ? error.message : 'Action failed.'
    state.saving = false
    render()
  } finally {
    state.saving = false
    render()
  }
}

root.addEventListener('click', (event) => {
  const target = event.target as HTMLElement
  const refreshButton = target.closest<HTMLElement>('[data-refresh-app]')
  if (refreshButton) {
    if (state.loading || state.saving) {
      return
    }
    void loadAllData()
    return
  }

  const crmStatusShell = target.closest<HTMLElement>('[data-crm-company-status-shell]')
  if (state.crmOpenCompanyStatusId && !crmStatusShell) {
    state.crmOpenCompanyStatusId = null
    render()
  }
  const statusShell = target.closest<HTMLElement>('[data-sales-quotation-status-shell]')
  if (state.salesOpenQuotationStatusId && !statusShell) {
    state.salesOpenQuotationStatusId = null
    render()
  }
  const modalExportButton = target.closest<HTMLElement>('[data-export-modal]')
  if (modalExportButton) {
    const format = modalExportButton.dataset.exportModal ?? 'excel'
    const label = modalExportButton.dataset.exportLabel ?? 'company-profile'
    const modalCard = target.closest<HTMLElement>('[data-crm-modal-card]')
    if (!modalCard) {
      return
    }
    if (format === 'pdf') {
      exportElementAsPdf(label, modalCard)
    } else {
      exportElementAsExcel(label, modalCard)
    }
    return
  }

  const tableExportButton = target.closest<HTMLElement>('[data-export-table]')
  if (tableExportButton) {
    const exportId = tableExportButton.dataset.exportTable ?? ''
    const format = tableExportButton.dataset.exportFormat ?? 'excel'
    const label = decodeURIComponent(tableExportButton.dataset.exportLabel ?? 'table-export')
    const table = root.querySelector<HTMLTableElement>(`table[data-export-id="${exportId}"]`)
    if (!table) {
      return
    }
    if (format === 'pdf') {
      exportTableAsPdf(label, table)
    } else {
      exportTableAsExcel(label, table)
    }
    return
  }

  const rowExportButton = target.closest<HTMLElement>('[data-export-row]')
  if (rowExportButton) {
    const row = rowExportButton.closest<HTMLTableRowElement>('tr')
    const table = row?.closest<HTMLTableElement>('table')
    const label = rowExportButton.dataset.exportLabel ?? table?.dataset.exportLabel ?? 'row-export'
    const format = rowExportButton.dataset.exportRow ?? 'excel'
    if (!row || !table) {
      return
    }
    if (format === 'pdf') {
      exportTableAsPdf(label, table, row)
    } else {
      exportTableAsExcel(label, table, row)
    }
    return
  }

  const addCompanyContactButton = target.closest<HTMLElement>('[data-add-company-contact]')
  if (addCompanyContactButton) {
    const form = addCompanyContactButton.closest<HTMLFormElement>('#company-form')
    const contactList = form?.querySelector<HTMLElement>('[data-company-contact-list]')
    if (!form || !contactList) {
      return
    }
    contactList.insertAdjacentHTML(
      'beforeend',
      companyContactRowMarkup(contactList.querySelectorAll('[data-company-contact-row="true"]').length),
    )
    renumberCompanyContacts(form)
    return
  }

  const removeCompanyContactButton = target.closest<HTMLElement>('[data-remove-company-contact]')
  if (removeCompanyContactButton) {
    const form = removeCompanyContactButton.closest<HTMLFormElement>('#company-form')
    const row = removeCompanyContactButton.closest<HTMLElement>('[data-company-contact-row="true"]')
    const rowCount = form?.querySelectorAll('[data-company-contact-row="true"]').length ?? 0
    if (!form || !row || rowCount <= 1) {
      return
    }
    row.remove()
    renumberCompanyContacts(form)
    return
  }

  const crmSectionButton = target.closest<HTMLElement>('[data-crm-section]')
  if (crmSectionButton) {
    const sectionId = crmSectionButton.dataset.crmSection as AppState['crmOpenSection']
    state.crmOpenSection = state.crmOpenSection === sectionId ? null : sectionId
    state.message = ''
    state.error = ''
    render()
    return
  }

  const salesSectionButton = target.closest<HTMLElement>('[data-sales-section]')
  if (salesSectionButton) {
    const sectionId = salesSectionButton.dataset.salesSection as AppState['salesOpenSection']
    state.salesOpenSection = state.salesOpenSection === sectionId ? null : sectionId
    state.message = ''
    state.error = ''
    render()
    return
  }

  const projectsSectionButton = target.closest<HTMLElement>('[data-projects-section]')
  if (projectsSectionButton) {
    const sectionId = projectsSectionButton.dataset.projectsSection as AppState['projectsOpenSection']
    state.projectsOpenSection = state.projectsOpenSection === sectionId ? null : sectionId
    state.message = ''
    state.error = ''
    render()
    return
  }

  const hrmSectionButton = target.closest<HTMLElement>('[data-hrm-section]')
  if (hrmSectionButton) {
    const sectionId = hrmSectionButton.dataset.hrmSection as AppState['hrmOpenSection']
    state.hrmOpenSection = state.hrmOpenSection === sectionId ? null : sectionId
    state.message = ''
    state.error = ''
    render()
    return
  }

  const accountingSectionButton = target.closest<HTMLElement>('[data-accounting-section]')
  if (accountingSectionButton) {
    const sectionId = accountingSectionButton.dataset.accountingSection as AppState['accountingOpenSection']
    state.accountingOpenSection = state.accountingOpenSection === sectionId ? null : sectionId
    state.message = ''
    state.error = ''
    render()
    return
  }

  const investmentSectionButton = target.closest<HTMLElement>('[data-investment-section]')
  if (investmentSectionButton) {
    const sectionId = investmentSectionButton.dataset.investmentSection as AppState['investmentOpenSection']
    state.investmentOpenSection = state.investmentOpenSection === sectionId ? null : sectionId
    state.message = ''
    state.error = ''
    render()
    return
  }

  const companyActionButton = target.closest<HTMLElement>('[data-company-action]')
  if (companyActionButton) {
    state.crmModalCompanyId = companyActionButton.dataset.companyId ?? null
    state.crmModalMode = (companyActionButton.dataset.companyAction as AppState['crmModalMode']) ?? null
    render()
    return
  }

  const crmMailAction = target.closest<HTMLAnchorElement>('a[href^="mailto:"]')
  if (crmMailAction) {
    return
  }

  const crmCompanyStatusToggle = target.closest<HTMLElement>('[data-crm-company-status-toggle]')
  if (crmCompanyStatusToggle) {
    const companyId = crmCompanyStatusToggle.dataset.crmCompanyStatusToggle ?? null
    state.crmOpenCompanyStatusId =
      state.crmOpenCompanyStatusId === companyId ? null : companyId
    render()
    return
  }

  const crmCompanyStatusOption = target.closest<HTMLElement>('[data-crm-company-status-option]')
  if (crmCompanyStatusOption) {
    const companyId = crmCompanyStatusOption.dataset.crmCompanyStatusOption ?? ''
    const status = crmCompanyStatusOption.dataset.crmCompanyStatusValue ?? ''
    state.crmOpenCompanyStatusId = null
    void runAction(
      async () => api.updateCompany(companyId, { status }),
      'Company status updated.',
    )
    return
  }

  const crmCompanyRow = target.closest<HTMLElement>('[data-crm-company-row]')
  if (crmCompanyRow) {
    const companyId = crmCompanyRow.dataset.crmCompanyRow ?? null
    setCallerContext(companyId)
    render()
    focusLeadEnrichment()
    return
  }

  const salesCompanyButton = target.closest<HTMLElement>('[data-sales-company-id]')
  if (salesCompanyButton) {
    state.activeSection = 'sales'
    state.salesOpenSection = 'pipeline'
    state.salesQuotationCompanyId = salesCompanyButton.dataset.salesCompanyId ?? null
    state.salesQuotationServicePreset = null
    state.message = ''
    state.error = ''
    render()
    focusSalesQuotationDesk()
    return
  }

  const salesRenewButton = target.closest<HTMLElement>('[data-sales-renew-company-id]')
  if (salesRenewButton) {
    state.activeSection = 'sales'
    state.salesOpenSection = 'pipeline'
    state.salesQuotationCompanyId = salesRenewButton.dataset.salesRenewCompanyId ?? null
    state.salesQuotationServicePreset = 'AMC Renewal'
    state.message = ''
    state.error = ''
    render()
    focusSalesQuotationDesk()
    return
  }

  const salesQuotationSendAction = target.closest<HTMLElement>('[data-sales-quotation-send]')
  if (salesQuotationSendAction) {
    const quotationId = salesQuotationSendAction.dataset.salesQuotationSend ?? ''
    const quotationHref = salesQuotationSendAction.dataset.salesQuotationHref ?? ''
    if (quotationHref) {
      window.open(quotationHref, '_blank', 'noopener,noreferrer')
    }
    if (quotationId) {
      window.setTimeout(() => {
        void runAction(
          async () => api.updateQuotationStatus(quotationId, 'Sent'),
          'Quotation marked as sent.',
        )
      }, 0)
    }
    return
  }

  const salesQuotationStatusToggle = target.closest<HTMLElement>('[data-sales-quotation-status-toggle]')
  if (salesQuotationStatusToggle) {
    const quotationId = salesQuotationStatusToggle.dataset.salesQuotationStatusToggle ?? null
    state.salesOpenQuotationStatusId =
      state.salesOpenQuotationStatusId === quotationId ? null : quotationId
    render()
    return
  }

  const salesQuotationStatusOption = target.closest<HTMLElement>('[data-sales-quotation-status-option]')
  if (salesQuotationStatusOption) {
    const quotationId = salesQuotationStatusOption.dataset.salesQuotationStatusOption ?? ''
    const status = salesQuotationStatusOption.dataset.salesQuotationStatusValue ?? ''
    state.salesOpenQuotationStatusId = null
    void runAction(
      async () => api.updateQuotationStatus(quotationId, status),
      'Quotation status updated.',
    )
    return
  }

  const salesQuotationViewAction = target.closest<HTMLElement>('[data-sales-quotation-view]')
  if (salesQuotationViewAction) {
    state.salesModalQuotationId = salesQuotationViewAction.dataset.salesQuotationView ?? null
    state.salesOpenQuotationStatusId = null
    render()
    return
  }

  if (target.closest('[data-sales-modal-close]') || target.hasAttribute('data-sales-modal-backdrop')) {
    state.salesModalQuotationId = null
    render()
    return
  }

  if (target.closest('[data-crm-modal-close]') || target.hasAttribute('data-crm-modal-backdrop')) {
    state.crmModalCompanyId = null
    state.crmModalMode = null
    render()
    return
  }

  const navigationButton = target.closest<HTMLElement>('[data-view]')
  if (!navigationButton) {
    return
  }

  state.activeSection = navigationButton.dataset.view as Section
  state.message = ''
  state.error = ''
  render()
})

root.addEventListener('input', (event) => {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
  if (!(target instanceof HTMLInputElement)) {
    return
  }

  const filterKey = target.dataset.tableColumnFilter ?? ''
  const columnIndex = Number(target.dataset.tableColumnIndex ?? '-1')
  if (!filterKey || Number.isNaN(columnIndex) || columnIndex < 0) {
    return
  }

  const filters = [...(tableColumnFilters[filterKey] ?? [])]
  filters[columnIndex] = target.value.trim()
  tableColumnFilters[filterKey] = filters

  const table = target.closest<HTMLTableElement>('table')
  if (table) {
    applyTableColumnFilters(table)
  }
})

root.addEventListener('change', (event) => {
  const target = event.target as HTMLInputElement | HTMLSelectElement

  const companyColumnFilter = target.getAttribute('data-company-column-filter') as
    | keyof AppState['crmCompanyColumnFilters']
    | null
  if (companyColumnFilter) {
    state.crmCompanyColumnFilters = {
      ...state.crmCompanyColumnFilters,
      [companyColumnFilter]: target.value.trim(),
    }
    render()
    return
  }

  if (target.matches('[data-company-status-filter]')) {
    state.crmCompanyStatusFilter = target.value.trim()
    render()
    return
  }

  const leadColumnFilter = target.getAttribute('data-lead-column-filter') as
    | keyof AppState['crmLeadColumnFilters']
    | null
  if (leadColumnFilter) {
    state.crmLeadColumnFilters = {
      ...state.crmLeadColumnFilters,
      [leadColumnFilter]: target.value.trim(),
    }
    render()
    return
  }

  if (target.matches('[data-lead-status-filter]')) {
    state.crmLeadStatusFilter = target.value.trim()
    render()
  }
})

root.addEventListener('submit', async (event) => {
  event.preventDefault()
  const form = event.target as HTMLFormElement
  const formData = new FormData(form)

  switch (form.id) {
    case 'company-form':
      const contactNames = listValues(formData, 'contact_full_name')
      const contactEmails = listValues(formData, 'contact_email')
      const contactPhones = listValues(formData, 'contact_phone')
      const contacts = contactNames
        .map((full_name, index) => ({
          full_name,
          email: contactEmails[index] ?? '',
          phone: contactPhones[index] ?? '',
        }))
        .filter((contact) => contact.full_name || contact.email || contact.phone)

      if (!contacts.length) {
        state.error = 'Add at least one company contact before creating the company.'
        render()
        return
      }

      if (contacts.some((contact) => !contact.full_name || !contact.email || !contact.phone)) {
        state.error = 'Each company contact needs a name, email, and phone number.'
        render()
        return
      }

      const createdCompany = await runAction(
        async () =>
          api.createCompany({
            name: value(formData, 'name'),
            website: optional(formData, 'website'),
            industry: optional(formData, 'industry'),
            location: optional(formData, 'location'),
            contact_person: contacts[0]?.full_name,
            email: contacts[0]?.email,
            phone: contacts[0]?.phone,
            contacts,
          }),
        'Company added to the shared database.',
      )
      if (!state.error && createdCompany) {
        upsertCompanyInState(createdCompany)
        resetCompanyTableFilters()
        state.activeSection = 'crm'
        state.crmOpenSection = 'company-list'
        render()
      }
      return

    case 'company-import-form': {
      const file = formData.get('file')
      if (!(file instanceof File) || !file.size) {
        state.error = 'Choose a CSV file to import.'
        render()
        return
      }
      await runAction(
        async () => {
          const result = await api.importCompanies(file, value(formData, 'mapping_json'))
          state.message = `Imported ${result.imported} companies. Duplicates skipped: ${result.duplicates.length}.`
        },
        state.message || 'CSV import finished.',
      )
      if (!state.error) {
        resetCompanyTableFilters()
        state.activeSection = 'crm'
        state.crmOpenSection = 'company-list'
        render()
      }
      return
    }

    case 'lead-form':
      if (!value(formData, 'company_id')) {
        state.error = 'Select a company before saving lead details.'
        render()
        return
      }
      const leadCompanyId = value(formData, 'company_id')
      await runAction(
        async () =>
          api.upsertLead({
            company_id: leadCompanyId,
            requirement_summary: optional(formData, 'requirement_summary'),
            discussion_notes: optional(formData, 'discussion_notes'),
            estimated_scope: optional(formData, 'estimated_scope'),
            estimated_budget: numberValue(formData, 'estimated_budget'),
            status: optional(formData, 'status'),
          }),
        'Lead details updated.',
      )
      if (!state.error) {
        state.crmCallerSelectedCompanyId = leadCompanyId
        state.crmCallerSelectedLeadId = leadIdForCompany(leadCompanyId)
        resetLeadTableFilters()
        state.activeSection = 'crm'
        state.crmOpenSection = 'lead-register'
        render()
      }
      return

    case 'company-status-form':
      const updatedCompany = await runAction(
        async () => {
          const company = await api.updateCompany(value(formData, 'company_id'), { status: value(formData, 'status') })
          state.crmModalCompanyId = null
          state.crmModalMode = null
          return company
        },
        'Company status updated.',
      )
      if (!state.error && updatedCompany) {
        upsertCompanyInState(updatedCompany)
        resetCompanyTableFilters()
        state.activeSection = 'crm'
        state.crmOpenSection = 'company-list'
        render()
      }
      return

    case 'quotation-form':
      const quotationUnitPrice = numberValue(formData, 'unit_price')
      await runAction(
        async () =>
          api.createQuotation({
            company_id: value(formData, 'company_id'),
            service_description: value(formData, 'service_description'),
            scope_of_work: optional(formData, 'scope_of_work'),
            unit_price: quotationUnitPrice,
            taxes: gstAmount(quotationUnitPrice, value(formData, 'gst_rate')),
            validity_period_end: optional(formData, 'validity_period_end'),
          }),
        'Quotation created.',
      )
      if (!state.error) {
        state.activeSection = 'sales'
        state.salesOpenSection = 'proposals'
        state.salesQuotationCompanyId = null
        state.salesQuotationServicePreset = null
        render()
      }
      return

    case 'quotation-status-form':
      await runAction(
        async () => api.updateQuotationStatus(value(formData, 'quotation_id'), value(formData, 'status')),
        'Quotation status updated.',
      )
      return

    case 'quotation-approval-form':
      await runAction(
        async () =>
          api.approveQuotation(value(formData, 'quotation_id'), {
            payment_terms: optional(formData, 'payment_terms'),
            delivery_timeline: optional(formData, 'delivery_timeline'),
            project_title: optional(formData, 'project_title'),
            start_date: optional(formData, 'start_date'),
            deadline: optional(formData, 'deadline'),
            project_manager_id: optional(formData, 'project_manager_id'),
          }),
        'Quotation approved. Sales order and project created.',
      )
      return

    case 'invoice-form':
      const invoiceBaseAmount = numberValue(formData, 'amount')
      await runAction(
        async () =>
          api.createInvoice({
            client_id: value(formData, 'client_id'),
            sales_order_id: value(formData, 'sales_order_id'),
            amount: invoiceBaseAmount,
            taxes: gstAmount(invoiceBaseAmount, value(formData, 'gst_rate')),
            due_date: value(formData, 'due_date'),
            billing_mode: value(formData, 'billing_mode'),
          }),
        'Invoice generated and posted to accounting.',
      )
      return

    case 'payment-form':
      await runAction(
        async () =>
          api.recordPayment(value(formData, 'invoice_id'), {
            amount: numberValue(formData, 'amount'),
            payment_date: value(formData, 'payment_date'),
            payment_method: value(formData, 'payment_method'),
            reference: optional(formData, 'reference'),
          }),
        'Payment recorded and receivables updated.',
      )
      return

    case 'credit-note-form':
      await runAction(
        async () =>
          api.createCreditNote(value(formData, 'invoice_id'), {
            amount: numberValue(formData, 'amount'),
            reason: value(formData, 'reason'),
          }),
        'Credit note issued.',
      )
      return

    case 'requirement-form':
      await runAction(
        async () =>
          api.submitRequirements({
            client_id: value(formData, 'client_id'),
            project_id: optional(formData, 'project_id'),
            business_overview: optional(formData, 'business_overview'),
            project_objective: optional(formData, 'project_objective'),
            required_features: csvList(value(formData, 'required_features')),
            expected_deliverables: csvList(value(formData, 'expected_deliverables')),
            integrations: csvList(value(formData, 'integrations')),
            timeline_expectations: optional(formData, 'timeline_expectations'),
            budget_expectations: optional(formData, 'budget_expectations'),
          }),
        'Requirements stored inside the project workspace.',
      )
      return

    case 'task-form':
      await runAction(
        async () =>
          api.createTask(value(formData, 'project_id'), {
            task_name: value(formData, 'task_name'),
            description: optional(formData, 'description'),
            assigned_person_id: optional(formData, 'assigned_person_id'),
            deadline: optional(formData, 'deadline'),
            estimated_time: numberValue(formData, 'estimated_time'),
            priority: value(formData, 'priority'),
          }),
        'Task created.',
      )
      return

    case 'time-entry-form':
      await runAction(
        async () =>
          api.logTime(value(formData, 'task_id'), {
            employee_id: value(formData, 'employee_id'),
            hours_worked: numberValue(formData, 'hours_worked'),
            work_notes: optional(formData, 'work_notes'),
          }),
        'Time logged.',
      )
      return

    case 'employee-form':
      await runAction(
        async () =>
          api.createEmployee({
            name: value(formData, 'name'),
            employee_type: value(formData, 'employee_type'),
            department: value(formData, 'department'),
            role: value(formData, 'role'),
            joining_date: value(formData, 'joining_date'),
            salary_structure: value(formData, 'salary_structure'),
            monthly_compensation: numberValue(formData, 'monthly_compensation'),
          }),
        'Employee onboarded.',
      )
      return

    case 'assignment-form':
      await runAction(
        async () =>
          api.assignEmployee({
            employee_id: value(formData, 'employee_id'),
            project_id: value(formData, 'project_id'),
            allocation_role: value(formData, 'allocation_role'),
          }),
        'Employee allocated to project.',
      )
      return

    case 'performance-review-form':
      await runAction(
        async () =>
          api.createPerformanceReview({
            employee_id: value(formData, 'employee_id'),
            reviewer: value(formData, 'reviewer'),
            review_period: value(formData, 'review_period'),
            goals: optional(formData, 'goals'),
            feedback: optional(formData, 'feedback'),
            rating: numberValue(formData, 'rating'),
          }),
        'Performance review recorded.',
      )
      return

    case 'attendance-form':
      await runAction(
        async () =>
          api.recordAttendance({
            employee_id: value(formData, 'employee_id'),
            work_date: value(formData, 'work_date'),
            check_in: optional(formData, 'check_in'),
            check_out: optional(formData, 'check_out'),
            leave_record: optional(formData, 'leave_record'),
          }),
        'Attendance recorded.',
      )
      return

    case 'payroll-form':
      await runAction(
        async () =>
          api.createPayroll({
            employee_id: value(formData, 'employee_id'),
            period_start: value(formData, 'period_start'),
            period_end: value(formData, 'period_end'),
            base_amount: numberValue(formData, 'base_amount'),
            bonus: numberValue(formData, 'bonus') ?? 0,
            deductions: numberValue(formData, 'deductions') ?? 0,
            payment_date: optional(formData, 'payment_date'),
            status: value(formData, 'status'),
          }),
        'Payroll processed and posted.',
      )
      return

    case 'expense-form':
      await runAction(
        async () =>
          api.recordExpense({
            category: value(formData, 'category'),
            description: value(formData, 'description'),
            amount: numberValue(formData, 'amount'),
            payment_date: value(formData, 'payment_date'),
            payment_method: optional(formData, 'payment_method'),
          }),
        'Expense recorded in the ledger.',
      )
      return

    case 'partner-investment-form':
      await runAction(
        async () =>
          api.createPartnerInvestment({
            partner_name: value(formData, 'partner_name'),
            investment_date: value(formData, 'investment_date'),
            investment_time_period: optional(formData, 'investment_time_period'),
            share_of_partner: numberValue(formData, 'share_of_partner'),
            investment_amount: numberValue(formData, 'investment_amount'),
            mode: value(formData, 'mode'),
            investment_type: value(formData, 'investment_type'),
          }),
        'Partner investment recorded and posted to the ledger.',
      )
      return
  }
})

render()
registerPwa()
void loadAllData()
