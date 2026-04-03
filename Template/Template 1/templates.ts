import type { AppState, Client, Company, Employee, Project, Quotation, Section } from './types'

const sectionLabels: Record<Section, string> = {
  dashboard: 'Overview',
  crm: 'CRM',
  sales: 'Sales',
  projects: 'Projects',
  hrm: 'HRM',
  accounting: 'Accounting',
  investment: 'Investment',
}

function escapeHtml(value: string | number | null | undefined): string {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function currency(value: number | undefined): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(value ?? 0)
}

function dateLabel(value: string | null | undefined): string {
  if (!value) return 'Not set'
  return new Date(value).toLocaleDateString()
}

function chipTone(value: string): 'good' | 'active' | 'muted' | 'alert' {
  return (
    /paid|approved|completed|client/i.test(value) ? 'good' :
    /overdue|blocked|reject|not interested/i.test(value) ? 'alert' :
    /progress|lead|discussion|partial|planning|connected|interested|quotation|negotiation/i.test(value) ? 'active' :
    'muted'
  )
}

function chip(value: string): string {
  const tone = chipTone(value)
  return `<span class="status-chip" data-tone="${tone}">${escapeHtml(value)}</span>`
}

function phoneHref(value: string | null | undefined): string {
  const rawValue = String(value ?? '').trim()
  if (!rawValue) return ''
  const normalized = rawValue.replace(/[^0-9+]/g, '')
  return `tel:${normalized || rawValue}`
}

const crmOutreachMailSubject = 'Helping Your Business Run Smarter with the Right Systems'
const titanMailComposeBaseUrl = 'https://app.titan.email/mail/'

function crmOutreachMailBody(contactName: string | null | undefined): string {
  const salutationName = String(contactName ?? '').trim() || 'there'
  return `Dear ${salutationName},

Many growing businesses struggle with scattered processes, manual work, and lack of operational visibility. At Zappizo, we help companies solve this by designing structured systems that bring sales, operations, and data into one streamlined workflow.

We work closely with businesses to understand how they operate and implement customized ERP and business solutions that improve efficiency, clarity, and scalability.

If improving operational efficiency or building better internal systems is something you are exploring, I would be happy to schedule a short call to understand your requirements and see if we can help.

Would you be available for a brief 15-minute conversation this week?

Best regards,`
}

function crmOutreachMailTo(value: string | null | undefined, contactName: string | null | undefined): string {
  const rawValue = String(value ?? '').trim()
  if (!rawValue) return ''
  const subject = encodeURIComponent(crmOutreachMailSubject)
  const body = encodeURIComponent(crmOutreachMailBody(contactName))
  return `mailto:${rawValue}?subject=${subject}&body=${body}`
}

function titanComposeHref(mailTo: string): string {
  const actions = encodeURIComponent(JSON.stringify([{ action: 'compose', params: { mailTo } }]))
  return `${titanMailComposeBaseUrl}?actions=${actions}`
}

function emailHref(value: string | null | undefined, contactName: string | null | undefined): string {
  const mailTo = crmOutreachMailTo(value, contactName)
  if (!mailTo) return ''
  return titanComposeHref(mailTo)
}

function options(items: Array<{ value: string; label: string }>, selected = ''): string {
  return items
    .map(
      ({ value, label }) =>
        `<option value="${escapeHtml(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(label)}</option>`,
    )
    .join('')
}

type CompanyContactInfo = {
  full_name?: string | null
  email?: string | null
  phone?: string | null
  is_primary?: boolean
}

function normalizeSearchText(value: string | number | null | undefined): string {
  return String(value ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9\s]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function companyContacts(company: Company | undefined): CompanyContactInfo[] {
  if (!company) {
    return []
  }

  if (company.contacts?.length) {
    return company.contacts
  }

  if (company.contact_person || company.email || company.phone) {
    return [
      {
        full_name: company.contact_person,
        email: company.email,
        phone: company.phone,
        is_primary: true,
      },
    ]
  }

  return []
}

function primaryCompanyContact(company: Company | undefined): CompanyContactInfo | null {
  const contacts = companyContacts(company)
  return contacts.find((contact) => contact.is_primary) ?? contacts[0] ?? null
}

function contactPhoneLink(phone: string | null | undefined): string {
  const rawValue = String(phone ?? '').trim()
  if (!rawValue) return 'Not set'
  return `<a class="crm-contact-link" href="${escapeHtml(phoneHref(rawValue))}">${escapeHtml(rawValue)}</a>`
}

function websiteHref(value: string | null | undefined): string {
  const rawValue = String(value ?? '').trim()
  if (!rawValue) return ''
  return /^https?:\/\//i.test(rawValue) ? rawValue : `https://${rawValue}`
}

function websiteLink(value: string | null | undefined, fallback = 'Optional'): string {
  const rawValue = String(value ?? '').trim()
  if (!rawValue) return fallback
  return `<a class="crm-contact-link" href="${escapeHtml(websiteHref(rawValue))}" target="_blank" rel="noopener noreferrer">${escapeHtml(rawValue)}</a>`
}

function contactEmailLink(email: string | null | undefined, contactName: string | null | undefined): string {
  const rawValue = String(email ?? '').trim()
  if (!rawValue) return 'Not set'
  return `<a class="crm-contact-link" href="${escapeHtml(emailHref(rawValue, contactName))}" target="_blank" rel="noopener noreferrer">${escapeHtml(rawValue)}</a>`
}

function companyContactStack(
  company: Company | undefined,
  renderLine: (contact: CompanyContactInfo) => string,
  fallback: string,
): string {
  const contacts = companyContacts(company)
  if (!contacts.length) {
    return fallback
  }

  return `
    <div class="company-contact-stack">
      ${contacts.map((contact) => `<div class="company-contact-line">${renderLine(contact)}</div>`).join('')}
    </div>
  `
}

function companyStatusOptions(selected = 'Interested', companyId = ''): string {
  return ['Connected', 'Not Connected', 'Interested', 'Follow Up']
    .map((value) => {
      const activeClass = value === selected ? ' is-active' : ''
      return `
        <button
          type="button"
          class="quotation-status-option${activeClass}"
          data-tone="${companyStatusTone(value)}"
          data-crm-company-status-option="${escapeHtml(companyId)}"
          data-crm-company-status-value="${escapeHtml(value)}"
        >
          <span class="quotation-status-dot" aria-hidden="true"></span>
          <span>${escapeHtml(value)}</span>
        </button>
      `
    })
    .join('')
}

function companyStatusTone(value: string): 'good' | 'active' | 'muted' | 'alert' {
  return (
    /^connected$/i.test(value) ? 'good' :
    /^interested$/i.test(value) ? 'active' :
    /^not connected$/i.test(value) ? 'alert' :
    'muted'
  )
}

function companyStatusAction(company: Company, openCompanyStatusId: string | null): string {
  const statusMenuOpen = openCompanyStatusId === company.id
  return `
    <div class="quotation-status-shell" data-crm-company-status-shell="${escapeHtml(company.id)}">
      <button
        type="button"
        class="quotation-status-editor"
        data-tone="${companyStatusTone(company.status)}"
        data-crm-company-status-toggle="${escapeHtml(company.id)}"
        aria-haspopup="true"
        aria-expanded="${statusMenuOpen ? 'true' : 'false'}"
        aria-label="Edit company status"
      >
        <span class="quotation-status-dot" aria-hidden="true"></span>
        <span class="quotation-status-label">${escapeHtml(company.status)}</span>
        <span class="quotation-status-caret" aria-hidden="true"></span>
      </button>
      ${statusMenuOpen ? `<div class="quotation-status-menu">${companyStatusOptions(company.status, company.id)}</div>` : ''}
    </div>
  `
}

function companyContactFormRow(index: number): string {
  const removeLabel = index === 0 ? 'Primary contact' : 'Additional contact'
  return `
    <article class="crm-contact-card" data-company-contact-row="true">
      <div class="crm-contact-card-head">
        <div>
          <p class="eyebrow">${escapeHtml(removeLabel)}</p>
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

function companyName(companyId: string, companies: Company[]): string {
  return companies.find((company) => company.id === companyId)?.name ?? 'Unknown company'
}

function quotationMailHref(
  quotation: Quotation,
  client: Client | undefined,
  company: Company | undefined,
  contactName: string | null | undefined,
  recipientEmail: string | null | undefined,
): string {
  const rawValue = String(recipientEmail ?? '').trim()
  if (!rawValue) return ''
  const salutationName = String(contactName ?? '').trim() || 'there'
  const subject = encodeURIComponent(`Quotation ${quotation.quotation_number} from Zappizo`)
  const body = encodeURIComponent(`Dear ${salutationName},

Please find the quotation details below for your review.

Quotation Number: ${quotation.quotation_number}
Company: ${company?.name ?? 'Unknown company'}
Client Code: ${client?.client_code ?? 'Unavailable'}
Service Description: ${quotation.service_description}
Scope of Work: ${quotation.scope_of_work ?? 'Not specified'}
Unit Price: ${currency(quotation.unit_price)}
Taxes: ${currency(quotation.taxes)}
Total Amount: ${currency(quotation.total_amount)}
Validity Until: ${dateLabel(quotation.validity_period_end)}
Created On: ${dateLabel(quotation.created_at)}

Please let us know if you would like any clarification or revisions.

Best regards,`)
  return titanComposeHref(`mailto:${rawValue}?subject=${subject}&body=${body}`)
}

function matchesColumnFilter(value: string | number | null | undefined, filter: string): boolean {
  const normalizedFilter = normalizeSearchText(filter)
  if (!normalizedFilter) return true
  return normalizeSearchText(value).includes(normalizedFilter)
}

function clientLabel(clientId: string, clients: Client[], companies: Company[]): string {
  const client = clients.find((item) => item.id === clientId)
  if (!client) return 'Unknown client'
  return `${companyName(client.company_id, companies)} (${client.client_code})`
}

function employeeName(employeeId: string | null | undefined, employees: Employee[]): string {
  if (!employeeId) return 'Unassigned'
  return employees.find((employee) => employee.id === employeeId)?.name ?? 'Unknown employee'
}

function projectLabel(projectId: string, projects: Project[]): string {
  const project = projects.find((item) => item.id === projectId)
  return project ? `${project.project_title} (${project.project_code})` : 'Unknown project'
}

function rowExportButtons(label: string): string {
  return `
    <button type="button" class="ghost-button" data-export-row="excel" data-export-label="${escapeHtml(label)}">Excel</button>
    <button type="button" class="ghost-button" data-export-row="pdf" data-export-label="${escapeHtml(label)}">PDF</button>
  `
}

function iconButton(label: string, icon: string, attributes: string): string {
  return `
    <button type="button" class="ghost-button icon-action-button" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}" ${attributes}>
      ${icon}
    </button>
  `
}

function proposalRowActionButtons(label: string, quotationId: string, quotationMail: string | null): string {
  const excelButton = iconButton(
    `${label} export excel`,
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zm0 0v5h5M9 10l6 8M15 10l-6 8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    `data-export-row="excel" data-export-label="${escapeHtml(label)}"`,
  )
  const pdfButton = iconButton(
    `${label} export pdf`,
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm7 0v5h5M8.5 15h2a1.5 1.5 0 0 0 0-3h-2zm0 0v3m5-3h2m-2 1.5h1.5m-1.5 1.5h2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    `data-export-row="pdf" data-export-label="${escapeHtml(label)}"`,
  )
  const sendButton = quotationMail
    ? iconButton(
        `${label} send quotation`,
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 12 15-7-4 14-3-5-8-2Zm8 2 7-9" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        `data-sales-quotation-send="${escapeHtml(quotationId)}" data-sales-quotation-href="${escapeHtml(quotationMail)}"`,
      )
    : '<span class="cell-sub">No email available</span>'
  const viewButton = iconButton(
    `${label} view details`,
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Zm9.5 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    `data-sales-quotation-view="${escapeHtml(quotationId)}"`,
  )

  return `${excelButton}${pdfButton}${sendButton}${viewButton}`
}

function companyRowActionButtons(company: Company): string {
  const rowLabel = `${company.name} company`
  const excelButton = iconButton(
    `${rowLabel} export excel`,
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zm0 0v5h5M9 10l6 8M15 10l-6 8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    `data-export-row="excel" data-export-label="${escapeHtml(rowLabel)}"`,
  )
  const pdfButton = iconButton(
    `${rowLabel} export pdf`,
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm7 0v5h5M8.5 15h2a1.5 1.5 0 0 0 0-3h-2zm0 0v3m5-3h2m-2 1.5h1.5m-1.5 1.5h2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    `data-export-row="pdf" data-export-label="${escapeHtml(rowLabel)}"`,
  )
  const viewButton = iconButton(
    `${company.name} view details`,
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Zm9.5 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    `data-company-action="view" data-company-id="${escapeHtml(company.id)}"`,
  )
  return `${excelButton}${pdfButton}${viewButton}`
}

function gstOptions(selected = '18'): string {
  return options(
    [
      { value: '18', label: '18% GST' },
      { value: '0', label: '0% GST' },
    ],
    selected,
  )
}

function quotationStatusOptions(selected = 'Draft', quotationId = ''): string {
  return ['Draft', 'Sent', 'Approved', 'Negotiation', 'Reject']
    .map((value) => {
      const activeClass = value === selected ? ' is-active' : ''
      return `
        <button
          type="button"
          class="quotation-status-option${activeClass}"
          data-tone="${chipTone(value)}"
          data-sales-quotation-status-option="${escapeHtml(quotationId)}"
          data-sales-quotation-status-value="${escapeHtml(value)}"
        >
          <span class="quotation-status-dot" aria-hidden="true"></span>
          <span>${escapeHtml(value)}</span>
        </button>
      `
    })
    .join('')
}

type ModuleHighlight = {
  label: string
  value: string | number
  tone: 'good' | 'active' | 'muted' | 'alert'
}

type ModuleStageButton = {
  id: string
  label: string
  detail: string
  meta: string
}

function moduleHighlightCards(items: ModuleHighlight[]): string {
  return items
    .map(
      (item) => `
        <article class="crm-stat-card" data-tone="${item.tone}">
          <span>${escapeHtml(item.label)}</span>
          <strong>${escapeHtml(item.value)}</strong>
        </article>
      `,
    )
    .join('')
}

function moduleHero(
  eyebrow: string,
  title: string,
  copy: string,
  pill: string,
  highlights: ModuleHighlight[],
): string {
  return `
    <article class="panel crm-hero-panel">
      <div class="crm-stage-header">
        <div>
          <p class="eyebrow">${escapeHtml(eyebrow)}</p>
          <h3>${escapeHtml(title)}</h3>
          <p class="hero-copy">${escapeHtml(copy)}</p>
        </div>
        <span class="crm-stage-pill">${escapeHtml(pill)}</span>
      </div>
      <div class="crm-summary-grid crm-summary-grid-wide">${moduleHighlightCards(highlights)}</div>
    </article>
  `
}

function moduleStage(eyebrow: string, title: string, copy: string, pill: string, content: string): string {
  return `
    <section class="crm-stage-card">
      <div class="crm-stage-header">
        <div>
          <p class="eyebrow">${escapeHtml(eyebrow)}</p>
          <h3>${escapeHtml(title)}</h3>
          <p class="hero-copy">${escapeHtml(copy)}</p>
        </div>
        <span class="crm-stage-pill">${escapeHtml(pill)}</span>
      </div>
      ${content}
    </section>
  `
}

function moduleStageStrip(buttons: ModuleStageButton[], activeId: string | null, dataAttribute: string): string {
  return `
    <div class="crm-strip">
      ${buttons
        .map(
          (section) => `
            <button
              type="button"
              class="crm-section-bar ${activeId === section.id ? 'is-active' : ''}"
              ${dataAttribute}="${escapeHtml(section.id)}"
            >
              <span class="crm-section-topline">
                <span class="crm-section-meta">${escapeHtml(section.meta)}</span>
                <span class="crm-section-arrow" aria-hidden="true"></span>
              </span>
              <span class="crm-section-label">${escapeHtml(section.label)}</span>
              <span class="crm-section-detail">${escapeHtml(section.detail)}</span>
            </button>
          `,
        )
        .join('')}
    </div>
  `
}

function nav(state: AppState): string {
  return (Object.keys(sectionLabels) as Section[])
    .map(
      (section) => `
        <button class="nav-link ${state.activeSection === section ? 'is-active' : ''}" data-view="${section}">
          <span>${sectionLabels[section]}</span>
        </button>
      `,
    )
    .join('')
}

function overview(state: AppState): string {
  const counts = state.dashboard?.counts ?? {}
  const pipelineCards = Object.entries(state.dashboard?.pipeline ?? {})
    .map(([label, count]) => `<div class="mini-card"><span>${escapeHtml(label)}</span><strong>${count}</strong></div>`)
    .join('')
  const invoiceCards = Object.entries(state.dashboard?.invoice_status ?? {})
    .map(([label, count]) => `<div class="mini-card"><span>${escapeHtml(label)}</span><strong>${count}</strong></div>`)
    .join('')
  const timelineEntries = state.events.length ? state.events : (state.dashboard?.recent_events ?? [])
  const eventItems = timelineEntries
    .map(
      (event) => `
        <li class="timeline-item">
          <div class="timeline-meta">${escapeHtml(event.module)} | ${new Date(event.created_at).toLocaleString()}</div>
          <strong>${escapeHtml(event.action)}</strong>
          <p>${escapeHtml(event.description)}</p>
        </li>
      `,
    )
    .join('')

  const overviewHighlights: ModuleHighlight[] = [
    { label: 'Companies', value: counts.companies ?? 0, tone: 'active' },
    { label: 'Clients', value: counts.clients ?? 0, tone: 'good' },
    { label: 'Projects', value: counts.projects ?? 0, tone: 'active' },
    { label: 'Revenue', value: currency(counts.revenue), tone: 'good' },
  ]

  return `
    <section class="crm-shell">
      ${moduleHero(
        'Overview',
        'Executive Snapshot',
        'Athena keeps commercial, delivery, workforce, and accounting activity in one traceable operating picture.',
        `${timelineEntries.length} recent events`,
        overviewHighlights,
      )}
      ${moduleStage(
        'Stage one',
        'Operational Pulse',
        'Read the immediate health of pipeline and finance activity without leaving the shared dashboard.',
        `${state.companies.length} shared companies`,
        `
          <div class="module-grid crm-section-grid crm-split-grid">
            <article class="panel crm-panel-card">
              <div class="crm-panel-copy">
                <p class="eyebrow">Commercial flow</p>
                <div class="panel-head"><h2>Pipeline Snapshot</h2><span>${state.companies.length} shared companies</span></div>
              </div>
              <div class="mini-grid">${pipelineCards || '<p class="empty">No CRM activity yet.</p>'}</div>
            </article>
            <article class="panel crm-panel-card">
              <div class="crm-panel-copy">
                <p class="eyebrow">Billing visibility</p>
                <div class="panel-head"><h2>Invoice Health</h2><span>${state.invoices.length} invoices</span></div>
              </div>
              <div class="mini-grid">${invoiceCards || '<p class="empty">No invoices yet.</p>'}</div>
            </article>
          </div>
        `,
      )}
      ${moduleStage(
        'Stage two',
        'Workflow Feed',
        'Follow the exact sequence of cross-module actions that changed the state of the business.',
        `${timelineEntries.length} tracked events`,
        `
          <article class="panel crm-panel-card">
            <div class="crm-panel-copy">
              <p class="eyebrow">Traceability</p>
              <div class="panel-head"><h2>Recent Workflow Events</h2><span>Cross-module activity stream</span></div>
            </div>
            <ol class="timeline">${eventItems || '<p class="empty">Workflow events will appear here after activity.</p>'}</ol>
          </article>
        `,
      )}
    </section>
  `
}

function crm(state: AppState): string {
  const companyImportFormatReference = [
    'Company Name',
    'Website',
    'Industry',
    'Company Address',
    'Contact Person',
    'Email ID of Contact Person',
    'Phone Number',
  ].join(' | ')
  const existingCustomerRecords = state.existingCustomers
  const crmSectionButtons = [
    {
      id: 'create-company',
      label: 'Create Company Database',
      detail: 'Manual entry and CSV upload',
      meta: `${state.companies.length} records`,
    },
    {
      id: 'company-list',
      label: 'Company List',
      detail: 'Search, inspect, and revise status',
      meta: `${state.companies.length} companies`,
    },
    {
      id: 'caller-workspace',
      label: 'Caller Workspace',
      detail: 'Calls and lead updates in one flow',
      meta: `${state.leads.length} active leads`,
    },
    {
      id: 'lead-register',
      label: 'Lead Register',
      detail: 'Pipeline visibility for qualified discussions',
      meta: `${state.leads.filter((lead) => lead.status === 'Potential Client').length} potential clients`,
    },
    {
      id: 'existing-customers',
      label: 'Existing Customers',
      detail: 'CRM accounts backed by confirmed sales orders',
      meta: `${existingCustomerRecords.length} customers`,
    },
  ]
  const activeSection = crmSectionButtons.find((section) => section.id === state.crmOpenSection)
  const connectedCompanies = state.companies.filter((company) => company.status === 'Connected').length
  const interestedCompanies = state.companies.filter((company) => company.status === 'Interested').length
  const followUpCompanies = state.companies.filter((company) => company.status === 'Follow Up').length
  const potentialClients = state.leads.filter((lead) => lead.status === 'Potential Client').length
  const existingCustomers = existingCustomerRecords.length
  const crmHighlights = [
    { label: 'Connected', value: connectedCompanies, tone: 'active' },
    { label: 'Interested', value: interestedCompanies, tone: 'good' },
    { label: 'Follow Up', value: followUpCompanies, tone: 'muted' },
    { label: 'Potential Clients', value: potentialClients, tone: 'good' },
    { label: 'Existing Customers', value: existingCustomers, tone: 'active' },
  ]

  const filteredCompanies = state.companies.filter((company) => {
    const primaryContact = primaryCompanyContact(company)
    return (
      matchesColumnFilter(company.name, state.crmCompanyColumnFilters.name) &&
      matchesColumnFilter(primaryContact?.full_name, state.crmCompanyColumnFilters.contact) &&
      matchesColumnFilter(primaryContact?.email, state.crmCompanyColumnFilters.email) &&
      matchesColumnFilter(primaryContact?.phone, state.crmCompanyColumnFilters.phone) &&
      matchesColumnFilter(company.website, state.crmCompanyColumnFilters.website) &&
      matchesColumnFilter(company.industry, state.crmCompanyColumnFilters.industry) &&
      matchesColumnFilter(company.location, state.crmCompanyColumnFilters.location) &&
      (!state.crmCompanyStatusFilter || company.status === state.crmCompanyStatusFilter)
    )
  })
  const filteredLeads = state.leads.filter((lead) => {
    const company = state.companies.find((item) => item.id === lead.company_id)
    const primaryContact = primaryCompanyContact(company)
    return (
      matchesColumnFilter(company?.name, state.crmLeadColumnFilters.company) &&
      matchesColumnFilter(primaryContact?.full_name, state.crmLeadColumnFilters.contact) &&
      matchesColumnFilter(lead.requirement_summary, state.crmLeadColumnFilters.requirement) &&
      matchesColumnFilter(lead.estimated_budget, state.crmLeadColumnFilters.budget) &&
      (!state.crmLeadStatusFilter || lead.status === state.crmLeadStatusFilter)
    )
  })
  const callerLeads = state.leads
  const companyStatusFilterOptions = options(
    [
      { value: '', label: 'All' },
      ...['Connected', 'Not Connected', 'Interested', 'Follow Up'].map((value) => ({ value, label: value })),
    ],
    state.crmCompanyStatusFilter,
  )
  const leadStatusFilterOptions = options(
    [
      { value: '', label: 'All' },
      ...['Interested', 'Not Interested', 'Potential Client', 'Follow Up', 'Quotation Sent', 'Open'].map((value) => ({ value, label: value })),
    ],
    state.crmLeadStatusFilter,
  )
  const callerSelectableCompanies = state.companies
  const selectedCallerCompany =
    (state.crmCallerSelectedCompanyId ?
      callerSelectableCompanies.find((company) => company.id === state.crmCallerSelectedCompanyId) :
      null) ??
    (state.crmCallerSelectedLeadId ?
      callerSelectableCompanies.find(
        (company) => company.id === callerLeads.find((lead) => lead.id === state.crmCallerSelectedLeadId)?.company_id,
      ) :
      null) ??
    null
  const selectedCallerCompanyId = selectedCallerCompany?.id ?? ''
  const selectedCallerLead =
    (selectedCallerCompany ?
      callerLeads.find((lead) => lead.company_id === selectedCallerCompany.id) :
      null) ??
    (state.crmCallerSelectedLeadId ?
      callerLeads.find((lead) => lead.id === state.crmCallerSelectedLeadId) :
      null) ??
    null
  const selectedCallerLeadId = selectedCallerLead?.id ?? ''
  const selectedCallerContact = primaryCompanyContact(selectedCallerCompany ?? undefined)
  const leadEnrichmentNote =
    !selectedCallerCompany ?
      'Click a phone number in Company List to load the company here.' :
    selectedCallerLead ?
      'The selected company already has a lead record. Update the details and save changes.' :
      'No lead record exists for this company yet. Fill the details to create one.'

  const companyRows = filteredCompanies
    .map((company) => {
      const primaryContact = primaryCompanyContact(company)
      return `
        <tr class="crm-company-row" data-crm-company-row="${escapeHtml(company.id)}">
          <td><strong>${escapeHtml(company.name)}</strong></td>
          <td>
            <div class="proposal-contact-cell">
              <strong>${escapeHtml(primaryContact?.full_name ?? 'Not set')}</strong>
              <span class="cell-sub proposal-contact-email">${escapeHtml(primaryContact?.email ?? 'Not set')}</span>
            </div>
          </td>
          <td>${companyContactStack(company, (contact) => contactEmailLink(contact.email, contact.full_name), 'Not set')}</td>
          <td>${companyContactStack(company, (contact) => contactPhoneLink(contact.phone), 'Not set')}</td>
          <td>${websiteLink(company.website, 'Optional')}</td>
          <td>${escapeHtml(company.industry ?? 'Not set')}</td>
          <td>${escapeHtml(company.location ?? 'Not set')}</td>
          <td>${companyStatusAction(company, state.crmOpenCompanyStatusId)}</td>
          <td>
            <div class="action-row proposal-action-row">${companyRowActionButtons(company)}</div>
          </td>
        </tr>
      `
    })
    .join('')

  const leadRows = filteredLeads
    .map((lead) => {
      const company = state.companies.find((item) => item.id === lead.company_id)
      const primaryContact = primaryCompanyContact(company)
      return `
        <tr>
          <td>${escapeHtml(company?.name ?? 'Unknown company')}</td>
          <td>
            <div class="table-contact-cell">
              <strong>${escapeHtml(primaryContact?.full_name ?? 'Not set')}</strong>
              <div class="cell-sub">${contactEmailLink(primaryContact?.email, primaryContact?.full_name)}</div>
              <div class="cell-sub">${contactPhoneLink(primaryContact?.phone)}</div>
            </div>
          </td>
          <td>${escapeHtml(lead.requirement_summary ?? 'Requirement not captured')}</td>
          <td>${chip(lead.status)}</td>
          <td>${lead.estimated_budget ? currency(lead.estimated_budget) : 'TBD'}</td>
        </tr>
      `
    })
    .join('')
  const existingCustomerRows = existingCustomerRecords
    .map((customer) => {
      return `
        <tr>
          <td><strong>${escapeHtml(customer.client_code)}</strong></td>
          <td>${escapeHtml(customer.company_name)}</td>
          <td>
            <div class="table-contact-cell">
              <strong>${escapeHtml(customer.primary_contact_name ?? customer.relationship_manager ?? 'Not set')}</strong>
              <div class="cell-sub">${contactEmailLink(customer.billing_email ?? customer.primary_contact_email, customer.primary_contact_name ?? customer.relationship_manager)}</div>
              <div class="cell-sub">${contactPhoneLink(customer.primary_contact_phone)}</div>
            </div>
          </td>
          <td>${escapeHtml(customer.location ?? 'Not set')}</td>
          <td><strong>${escapeHtml(customer.sales_order_number)}</strong><div class="cell-sub">${escapeHtml(customer.quotation_number ?? 'Quotation unavailable')}</div></td>
          <td>${currency(customer.contract_value)}</td>
          <td>${chip(customer.sales_order_status)}</td>
          <td>${escapeHtml(dateLabel(customer.sales_order_created_at))}</td>
          <td>
            <div class="action-row table-action-row">
              <button type="button" class="ghost-button" data-sales-renew-company-id="${escapeHtml(customer.company_id)}">Renew validity</button>
              <button type="button" class="ghost-button" data-company-action="view" data-company-id="${escapeHtml(customer.company_id)}">View</button>
              <button type="button" class="ghost-button" data-company-action="edit" data-company-id="${escapeHtml(customer.company_id)}">Edit</button>
            </div>
          </td>
        </tr>
      `
    })
    .join('')

  let sectionContent = ''

  if (state.crmOpenSection === 'create-company') {
    sectionContent = `
      <section class="crm-stage-card">
        <div class="crm-stage-header">
          <div>
            <p class="eyebrow">Stage one</p>
            <h3>Create Company Database</h3>
            <p class="hero-copy">Capture clean source records before the caller team starts qualification.</p>
          </div>
          <span class="crm-stage-pill">Symmetric input workspace</span>
        </div>
        <div class="module-grid crm-section-grid crm-split-grid">
        <article class="panel crm-panel-card">
          <div class="crm-panel-copy">
            <p class="eyebrow">Manual entry</p>
            <div class="panel-head"><h2>Create Company</h2><span>Shared CRM source record</span></div>
          </div>
          <form id="company-form" class="card-form">
            <input name="name" placeholder="Company Name" required />
            <input name="website" placeholder="Website (Optional)" />
            <input name="industry" placeholder="Industry of the Company" required />
            <input name="location" placeholder="Company Address" />
            <div class="crm-contact-stack" data-company-contact-list="true">
              ${companyContactFormRow(0)}
            </div>
            <div class="crm-contact-toolbar">
              <p class="crm-search-caption">Add every contact person for this company. The first one remains the primary sales handoff contact.</p>
              <button type="button" class="ghost-button" data-add-company-contact="true">Add Another Contact</button>
            </div>
            <button type="submit">Create Company</button>
          </form>
        </article>
        <article class="panel crm-panel-card crm-panel-card-fit">
          <div class="crm-panel-copy">
            <p class="eyebrow">Bulk import</p>
            <div class="panel-head"><h2>CSV Upload Option</h2><span>Fill the company list automatically</span></div>
          </div>
          <form id="company-import-form" class="card-form">
            <input name="file" type="file" accept=".csv" required />
            <input name="mapping_json" type="hidden" value="" />
            <div class="crm-mapping-box" aria-label="CSV format reference">
              <p>${escapeHtml(companyImportFormatReference)}</p>
            </div>
            <button type="submit">Upload CSV</button>
          </form>
        </article>
        </div>
      </section>
    `
  }

  if (state.crmOpenSection === 'company-list') {
    sectionContent = `
      <section class="crm-stage-card">
        <div class="crm-stage-header">
          <div>
            <p class="eyebrow">Stage two</p>
            <h3>Company List</h3>
            <p class="hero-copy">Search the CRM database, inspect details instantly, and keep company status current.</p>
          </div>
          <span class="crm-stage-pill">${filteredCompanies.length} visible</span>
        </div>
      <article class="panel crm-panel-card crm-table-panel proposal-register-panel">
        <div class="crm-panel-copy">
          <div class="panel-head"><h2>Company List</h2><span>${filteredCompanies.length} matching records</span></div>
        </div>
        <div class="table-wrap proposal-register-wrap crm-company-register-wrap">
          <table class="crm-company-table proposal-register-table crm-company-register-table">
            <thead>
              <tr>
                <th>
                  <label class="crm-table-column-filter">
                    <span>Company Name</span>
                    <input class="crm-table-filter-input" type="search" placeholder="Filter" value="${escapeHtml(state.crmCompanyColumnFilters.name)}" data-company-column-filter="name" aria-label="Filter companies by name" />
                  </label>
                </th>
                <th>
                  <label class="crm-table-column-filter">
                    <span>Contact Person</span>
                    <input class="crm-table-filter-input" type="search" placeholder="Filter" value="${escapeHtml(state.crmCompanyColumnFilters.contact)}" data-company-column-filter="contact" aria-label="Filter companies by contact person" />
                  </label>
                </th>
                <th>
                  <label class="crm-table-column-filter">
                    <span>Email ID</span>
                    <input class="crm-table-filter-input" type="search" placeholder="Filter" value="${escapeHtml(state.crmCompanyColumnFilters.email)}" data-company-column-filter="email" aria-label="Filter companies by email" />
                  </label>
                </th>
                <th>
                  <label class="crm-table-column-filter">
                    <span>Phone Number</span>
                    <input class="crm-table-filter-input" type="search" placeholder="Filter" value="${escapeHtml(state.crmCompanyColumnFilters.phone)}" data-company-column-filter="phone" aria-label="Filter companies by phone number" />
                  </label>
                </th>
                <th>
                  <label class="crm-table-column-filter">
                    <span>Website</span>
                    <input class="crm-table-filter-input" type="search" placeholder="Filter" value="${escapeHtml(state.crmCompanyColumnFilters.website)}" data-company-column-filter="website" aria-label="Filter companies by website" />
                  </label>
                </th>
                <th>
                  <label class="crm-table-column-filter">
                    <span>Industry</span>
                    <input class="crm-table-filter-input" type="search" placeholder="Filter" value="${escapeHtml(state.crmCompanyColumnFilters.industry)}" data-company-column-filter="industry" aria-label="Filter companies by industry" />
                  </label>
                </th>
                <th>
                  <label class="crm-table-column-filter">
                    <span>Company Address</span>
                    <input class="crm-table-filter-input" type="search" placeholder="Filter" value="${escapeHtml(state.crmCompanyColumnFilters.location)}" data-company-column-filter="location" aria-label="Filter companies by address" />
                  </label>
                </th>
                <th>
                  <label class="crm-table-column-filter">
                    <span>Status</span>
                    <select class="crm-table-filter-select" data-company-status-filter="true" aria-label="Filter companies by status">
                      ${companyStatusFilterOptions}
                    </select>
                  </label>
                </th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>${companyRows || '<tr><td colspan="9">No companies found.</td></tr>'}</tbody>
          </table>
        </div>
      </article>
      </section>
    `
  }

  if (state.crmOpenSection === 'caller-workspace') {
    sectionContent = `
      <section class="crm-stage-card">
        <div class="crm-stage-header">
          <div>
            <p class="eyebrow">Stage three</p>
            <h3>Caller Workspace</h3>
            <p class="hero-copy">Capture lead context directly from one full-width enrichment workspace.</p>
          </div>
          <span class="crm-stage-pill">${selectedCallerLead ? 'Existing lead record' : 'New lead creation ready'}</span>
        </div>
        <article class="panel crm-panel-card">
          <div class="crm-panel-copy">
            <p class="eyebrow">Lead enrichment</p>
            <div class="panel-head"><h2>Lead Enrichment Workspace</h2><span>Click from Company List loads this workspace</span></div>
          </div>
          <form id="lead-form" class="card-form">
            <input type="hidden" name="company_id" value="${escapeHtml(selectedCallerCompanyId)}" />
            <input value="${escapeHtml(selectedCallerCompany?.name ?? '')}" placeholder="Company Name" readonly aria-label="Lead enrichment company" />
            <input value="${escapeHtml(selectedCallerContact?.full_name ?? '')}" placeholder="Contact Person" readonly aria-label="Lead enrichment contact" />
            <input value="${escapeHtml(selectedCallerContact?.email ?? '')}" placeholder="Email ID" readonly aria-label="Lead enrichment email" />
            <input value="${escapeHtml(selectedCallerContact?.phone ?? '')}" placeholder="Phone Number" readonly aria-label="Lead enrichment phone" />
            <input type="hidden" name="lead_id" value="${escapeHtml(selectedCallerLeadId)}" />
            <p class="crm-form-caption">${escapeHtml(leadEnrichmentNote)}</p>
            <textarea name="requirement_summary" rows="2" placeholder="Requirement summary" data-lead-focus="true">${escapeHtml(selectedCallerLead?.requirement_summary ?? '')}</textarea>
            <textarea name="discussion_notes" rows="2" placeholder="Discussion notes">${escapeHtml(selectedCallerLead?.discussion_notes ?? '')}</textarea>
            <textarea name="estimated_scope" rows="2" placeholder="Estimated scope">${escapeHtml(selectedCallerLead?.estimated_scope ?? '')}</textarea>
            <input name="estimated_budget" type="number" min="0" step="0.01" placeholder="Estimated budget" value="${escapeHtml(selectedCallerLead?.estimated_budget ?? '')}" />
            <select name="status">${options(['Interested', 'Not Interested', 'Follow Up', 'Potential Client'].map((value) => ({ value, label: value })), ['Interested', 'Not Interested', 'Follow Up', 'Potential Client'].includes(selectedCallerLead?.status ?? '') ? (selectedCallerLead?.status ?? 'Potential Client') : 'Potential Client')}</select>
            <button type="submit" ${selectedCallerCompany ? '' : 'disabled'}>${selectedCallerLead ? 'Update Lead' : 'Create Lead'}</button>
          </form>
        </article>
      </section>
    `
  }

  if (state.crmOpenSection === 'lead-register') {
    sectionContent = `
      <section class="crm-stage-card">
        <div class="crm-stage-header">
          <div>
            <p class="eyebrow">Stage four</p>
            <h3>Lead Register</h3>
            <p class="hero-copy">Monitor qualified discussions and surface the next potential clients for sales follow-through.</p>
          </div>
          <span class="crm-stage-pill">${filteredLeads.length} visible</span>
        </div>
      <article class="panel crm-panel-card crm-table-panel">
        <div class="crm-panel-copy">
          <div class="panel-head"><h2>Lead Register</h2><span>${filteredLeads.length} matching leads</span></div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>
                  <label class="crm-table-column-filter">
                    <span>Company Name</span>
                    <input class="crm-table-filter-input" type="search" placeholder="Filter" value="${escapeHtml(state.crmLeadColumnFilters.company)}" data-lead-column-filter="company" aria-label="Filter leads by company name" />
                  </label>
                </th>
                <th>
                  <label class="crm-table-column-filter">
                    <span>Contact Person</span>
                    <input class="crm-table-filter-input" type="search" placeholder="Filter" value="${escapeHtml(state.crmLeadColumnFilters.contact)}" data-lead-column-filter="contact" aria-label="Filter leads by contact person" />
                  </label>
                </th>
                <th>
                  <label class="crm-table-column-filter">
                    <span>Requirement Summary</span>
                    <input class="crm-table-filter-input" type="search" placeholder="Filter" value="${escapeHtml(state.crmLeadColumnFilters.requirement)}" data-lead-column-filter="requirement" aria-label="Filter leads by requirement summary" />
                  </label>
                </th>
                <th>
                  <label class="crm-table-column-filter">
                    <span>Status</span>
                    <select class="crm-table-filter-select" data-lead-status-filter="true" aria-label="Filter leads by status">
                      ${leadStatusFilterOptions}
                    </select>
                  </label>
                </th>
                <th>
                  <label class="crm-table-column-filter">
                    <span>Estimated Budget</span>
                    <input class="crm-table-filter-input" type="search" placeholder="Filter" value="${escapeHtml(state.crmLeadColumnFilters.budget)}" data-lead-column-filter="budget" aria-label="Filter leads by estimated budget" />
                  </label>
                </th>
              </tr>
            </thead>
            <tbody>${leadRows || '<tr><td colspan="5">No leads found.</td></tr>'}</tbody>
          </table>
        </div>
      </article>
      </section>
    `
  }

  if (state.crmOpenSection === 'existing-customers') {
    sectionContent = `
      <section class="crm-stage-card">
        <div class="crm-stage-header">
          <div>
            <p class="eyebrow">Stage five</p>
            <h3>Existing Customers</h3>
            <p class="hero-copy">Review every customer backed by a live sales order and keep the CRM account editable.</p>
          </div>
          <span class="crm-stage-pill">${existingCustomers} customers</span>
        </div>
      <article class="panel crm-panel-card crm-table-panel">
        <div class="crm-panel-copy">
          <div class="panel-head"><h2>Existing Customers</h2><span>${existingCustomers} customers with sales orders</span></div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Customer Code</th>
                <th>Company Name</th>
                <th>Primary Contact</th>
                <th>Company Address</th>
                <th>Latest Sales Order</th>
                <th>Order Value</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>${existingCustomerRows || '<tr><td colspan="9">No existing customers yet.</td></tr>'}</tbody>
          </table>
        </div>
      </article>
      </section>
    `
  }

  return `
    <section class="crm-shell">
      <article class="panel crm-hero-panel">
        <div class="panel-head crm-hero-head">
          <h2>CRM Snapshot</h2>
          <span>Live pipeline counts</span>
        </div>
        <div class="crm-summary-scroll">
        <div class="crm-summary-grid crm-summary-grid-wide crm-summary-grid-inline" style="grid-template-columns: repeat(${crmHighlights.length}, minmax(160px, 1fr));">
          ${crmHighlights
            .map(
              (item) => `
                <article class="crm-stat-card" data-tone="${item.tone}">
                  <span>${escapeHtml(item.label)}</span>
                  <strong>${item.value}</strong>
                </article>
              `,
            )
            .join('')}
        </div>
        </div>
      </article>
      <div class="crm-strip">
        ${crmSectionButtons
          .map(
            (section) => `
              <button
                type="button"
                class="crm-section-bar ${state.crmOpenSection === section.id ? 'is-active' : ''}"
                data-crm-section="${section.id}"
              >
                <span class="crm-section-topline">
                  <span class="crm-section-meta">${escapeHtml(section.meta)}</span>
                  <span class="crm-section-arrow" aria-hidden="true"></span>
                </span>
                <span class="crm-section-label">${escapeHtml(section.label)}</span>
                <span class="crm-section-detail">${escapeHtml(section.detail)}</span>
              </button>
            `,
          )
          .join('')}
      </div>
      ${activeSection ? `<div class="crm-active-caption">Open stage: <strong>${escapeHtml(activeSection.label)}</strong></div>` : ''}
      ${sectionContent}
      ${crmModal(state)}
    </section>
  `
}

function crmModal(state: AppState): string {
  if (!state.crmModalCompanyId || !state.crmModalMode) {
    return ''
  }

  const company = state.companies.find((item) => item.id === state.crmModalCompanyId)
  if (!company) {
    return ''
  }
  const existingCustomer = state.existingCustomers.find((item) => item.company_id === company.id) ?? null

  if (state.crmModalMode === 'view') {
    return `
      <div class="modal-backdrop" data-crm-modal-backdrop="true">
        <div class="modal-card crm-modal-card" data-crm-modal-card="true">
          <p class="eyebrow">Company profile</p>
          <div class="panel-head crm-modal-head">
            <h2>${escapeHtml(company.name)}</h2>
            <div class="action-row crm-modal-actions">
              <button type="button" class="ghost-button" data-crm-modal-close="true">Close</button>
            </div>
          </div>
          <div class="detail-grid crm-modal-detail-grid">
            <p><strong>Company Name</strong><span>${escapeHtml(company.name)}</span></p>
            <p><strong>Primary Contact</strong><span>${escapeHtml(primaryCompanyContact(company)?.full_name ?? 'Not set')}</span></p>
            <p><strong>Primary Email ID</strong><span>${escapeHtml(primaryCompanyContact(company)?.email ?? 'Not set')}</span></p>
            <p><strong>Primary Phone Number</strong><span>${escapeHtml(primaryCompanyContact(company)?.phone ?? 'Not set')}</span></p>
            <p><strong>Website</strong><span>${websiteLink(company.website, 'Optional')}</span></p>
            <p><strong>Industry</strong><span>${escapeHtml(company.industry ?? 'Not set')}</span></p>
            <p><strong>Company Address</strong><span>${escapeHtml(company.location ?? 'Not set')}</span></p>
            <p><strong>Status</strong><span>${chip(company.status)}</span></p>
          </div>
          <div class="crm-contact-view">
            <div class="panel-head"><h3>Company Contacts</h3><span>${companyContacts(company).length} total</span></div>
            <div class="crm-contact-view-grid">
              ${
                companyContacts(company).length
                  ? companyContacts(company)
                      .map(
                        (contact) => `
                          <article class="crm-contact-view-card">
                            <strong>${escapeHtml(contact.full_name ?? 'Unnamed contact')}</strong>
                            <p>${escapeHtml(contact.email ?? 'Email not set')}</p>
                            <p>${escapeHtml(contact.phone ?? 'Phone not set')}</p>
                            ${contact.is_primary ? '<span class="status-chip" data-tone="good">Primary</span>' : ''}
                          </article>
                        `,
                      )
                      .join('')
                  : '<p class="empty">No contacts added yet.</p>'
              }
            </div>
          </div>
          ${
            existingCustomer ?
              `
                <div class="crm-contact-view">
                  <div class="panel-head"><h3>Commercial Snapshot</h3><span>${escapeHtml(existingCustomer.client_code)}</span></div>
                  <div class="detail-grid crm-modal-detail-grid">
                    <p><strong>Billing Email</strong><span>${escapeHtml(existingCustomer.billing_email ?? 'Not set')}</span></p>
                    <p><strong>Relationship Manager</strong><span>${escapeHtml(existingCustomer.relationship_manager ?? 'Not set')}</span></p>
                    <p><strong>Client Notes</strong><span>${escapeHtml(existingCustomer.client_notes ?? 'Not set')}</span></p>
                    <p><strong>Onboarded</strong><span>${escapeHtml(dateLabel(existingCustomer.onboarded_at))}</span></p>
                    <p><strong>Quotation</strong><span>${escapeHtml(existingCustomer.quotation_number ?? 'Not set')}</span></p>
                    <p><strong>Quotation Status</strong><span>${chip(existingCustomer.quotation_status ?? 'Not set')}</span></p>
                    <p><strong>Service Description</strong><span>${escapeHtml(existingCustomer.service_description ?? 'Not set')}</span></p>
                    <p><strong>Scope of Work</strong><span>${escapeHtml(existingCustomer.scope_of_work ?? 'Not set')}</span></p>
                    <p><strong>Unit Price</strong><span>${existingCustomer.unit_price != null ? currency(existingCustomer.unit_price) : 'Not set'}</span></p>
                    <p><strong>Taxes</strong><span>${existingCustomer.taxes != null ? currency(existingCustomer.taxes) : 'Not set'}</span></p>
                    <p><strong>Quotation Total</strong><span>${existingCustomer.quotation_total_amount != null ? currency(existingCustomer.quotation_total_amount) : 'Not set'}</span></p>
                    <p><strong>Validity</strong><span>${escapeHtml(dateLabel(existingCustomer.validity_period_end))}</span></p>
                    <p><strong>Sales Order</strong><span>${escapeHtml(existingCustomer.sales_order_number)}</span></p>
                    <p><strong>Order Status</strong><span>${chip(existingCustomer.sales_order_status)}</span></p>
                    <p><strong>Order Value</strong><span>${currency(existingCustomer.contract_value)}</span></p>
                    <p><strong>Payment Terms</strong><span>${escapeHtml(existingCustomer.payment_terms ?? 'Not set')}</span></p>
                    <p><strong>Delivery Timeline</strong><span>${escapeHtml(existingCustomer.delivery_timeline ?? 'Not set')}</span></p>
                    <p><strong>Order Created</strong><span>${escapeHtml(dateLabel(existingCustomer.sales_order_created_at))}</span></p>
                  </div>
                </div>
              ` :
              ''
          }
        </div>
      </div>
    `
  }

  return `
    <div class="modal-backdrop" data-crm-modal-backdrop="true">
      <div class="modal-card crm-modal-card" data-crm-modal-card="true">
        <p class="eyebrow">Status control</p>
        <div class="panel-head"><h2>Edit Company Status</h2><button type="button" class="ghost-button" data-crm-modal-close="true">Close</button></div>
        <form id="company-status-form" class="card-form">
          <input type="hidden" name="company_id" value="${company.id}" />
          <p><strong>${escapeHtml(company.name)}</strong></p>
          <select name="status">${options(['Connected', 'Not Connected', 'Interested', 'Follow Up'].map((value) => ({ value, label: value })), company.status)}</select>
          <button type="submit">Update Status</button>
        </form>
      </div>
    </div>
  `
}

function salesQuotationModal(state: AppState): string {
  if (!state.salesModalQuotationId) {
    return ''
  }

  const quotation = state.quotations.find((item) => item.id === state.salesModalQuotationId)
  if (!quotation) {
    return ''
  }

  const client = state.clients.find((item) => item.id === quotation.client_id) ?? null
  const company =
    state.companies.find((item) => item.id === quotation.company_id) ??
    state.companies.find((item) => item.id === client?.company_id) ??
    null
  const primaryContact = primaryCompanyContact(company ?? undefined)
  const order = state.orders.find((item) => item.quotation_id === quotation.id) ?? null
  const contactName = quotation.contact_name ?? primaryContact?.full_name ?? company?.contact_person ?? 'Not set'
  const contactEmail =
    quotation.contact_email ?? client?.billing_email ?? primaryContact?.email ?? company?.email ?? 'Not set'
  const contactPhone = quotation.contact_phone ?? primaryContact?.phone ?? company?.phone ?? 'Not set'
  const modalLabel = `${quotation.quotation_number} quotation`

  return `
    <div class="modal-backdrop" data-sales-modal-backdrop="true">
      <div class="modal-card crm-modal-card sales-modal-card" data-crm-modal-card="true" data-detail-modal-card="true">
        <p class="eyebrow">Proposal detail</p>
        <div class="panel-head sales-modal-head">
          <div>
            <h2>${escapeHtml(quotation.quotation_number)}</h2>
            <span>${escapeHtml(company?.name ?? 'Unknown company')}</span>
          </div>
          <div class="action-row">
            <button type="button" class="ghost-button" data-export-modal="excel" data-export-label="${escapeHtml(modalLabel)}">Export Excel</button>
            <button type="button" class="ghost-button" data-export-modal="pdf" data-export-label="${escapeHtml(modalLabel)}">Export PDF</button>
            <button type="button" class="ghost-button" data-sales-modal-close="true">Close</button>
          </div>
        </div>

        <div class="detail-grid sales-detail-grid">
          <p><strong>Quotation Number</strong><span>${escapeHtml(quotation.quotation_number)}</span></p>
          <p><strong>Client Code</strong><span>${escapeHtml(quotation.client_code ?? client?.client_code ?? 'Not set')}</span></p>
          <p><strong>Status</strong><span>${chip(quotation.status)}</span></p>
          <p><strong>Created On</strong><span>${escapeHtml(dateLabel(quotation.created_at))}</span></p>
          <p><strong>Valid Until</strong><span>${escapeHtml(dateLabel(quotation.validity_period_end))}</span></p>
          <p><strong>Company</strong><span>${escapeHtml(company?.name ?? 'Unknown company')}</span></p>
          <p><strong>Contact Person</strong><span>${escapeHtml(contactName)}</span></p>
          <p><strong>Email</strong><span>${escapeHtml(contactEmail)}</span></p>
          <p><strong>Phone</strong><span>${escapeHtml(contactPhone)}</span></p>
          <p><strong>Website</strong><span>${websiteLink(company?.website, 'Not set')}</span></p>
          <p><strong>Industry</strong><span>${escapeHtml(company?.industry ?? 'Not set')}</span></p>
          <p><strong>Company Address</strong><span>${escapeHtml(company?.location ?? 'Not set')}</span></p>
        </div>

        <div class="crm-contact-view sales-detail-section">
          <div class="panel-head"><h3>Commercial Scope</h3><span>${currency(quotation.total_amount)}</span></div>
          <div class="detail-grid sales-detail-grid">
            <p><strong>Service Description</strong><span>${escapeHtml(quotation.service_description)}</span></p>
            <p><strong>Unit Price</strong><span>${currency(quotation.unit_price)}</span></p>
            <p><strong>Taxes</strong><span>${currency(quotation.taxes)}</span></p>
            <p><strong>Total Amount</strong><span>${currency(quotation.total_amount)}</span></p>
          </div>
          <div class="sales-detail-block">
            <strong>Scope of Work</strong>
            <p>${escapeHtml(quotation.scope_of_work ?? 'Not specified')}</p>
          </div>
        </div>

        <div class="crm-contact-view sales-detail-section">
          <div class="panel-head"><h3>Linked Order</h3><span>${escapeHtml(order?.sales_order_number ?? 'Not created')}</span></div>
          <div class="detail-grid sales-detail-grid">
            <p><strong>Sales Order</strong><span>${escapeHtml(order?.sales_order_number ?? 'Not created')}</span></p>
            <p><strong>Order Status</strong><span>${order ? chip(order.status) : 'Not created'}</span></p>
            <p><strong>Contract Value</strong><span>${order ? currency(order.contract_value) : 'Not created'}</span></p>
            <p><strong>Payment Terms</strong><span>${escapeHtml(order?.payment_terms ?? 'Not set')}</span></p>
            <p><strong>Delivery Timeline</strong><span>${escapeHtml(order?.delivery_timeline ?? 'Not set')}</span></p>
            <p><strong>Order Created</strong><span>${escapeHtml(dateLabel(order?.created_at))}</span></p>
          </div>
        </div>
      </div>
    </div>
  `
}

function sales(state: AppState): string {
  const potentialLeadEntries = state.leads
    .filter((lead) => lead.status === 'Potential Client')
    .map((lead) => {
      const company = state.companies.find((item) => item.id === lead.company_id)
      const client = state.clients.find((item) => item.company_id === lead.company_id) ?? null
      const primaryContact = primaryCompanyContact(company)
      return { lead, company, client, primaryContact }
    })
    .filter(({ company }) => Boolean(company))
  const availableSalesCompanies = potentialLeadEntries
    .map((entry) => entry.company)
    .filter((company): company is Company => Boolean(company))
  const selectedQuoteCompanyId =
    state.salesQuotationCompanyId &&
    availableSalesCompanies.some((company) => company.id === state.salesQuotationCompanyId)
      ? state.salesQuotationCompanyId
      : (availableSalesCompanies[0]?.id ?? '')
  const selectedQuoteCompany =
    availableSalesCompanies.find((company) => company.id === selectedQuoteCompanyId) ?? null
  const selectedQuoteContact = primaryCompanyContact(selectedQuoteCompany ?? undefined)
  const quotationServicePreset = state.salesQuotationServicePreset ?? ''
  const approvedQuotations = state.quotations.filter((quotation) => /approved/i.test(quotation.status)).length

  const potentialClientRows = potentialLeadEntries
    .map(({ lead, company, client, primaryContact }) => {
      if (!company) {
        return ''
      }
      const isSelected = company.id === selectedQuoteCompanyId
      return `
        <tr
          class="${isSelected ? 'sales-pipeline-row is-selected' : 'sales-pipeline-row'}"
          data-sales-company-id="${escapeHtml(company.id)}"
        >
          <td>
            <button type="button" class="sales-pipeline-company-button" data-sales-company-id="${escapeHtml(company.id)}">
              <strong>${escapeHtml(company.name)}</strong>
              <div class="cell-sub">${escapeHtml(client?.client_code ?? 'Sales client will be created on quotation')}</div>
            </button>
          </td>
          <td>
            <strong>${escapeHtml(primaryContact?.full_name ?? company.contact_person ?? 'Not set')}</strong>
            <div class="cell-sub">${contactEmailLink(primaryContact?.email, primaryContact?.full_name)}</div>
            <div class="cell-sub">${contactPhoneLink(primaryContact?.phone)}</div>
          </td>
          <td>${escapeHtml(lead.requirement_summary ?? 'Requirement not captured')}</td>
          <td>${lead.estimated_budget ? currency(lead.estimated_budget) : 'TBD'}</td>
          <td>${chip(lead.status)}</td>
          <td>
            <div class="action-row table-action-row">
              <button type="button" class="ghost-button ${isSelected ? 'is-selected' : ''}" data-sales-company-id="${escapeHtml(company.id)}">
                ${isSelected ? 'Selected for quotation' : 'Create quotation'}
              </button>
            </div>
          </td>
        </tr>
      `
    })
    .join('')

  const quoteRows = state.quotations
    .map((quotation) => {
      const client = state.clients.find((item) => item.id === quotation.client_id)
      const company =
        state.companies.find((item) => item.id === quotation.company_id) ??
        state.companies.find((item) => item.id === client?.company_id)
      const primaryContact = primaryCompanyContact(company)
      const quotationMail = quotationMailHref(
        quotation,
        client,
        company,
        quotation.contact_name ?? primaryContact?.full_name,
        quotation.contact_email ?? client?.billing_email ?? primaryContact?.email ?? company?.email,
      )
      const companyName = quotation.company_name ?? company?.name ?? 'Unknown company'
      const contactName = quotation.contact_name ?? primaryContact?.full_name ?? company?.contact_person ?? 'Not set'
      const contactEmail =
        quotation.contact_email ?? client?.billing_email ?? primaryContact?.email ?? company?.email ?? 'No email'
      const clientCode = quotation.client_code ?? client?.client_code ?? 'Client code unavailable'
      const quotationStatusTone = chipTone(quotation.status)
      const statusMenuOpen = state.salesOpenQuotationStatusId === quotation.id
      const quotationStatusCell = `
        <div class="quotation-status-shell" data-sales-quotation-status-shell="${escapeHtml(quotation.id)}">
          <button
            type="button"
            class="quotation-status-editor"
            data-tone="${quotationStatusTone}"
            data-sales-quotation-status-toggle="${escapeHtml(quotation.id)}"
            aria-haspopup="true"
            aria-expanded="${statusMenuOpen ? 'true' : 'false'}"
            aria-label="Edit quotation status"
          >
            <span class="quotation-status-dot" aria-hidden="true"></span>
            <span class="quotation-status-label">${escapeHtml(quotation.status)}</span>
            <span class="quotation-status-caret" aria-hidden="true"></span>
          </button>
          ${
            statusMenuOpen ?
              `<div class="quotation-status-menu">${quotationStatusOptions(quotation.status, quotation.id)}</div>` :
              ''
          }
        </div>
      `

      return `
        <tr>
          <td><strong>${escapeHtml(quotation.quotation_number)}</strong><span class="cell-sub proposal-inline-meta">${escapeHtml(clientCode)}</span></td>
          <td>${escapeHtml(companyName)}</td>
          <td>
            <div class="proposal-contact-cell">
              <strong>${escapeHtml(contactName)}</strong>
              <span class="cell-sub proposal-contact-email">${escapeHtml(contactEmail)}</span>
            </div>
          </td>
          <td>${escapeHtml(quotation.service_description)}</td>
          <td>${escapeHtml(quotation.scope_of_work ?? 'Not specified')}</td>
          <td>${currency(quotation.unit_price)}</td>
          <td>${currency(quotation.taxes)}</td>
          <td>${quotationStatusCell}</td>
          <td>${currency(quotation.total_amount)}</td>
          <td>${escapeHtml(dateLabel(quotation.validity_period_end))}</td>
          <td>${escapeHtml(dateLabel(quotation.created_at))}</td>
          <td>
            <div class="action-row proposal-action-row">${proposalRowActionButtons(`${quotation.quotation_number} quotation`, quotation.id, quotationMail)}</div>
          </td>
        </tr>
      `
    })
    .join('')
  const orderRows = state.orders
    .map((order) => {
      const quotation = state.quotations.find((item) => item.id === order.quotation_id)
      const client = state.clients.find((item) => item.id === order.client_id)
      const company = state.companies.find((item) => item.id === client?.company_id)
      const primaryContact = primaryCompanyContact(company)
      return `
        <tr>
          <td><strong>${escapeHtml(order.sales_order_number)}</strong><div class="cell-sub">${escapeHtml(client?.client_code ?? 'Client code unavailable')}</div></td>
          <td>${escapeHtml(company?.name ?? 'Unknown company')}</td>
          <td>
            <div class="table-contact-cell">
              <strong>${escapeHtml(primaryContact?.full_name ?? company?.contact_person ?? 'Not set')}</strong>
              <div class="cell-sub">${escapeHtml(client?.billing_email ?? primaryContact?.email ?? company?.email ?? 'No email')}</div>
            </div>
          </td>
          <td><strong>${escapeHtml(quotation?.quotation_number ?? 'Linked quotation unavailable')}</strong><div class="cell-sub">${chip(quotation?.status ?? 'Quotation missing')}</div></td>
          <td>${escapeHtml(quotation?.service_description ?? order.services)}</td>
          <td>${escapeHtml(quotation?.scope_of_work ?? 'Not specified')}</td>
          <td>${currency(quotation?.unit_price)}</td>
          <td>${currency(quotation?.taxes)}</td>
          <td>${escapeHtml(dateLabel(quotation?.validity_period_end))}</td>
          <td>${escapeHtml(order.payment_terms ?? 'Not set')}</td>
          <td>${escapeHtml(order.delivery_timeline ?? 'Not set')}</td>
          <td>${chip(order.status)}</td>
          <td>${currency(order.contract_value)}</td>
          <td>${escapeHtml(dateLabel(order.created_at))}</td>
          <td>
            <div class="action-row table-action-row">
              ${rowExportButtons(`${order.sales_order_number} sales order`)}
            </div>
          </td>
        </tr>
      `
    })
    .join('')
  const salesHighlights: ModuleHighlight[] = [
    { label: 'Potential Clients', value: potentialLeadEntries.length, tone: 'good' },
    { label: 'Quotations', value: state.quotations.length, tone: 'active' },
    { label: 'Approved Quotes', value: approvedQuotations, tone: 'good' },
    { label: 'Sales Orders', value: state.orders.length, tone: 'active' },
  ]
  const salesSectionButtons: ModuleStageButton[] = [
    {
      id: 'pipeline',
      label: 'Client Conversion',
      detail: 'Potential clients and quotation workbench',
      meta: `${potentialLeadEntries.length} potential clients`,
    },
    {
      id: 'proposals',
      label: 'Proposal Register',
      detail: 'Quotation ledger and dispatch actions',
      meta: `${state.quotations.length} proposals`,
    },
    {
      id: 'orders',
      label: 'Order Handoff',
      detail: 'Approve quotations into project-ready sales orders',
      meta: `${state.orders.length} active orders`,
    },
    {
      id: 'register',
      label: 'Commercial Register',
      detail: 'Sales order register view',
      meta: `${state.orders.length} orders`,
    },
  ]
  const activeSalesSection = salesSectionButtons.find((section) => section.id === state.salesOpenSection)

  let salesSectionContent = ''

  if (state.salesOpenSection === 'pipeline') {
    salesSectionContent = moduleStage(
      'Stage one',
      'Client Conversion',
      'Turn qualified CRM companies into structured proposals without leaving the same control surface.',
      `${potentialLeadEntries.length} potential clients`,
      `
        <div class="module-grid crm-section-grid crm-split-grid">
          <article class="panel crm-panel-card crm-table-panel">
            <div class="crm-panel-copy">
              <p class="eyebrow">Pipeline</p>
              <div class="panel-head"><h2>Potential Clients</h2><span>Live CRM lead register entries with Potential Client status</span></div>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Contact</th>
                    <th>Requirement Summary</th>
                    <th>Estimated Budget</th>
                    <th>Status</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>${potentialClientRows || '<tr><td colspan="6">Potential clients will appear here after CRM qualification.</td></tr>'}</tbody>
              </table>
            </div>
          </article>
          <article class="panel crm-panel-card">
            <div class="crm-panel-copy">
              <p class="eyebrow">Proposal desk</p>
              <div class="panel-head"><h2>Quotation Desk</h2><span>Create and progress commercial proposals</span></div>
            </div>
            <form id="quotation-form" class="card-form">
              <input type="hidden" name="company_id" value="${escapeHtml(selectedQuoteCompanyId)}" />
              <div class="crm-contact-view sales-proposal-client-summary">
                <div class="panel-head sales-proposal-summary-head">
                  <div>
                    <h3>${escapeHtml(selectedQuoteCompany?.name ?? 'No client selected')}</h3>
                    <span class="sales-proposal-summary-contact">${escapeHtml(selectedQuoteContact?.full_name ?? selectedQuoteCompany?.contact_person ?? 'Select from pipeline')}</span>
                  </div>
                  <span class="crm-stage-pill">${selectedQuoteCompanyId ? 'Selected from pipeline' : 'Awaiting selection'}</span>
                </div>
                <div class="crm-contact-view-grid sales-proposal-summary-grid">
                  <article class="crm-contact-view-card sales-proposal-summary-card">
                    <strong>Primary Contact</strong>
                    <p>${escapeHtml(selectedQuoteContact?.full_name ?? selectedQuoteCompany?.contact_person ?? 'Not set')}</p>
                  </article>
                  <article class="crm-contact-view-card sales-proposal-summary-card">
                    <strong>Email</strong>
                    <p>
                      ${
                        selectedQuoteCompanyId ?
                          contactEmailLink(
                            selectedQuoteContact?.email ?? selectedQuoteCompany?.email,
                            selectedQuoteContact?.full_name ?? selectedQuoteCompany?.contact_person,
                          ) :
                          'Not set'
                      }
                    </p>
                  </article>
                  <article class="crm-contact-view-card sales-proposal-summary-card">
                    <strong>Phone</strong>
                    <p>
                      ${
                        selectedQuoteCompanyId ?
                          contactPhoneLink(selectedQuoteContact?.phone ?? selectedQuoteCompany?.phone) :
                          'Not set'
                      }
                    </p>
                  </article>
                  <article class="crm-contact-view-card sales-proposal-summary-card">
                    <strong>Company Snapshot</strong>
                    <p>${escapeHtml(selectedQuoteCompany?.industry ?? 'Industry not set')}</p>
                    <p class="cell-sub">${escapeHtml(selectedQuoteCompany?.location ?? 'Location not set')}</p>
                  </article>
                </div>
              </div>
              <input
                name="service_description"
                value="${escapeHtml(quotationServicePreset)}"
                placeholder="Service description"
                data-sales-quotation-focus="true"
                required
              />
              <textarea name="scope_of_work" rows="2" placeholder="Scope of work"></textarea>
              <input name="unit_price" type="number" min="0" step="0.01" placeholder="Unit price" required />
              <select name="gst_rate">${gstOptions()}</select>
              <input name="validity_period_end" type="date" />
              <button type="submit" ${selectedQuoteCompanyId ? '' : 'disabled'}>Create quotation</button>
            </form>
          </article>
        </div>
      `,
    )
  }

  if (state.salesOpenSection === 'proposals') {
    salesSectionContent = moduleStage(
      'Stage two',
      'Proposal Register',
      'Keep every quotation in a dedicated ledger with direct dispatch actions before order handoff begins.',
      `${state.quotations.length} proposals`,
      `
        <div class="module-grid">
          <article class="panel crm-panel-card crm-table-panel panel wide proposal-register-panel">
            <div class="crm-panel-copy">
              <p class="eyebrow">Proposal register</p>
              <div class="panel-head"><h2>Quotations</h2><span>${state.quotations.length} total with dispatch action</span></div>
            </div>
            <div class="table-wrap proposal-register-wrap"><table class="proposal-register-table"><thead><tr><th>Quotation</th><th>Company</th><th>Contact</th><th>Service</th><th>Scope</th><th>Unit Price</th><th>Taxes</th><th>Status</th><th>Total</th><th>Validity</th><th>Created</th><th>Action</th></tr></thead><tbody>${quoteRows || '<tr><td colspan="12">No quotations yet.</td></tr>'}</tbody></table></div>
          </article>
        </div>
      `,
    )
  }

  if (state.salesOpenSection === 'orders') {
    salesSectionContent = moduleStage(
      'Stage three',
      'Order Handoff',
      'Convert approved commercials into project-ready sales orders without mixing invoicing into the sales workspace.',
      `${state.orders.length} active orders`,
      `
        <div class="module-grid">
          <article class="panel crm-panel-card panel wide">
            <div class="crm-panel-copy">
              <p class="eyebrow">Fulfillment handoff</p>
              <div class="panel-head"><h2>Sales Order Approval</h2><span>Approve quotes to trigger project creation</span></div>
              <p class="crm-search-caption">Capture the delivery, ownership, and commercial handoff details before the quotation becomes a sales order.</p>
            </div>
            <form id="quotation-approval-form" class="card-form sales-handoff-form">
              <label class="sales-handoff-field sales-handoff-field-wide">
                <span>Approved quotation</span>
                <select name="quotation_id" required>${options(state.quotations.map((quote) => ({ value: quote.id, label: quote.quotation_number })))}</select>
              </label>
              <label class="sales-handoff-field">
                <span>Payment terms</span>
                <input name="payment_terms" placeholder="Net 15, advance, milestone split" />
              </label>
              <label class="sales-handoff-field">
                <span>Delivery timeline</span>
                <input name="delivery_timeline" placeholder="Delivery timeline" />
              </label>
              <label class="sales-handoff-field">
                <span>Project title</span>
                <input name="project_title" placeholder="Project title" />
              </label>
              <label class="sales-handoff-field">
                <span>Project manager</span>
                <select name="project_manager_id">${options([{ value: '', label: 'Project manager (optional)' }, ...state.employees.map((employee) => ({ value: employee.id, label: employee.name }))])}</select>
              </label>
              <label class="sales-handoff-field">
                <span>Start date</span>
                <input name="start_date" type="date" />
              </label>
              <label class="sales-handoff-field">
                <span>Deadline</span>
                <input name="deadline" type="date" />
              </label>
              <div class="sales-handoff-actions">
                <p class="crm-search-caption">Approving the quotation creates the sales order and triggers the downstream project setup flow.</p>
                <button type="submit">Approve quotation</button>
              </div>
            </form>
          </article>
        </div>
      `,
    )
  }

  if (state.salesOpenSection === 'register') {
    salesSectionContent = moduleStage(
      'Stage four',
      'Commercial Register',
      'Keep the sales order register in its own staged view after proposal handling and approval.',
      `${state.orders.length} orders`,
      `
        <div class="module-grid">
          <article class="panel crm-panel-card crm-table-panel panel wide">
            <div class="crm-panel-copy">
              <p class="eyebrow">Order register</p>
              <div class="panel-head"><h2>Sales Orders</h2><span>${state.orders.length} total</span></div>
            </div>
            <div class="table-wrap"><table><thead><tr><th>Order</th><th>Company</th><th>Contact</th><th>Quotation</th><th>Service</th><th>Scope</th><th>Unit Price</th><th>Taxes</th><th>Validity</th><th>Payment Terms</th><th>Delivery Timeline</th><th>Status</th><th>Value</th><th>Created</th><th>Action</th></tr></thead><tbody>${orderRows || '<tr><td colspan="15">No sales orders yet.</td></tr>'}</tbody></table></div>
          </article>
        </div>
      `,
    )
  }

  return `
    <section class="crm-shell">
      ${moduleHero(
        'Sales',
        'Commercial Pipeline',
        'Move qualified demand from CRM into proposals, approvals, and project-ready sales orders.',
        `${state.orders.length} orders in motion`,
        salesHighlights,
      )}
      ${moduleStageStrip(salesSectionButtons, state.salesOpenSection, 'data-sales-section')}
      ${activeSalesSection ? `<div class="crm-active-caption">Open stage: <strong>${escapeHtml(activeSalesSection.label)}</strong></div>` : ''}
      ${salesSectionContent}
      ${salesQuotationModal(state)}
    </section>
  `
}

function projects(state: AppState): string {
  const activeProjects = state.projects.filter((project) => !/completed/i.test(project.status)).length
  const assignedTasks = state.tasks.filter((task) => task.assigned_person_id).length
  const scheduledDeliveries = state.projects.filter((project) => project.deadline).length
  const projectCards = state.projects
    .map(
      (project) => `
        <article class="crm-contact-view-card project-card">
          <div class="panel-head"><h3>${escapeHtml(project.project_title)}</h3>${chip(project.status)}</div>
          <p>${escapeHtml(clientLabel(project.client_id, state.clients, state.companies))}</p>
          <p>Manager: ${escapeHtml(employeeName(project.project_manager_id, state.employees))}</p>
          <p>Deadline: ${escapeHtml(dateLabel(project.deadline))}</p>
        </article>
      `,
    )
    .join('')
  const taskRows = state.tasks
    .map(
      (task) => `
        <tr>
          <td>${escapeHtml(task.task_name)}</td>
          <td>${escapeHtml(projectLabel(task.project_id, state.projects))}</td>
          <td>${escapeHtml(employeeName(task.assigned_person_id, state.employees))}</td>
          <td>${chip(task.status)}</td>
        </tr>
      `,
    )
    .join('')
  const projectHighlights: ModuleHighlight[] = [
    { label: 'Active Projects', value: activeProjects, tone: 'active' },
    { label: 'Task Board', value: state.tasks.length, tone: 'good' },
    { label: 'Assigned Tasks', value: assignedTasks, tone: 'active' },
    { label: 'Dated Deliveries', value: scheduledDeliveries, tone: 'muted' },
  ]
  const projectSectionButtons: ModuleStageButton[] = [
    {
      id: 'intake',
      label: 'Project Intake',
      detail: 'Requirements, planning, and execution setup',
      meta: `${state.tasks.length} delivery tasks`,
    },
    {
      id: 'register',
      label: 'Delivery Register',
      detail: 'Active projects and task board visibility',
      meta: `${state.projects.length} active records`,
    },
  ]
  const activeProjectSection = projectSectionButtons.find((section) => section.id === state.projectsOpenSection)

  let projectSectionContent = ''

  if (state.projectsOpenSection === 'intake') {
    projectSectionContent = moduleStage(
      'Stage one',
      'Project Intake',
      'Capture client requirements and immediately turn them into assigned execution tasks.',
      `${state.tasks.length} delivery tasks`,
      `
        <div class="module-grid crm-section-grid crm-split-grid">
          <article class="panel crm-panel-card">
            <div class="crm-panel-copy">
              <p class="eyebrow">Discovery</p>
              <div class="panel-head"><h2>Requirement Collection</h2><span>Capture structured client inputs</span></div>
            </div>
            <form id="requirement-form" class="card-form">
              <select name="client_id" required>${options(state.clients.map((client) => ({ value: client.id, label: clientLabel(client.id, state.clients, state.companies) })))}</select>
              <select name="project_id">${options([{ value: '', label: 'Link to latest project automatically' }, ...state.projects.map((project) => ({ value: project.id, label: projectLabel(project.id, state.projects) }))])}</select>
              <textarea name="business_overview" rows="2" placeholder="Business overview"></textarea>
              <textarea name="project_objective" rows="2" placeholder="Project objective"></textarea>
              <input name="required_features" placeholder="Required features (comma separated)" />
              <input name="expected_deliverables" placeholder="Deliverables (comma separated)" />
              <input name="integrations" placeholder="Integrations (comma separated)" />
              <input name="timeline_expectations" placeholder="Timeline expectations" />
              <input name="budget_expectations" placeholder="Budget expectations" />
              <button type="submit">Store requirements</button>
            </form>
          </article>
          <article class="panel crm-panel-card">
            <div class="crm-panel-copy">
              <p class="eyebrow">Execution</p>
              <div class="panel-head"><h2>Task Execution</h2><span>Assign work and log time</span></div>
            </div>
            <form id="task-form" class="card-form">
              <select name="project_id" required>${options(state.projects.map((project) => ({ value: project.id, label: projectLabel(project.id, state.projects) })))}</select>
              <input name="task_name" placeholder="Task name" required />
              <textarea name="description" rows="2" placeholder="Task description"></textarea>
              <select name="assigned_person_id">${options([{ value: '', label: 'Unassigned' }, ...state.employees.map((employee) => ({ value: employee.id, label: employee.name }))])}</select>
              <input name="deadline" type="date" />
              <input name="estimated_time" type="number" step="0.25" placeholder="Estimated hours" />
              <select name="priority">${options(['Low', 'Medium', 'High', 'Critical'].map((value) => ({ value, label: value })), 'High')}</select>
              <button type="submit">Create task</button>
            </form>
            <form id="time-entry-form" class="card-form">
              <select name="task_id" required>${options(state.tasks.map((task) => ({ value: task.id, label: task.task_name })))}</select>
              <select name="employee_id" required>${options(state.employees.map((employee) => ({ value: employee.id, label: employee.name })))}</select>
              <input name="hours_worked" type="number" min="0" step="0.25" placeholder="Hours worked" required />
              <textarea name="work_notes" rows="2" placeholder="Work notes"></textarea>
              <button type="submit">Log time</button>
            </form>
          </article>
        </div>
      `,
    )
  }

  if (state.projectsOpenSection === 'register') {
    projectSectionContent = moduleStage(
      'Stage two',
      'Delivery Register',
      'Track live projects and the task board in the same staged CRM design language.',
      `${state.projects.length} active records`,
      `
        <div class="module-grid crm-section-grid crm-split-grid">
          <article class="panel crm-panel-card">
            <div class="crm-panel-copy">
              <p class="eyebrow">Portfolio</p>
              <div class="panel-head"><h2>Active Projects</h2><span>${state.projects.length} total</span></div>
            </div>
            <div class="project-grid">${projectCards || '<p class="empty">Projects appear automatically from approved sales orders.</p>'}</div>
          </article>
          <article class="panel crm-panel-card crm-table-panel">
            <div class="crm-panel-copy">
              <p class="eyebrow">Execution board</p>
              <div class="panel-head"><h2>Task Board</h2><span>${state.tasks.length} tasks</span></div>
            </div>
            <div class="table-wrap"><table><thead><tr><th>Task</th><th>Project</th><th>Assigned</th><th>Status</th></tr></thead><tbody>${taskRows || '<tr><td colspan="4">No tasks yet.</td></tr>'}</tbody></table></div>
          </article>
        </div>
      `,
    )
  }

  return `
    <section class="crm-shell">
      ${moduleHero(
        'Projects',
        'Delivery Workspace',
        'Carry requirements, execution, and delivery visibility through the same staged interface used in CRM.',
        `${state.projects.length} delivery records`,
        projectHighlights,
      )}
      ${moduleStageStrip(projectSectionButtons, state.projectsOpenSection, 'data-projects-section')}
      ${activeProjectSection ? `<div class="crm-active-caption">Open stage: <strong>${escapeHtml(activeProjectSection.label)}</strong></div>` : ''}
      ${projectSectionContent}
    </section>
  `
}

function hrm(state: AppState): string {
  const activeEmployees = state.employees.filter((employee) => employee.active).length
  const departmentCount = new Set(
    state.employees.map((employee) => normalizeSearchText(employee.department)).filter(Boolean),
  ).size
  const staffedProjects = new Set(state.assignments.map((assignment) => assignment.project_id)).size
  const employeeRows = state.employees
    .map(
      (employee) => `
        <tr>
          <td><strong>${escapeHtml(employee.name)}</strong><div class="cell-sub">${escapeHtml(employee.employee_code)}</div></td>
          <td>${escapeHtml(employee.role)}</td>
          <td>${escapeHtml(employee.department)}</td>
          <td>${chip(employee.employee_type)}</td>
        </tr>
      `,
    )
    .join('')
  const assignmentRows = state.assignments
    .map(
      (assignment) => `
        <tr>
          <td>${escapeHtml(employeeName(assignment.employee_id, state.employees))}</td>
          <td>${escapeHtml(projectLabel(assignment.project_id, state.projects))}</td>
          <td>${escapeHtml(assignment.allocation_role)}</td>
        </tr>
      `,
    )
    .join('')
  const hrmHighlights: ModuleHighlight[] = [
    { label: 'Active Employees', value: activeEmployees, tone: 'good' },
    { label: 'Assignments', value: state.assignments.length, tone: 'active' },
    { label: 'Departments', value: departmentCount, tone: 'muted' },
    { label: 'Staffed Projects', value: staffedProjects, tone: 'active' },
  ]
  const hrmSectionButtons: ModuleStageButton[] = [
    {
      id: 'setup',
      label: 'Workforce Setup',
      detail: 'Onboarding, project assignments, and reviews',
      meta: `${state.employees.length} employee records`,
    },
    {
      id: 'operations',
      label: 'Operations Cadence',
      detail: 'Attendance, payroll, and workforce register',
      meta: `${activeEmployees} active employees`,
    },
    {
      id: 'allocation',
      label: 'Project Staffing',
      detail: 'Project staffing register',
      meta: `${state.assignments.length} assignments`,
    },
  ]
  const activeHrmSection = hrmSectionButtons.find((section) => section.id === state.hrmOpenSection)

  let hrmSectionContent = ''

  if (state.hrmOpenSection === 'setup') {
    hrmSectionContent = moduleStage(
      'Stage one',
      'Workforce Setup',
      'Create employee records and connect people to delivery work with the same high-clarity card system.',
      `${state.employees.length} employee records`,
      `
        <div class="module-grid crm-section-grid crm-split-grid">
          <article class="panel crm-panel-card">
            <div class="crm-panel-copy">
              <p class="eyebrow">Onboarding</p>
              <div class="panel-head"><h2>Employee Onboarding</h2><span>Profiles and employment structure</span></div>
            </div>
            <form id="employee-form" class="card-form">
              <input name="name" placeholder="Employee name" required />
              <select name="employee_type">${options(['Partner', 'Intern', 'Freelancer/Contractual', 'Advisor', 'Fulltime', 'Trainee'].map((value) => ({ value, label: value })), 'Fulltime')}</select>
              <input name="department" placeholder="Department" required />
              <input name="role" placeholder="Role" required />
              <input name="joining_date" type="date" required />
              <input name="salary_structure" placeholder="Salary structure" required />
              <input name="monthly_compensation" type="number" min="0" step="0.01" placeholder="Monthly compensation" required />
              <button type="submit">Onboard employee</button>
            </form>
          </article>
          <article class="panel crm-panel-card">
            <div class="crm-panel-copy">
              <p class="eyebrow">Planning</p>
              <div class="panel-head"><h2>Assignments and Reviews</h2><span>Project staffing and performance</span></div>
            </div>
            <form id="assignment-form" class="card-form">
              <select name="employee_id" required>${options(state.employees.map((employee) => ({ value: employee.id, label: employee.name })))}</select>
              <select name="project_id" required>${options(state.projects.map((project) => ({ value: project.id, label: projectLabel(project.id, state.projects) })))}</select>
              <input name="allocation_role" placeholder="Assignment role" required />
              <button type="submit">Assign employee</button>
            </form>
            <form id="performance-review-form" class="card-form">
              <select name="employee_id" required>${options(state.employees.map((employee) => ({ value: employee.id, label: employee.name })))}</select>
              <input name="reviewer" placeholder="Reviewer" required />
              <input name="review_period" placeholder="Review period" required />
              <textarea name="goals" rows="2" placeholder="Goals"></textarea>
              <textarea name="feedback" rows="2" placeholder="Feedback"></textarea>
              <input name="rating" type="number" min="0" max="5" step="0.1" placeholder="Rating" />
              <button type="submit">Record review</button>
            </form>
          </article>
        </div>
      `,
    )
  }

  if (state.hrmOpenSection === 'operations') {
    hrmSectionContent = moduleStage(
      'Stage two',
      'Operations Cadence',
      'Run attendance and payroll operations while keeping the core workforce register visible in the same staged flow.',
      `${activeEmployees} active employees`,
      `
        <div class="module-grid crm-section-grid crm-split-grid">
          <article class="panel crm-panel-card">
            <div class="crm-panel-copy">
              <p class="eyebrow">Operations</p>
              <div class="panel-head"><h2>Attendance and Payroll</h2><span>Operations to accounting flow</span></div>
            </div>
            <form id="attendance-form" class="card-form">
              <select name="employee_id" required>${options(state.employees.map((employee) => ({ value: employee.id, label: employee.name })))}</select>
              <input name="work_date" type="date" required />
              <input name="check_in" type="datetime-local" />
              <input name="check_out" type="datetime-local" />
              <input name="leave_record" placeholder="Leave record" />
              <button type="submit">Track attendance</button>
            </form>
            <form id="payroll-form" class="card-form">
              <select name="employee_id" required>${options(state.employees.map((employee) => ({ value: employee.id, label: employee.name })))}</select>
              <input name="period_start" type="date" required />
              <input name="period_end" type="date" required />
              <input name="base_amount" type="number" min="0" step="0.01" placeholder="Base amount" required />
              <input name="bonus" type="number" min="0" step="0.01" placeholder="Bonus" />
              <input name="deductions" type="number" min="0" step="0.01" placeholder="Deductions" />
              <input name="payment_date" type="date" />
              <select name="status">${options(['Draft', 'Processed', 'Paid'].map((value) => ({ value, label: value })), 'Processed')}</select>
              <button type="submit">Process payroll</button>
            </form>
          </article>
          <article class="panel crm-panel-card crm-table-panel">
            <div class="crm-panel-copy">
              <p class="eyebrow">Workforce register</p>
              <div class="panel-head"><h2>Employees</h2><span>${state.employees.length} active records</span></div>
            </div>
            <div class="table-wrap"><table><thead><tr><th>Employee</th><th>Role</th><th>Department</th><th>Type</th></tr></thead><tbody>${employeeRows || '<tr><td colspan="4">No employees yet.</td></tr>'}</tbody></table></div>
          </article>
        </div>
      `,
    )
  }

  if (state.hrmOpenSection === 'allocation') {
    hrmSectionContent = moduleStage(
      'Stage three',
      'Project Staffing',
      'Keep project staffing visible in the same CRM-style register treatment used elsewhere in the product.',
      `${state.assignments.length} assignments`,
      `
        <article class="panel crm-panel-card crm-table-panel">
          <div class="crm-panel-copy">
            <p class="eyebrow">Staffing register</p>
            <div class="panel-head"><h2>Project Assignments</h2><span>${state.assignments.length} assignments</span></div>
          </div>
          <div class="table-wrap"><table><thead><tr><th>Employee</th><th>Project</th><th>Assignment Role</th></tr></thead><tbody>${assignmentRows || '<tr><td colspan="3">No assignments yet.</td></tr>'}</tbody></table></div>
        </article>
      `,
    )
  }

  return `
    <section class="crm-shell">
      ${moduleHero(
        'HRM',
        'Workforce Control',
        'Manage people records, staffing, reviews, attendance, and payroll in the same staged interface as CRM.',
        `${state.assignments.length} staffing actions`,
        hrmHighlights,
      )}
      ${moduleStageStrip(hrmSectionButtons, state.hrmOpenSection, 'data-hrm-section')}
      ${activeHrmSection ? `<div class="crm-active-caption">Open stage: <strong>${escapeHtml(activeHrmSection.label)}</strong></div>` : ''}
      ${hrmSectionContent}
    </section>
  `
}

function accounting(state: AppState): string {
  const summary = state.financeSummary
  const outstandingReceivables = state.invoices.reduce(
    (total, invoice) => total + (invoice.total_amount - invoice.paid_amount),
    0,
  )
  const accountingHighlights: ModuleHighlight[] = [
    { label: 'Revenue', value: currency(summary?.revenue), tone: 'good' },
    { label: 'Invoices', value: state.invoices.length, tone: 'active' },
    { label: 'Unpaid Invoices', value: summary?.unpaid_invoices ?? 0, tone: summary?.unpaid_invoices ? 'alert' : 'good' },
    { label: 'Expenses', value: currency(summary?.expenses), tone: 'alert' },
    { label: 'Receivables', value: currency(summary?.receivables), tone: 'active' },
  ]
  const invoiceRows = state.invoices
    .map(
      (invoice) => `
        <tr>
          <td><strong>${escapeHtml(invoice.invoice_number)}</strong><div class="cell-sub">${escapeHtml(clientLabel(invoice.client_id, state.clients, state.companies))}</div></td>
          <td>${chip(invoice.status)}</td>
          <td>${currency(invoice.total_amount)}</td>
          <td>${currency(invoice.total_amount - invoice.paid_amount)}</td>
        </tr>
      `,
    )
    .join('')
  const ledgerRows = state.ledger
    .map(
      (entry) => `
        <tr>
          <td>${escapeHtml(entry.entry_date)}</td>
          <td>${escapeHtml(entry.reference)}</td>
          <td>${escapeHtml(entry.account_name)}</td>
          <td>${currency(entry.debit)}</td>
          <td>${currency(entry.credit)}</td>
        </tr>
      `,
    )
    .join('')
  const accountingSectionButtons: ModuleStageButton[] = [
    {
      id: 'capture',
      label: 'Expense Capture',
      detail: 'Expense posting and financial pulse',
      meta: `${state.expenses.length} expense entries`,
    },
    {
      id: 'billing',
      label: 'Billing and Invoicing',
      detail: 'Invoices, collections, credit notes, and receivables',
      meta: `${state.invoices.length} live invoices`,
    },
    {
      id: 'ledger',
      label: 'Ledger Register',
      detail: 'General ledger review',
      meta: `${state.ledger.length} posted entries`,
    },
  ]
  const activeAccountingSection = accountingSectionButtons.find((section) => section.id === state.accountingOpenSection)

  let accountingSectionContent = ''

  if (state.accountingOpenSection === 'capture') {
    accountingSectionContent = moduleStage(
      'Stage one',
      'Expense Capture',
      'Record spend and keep the accounting heartbeat visible beside the action surface.',
      `${state.expenses.length} expense entries`,
      `
        <div class="module-grid crm-section-grid crm-split-grid">
          <article class="panel crm-panel-card">
            <div class="crm-panel-copy">
              <p class="eyebrow">Posting input</p>
              <div class="panel-head"><h2>Expense Tracking</h2><span>Every entry posts to the ledger</span></div>
            </div>
            <form id="expense-form" class="card-form">
              <input name="category" placeholder="Expense category" required />
              <textarea name="description" rows="2" placeholder="Description"></textarea>
              <input name="amount" type="number" min="0" step="0.01" placeholder="Amount" required />
              <input name="payment_date" type="date" required />
              <input name="payment_method" placeholder="Payment method" />
              <button type="submit">Record expense</button>
            </form>
          </article>
          <article class="panel crm-panel-card crm-panel-card-fit">
            <div class="crm-panel-copy">
              <p class="eyebrow">Posting snapshot</p>
              <div class="panel-head"><h2>Accounting Pulse</h2><span>Financial state at a glance</span></div>
            </div>
            <div class="mini-grid">
              <div class="mini-card"><span>Ledger Entries</span><strong>${state.ledger.length}</strong></div>
              <div class="mini-card"><span>Expense Rows</span><strong>${state.expenses.length}</strong></div>
              <div class="mini-card"><span>Unpaid Invoices</span><strong>${summary?.unpaid_invoices ?? 0}</strong></div>
              <div class="mini-card"><span>Receivables</span><strong>${currency(summary?.receivables)}</strong></div>
            </div>
          </article>
        </div>
      `,
    )
  }

  if (state.accountingOpenSection === 'billing') {
    accountingSectionContent = moduleStage(
      'Stage two',
      'Billing and Invoicing',
      'Generate invoices, record collections, and manage receivables from the accounting workspace.',
      `${state.invoices.length} live invoices`,
      `
        <div class="module-grid crm-section-grid crm-split-grid">
          <article class="panel crm-panel-card">
            <div class="crm-panel-copy">
              <p class="eyebrow">Billing desk</p>
              <div class="panel-head"><h2>Invoice Generation</h2><span>Create invoices against approved sales orders</span></div>
            </div>
            <form id="invoice-form" class="card-form">
              <select name="client_id" required>${options(state.clients.map((client) => ({ value: client.id, label: clientLabel(client.id, state.clients, state.companies) })))}</select>
              <select name="sales_order_id" required>${options(state.orders.map((order) => ({ value: order.id, label: order.sales_order_number })))}</select>
              <input name="amount" type="number" min="0" step="0.01" placeholder="Base amount" required />
              <select name="gst_rate">${gstOptions()}</select>
              <input name="due_date" type="date" required />
              <select name="billing_mode">${options(['Full Billing', 'Milestone Billing', 'Partial Billing'].map((value) => ({ value, label: value })), 'Milestone Billing')}</select>
              <button type="submit">Generate invoice</button>
            </form>
          </article>
          <article class="panel crm-panel-card crm-panel-card-fit">
            <div class="crm-panel-copy">
              <p class="eyebrow">Collections</p>
              <div class="panel-head"><h2>Payments and Credit Notes</h2><span>Track money movement and invoice adjustments</span></div>
            </div>
            <form id="payment-form" class="card-form">
              <select name="invoice_id" required>${options(state.invoices.map((invoice) => ({ value: invoice.id, label: invoice.invoice_number })))}</select>
              <input name="amount" type="number" min="0" step="0.01" placeholder="Payment amount" required />
              <input name="payment_date" type="date" required />
              <input name="payment_method" placeholder="Payment method" required />
              <input name="reference" placeholder="Reference" />
              <button type="submit">Record payment</button>
            </form>
            <form id="credit-note-form" class="card-form">
              <select name="invoice_id" required>${options(state.invoices.map((invoice) => ({ value: invoice.id, label: invoice.invoice_number })))}</select>
              <input name="amount" type="number" min="0" step="0.01" placeholder="Credit note amount" required />
              <textarea name="reason" rows="2" placeholder="Reason"></textarea>
              <button type="submit">Issue credit note</button>
            </form>
          </article>
        </div>
        <article class="panel crm-panel-card crm-table-panel">
          <div class="crm-panel-copy">
            <p class="eyebrow">Billing register</p>
            <div class="panel-head"><h2>Invoices</h2><span>${state.invoices.length} total</span></div>
          </div>
          <div class="table-wrap"><table><thead><tr><th>Invoice</th><th>Status</th><th>Total</th><th>Outstanding</th></tr></thead><tbody>${invoiceRows || '<tr><td colspan="4">No invoices yet.</td></tr>'}</tbody></table></div>
          <div class="crm-contact-toolbar">
            <p class="crm-search-caption">Outstanding receivables are currently tracked at ${escapeHtml(currency(outstandingReceivables))}.</p>
            <span class="crm-stage-pill">${summary?.unpaid_invoices ?? 0} unpaid invoices</span>
          </div>
        </article>
      `,
    )
  }

  if (state.accountingOpenSection === 'ledger') {
    accountingSectionContent = moduleStage(
      'Stage three',
      'Ledger Register',
      'Review the general ledger with the same card and table treatment used throughout CRM.',
      `${state.ledger.length} posted entries`,
      `
        <article class="panel crm-panel-card crm-table-panel">
          <div class="crm-panel-copy">
            <p class="eyebrow">General register</p>
            <div class="panel-head"><h2>General Ledger</h2><span>${state.ledger.length} entries</span></div>
          </div>
          <div class="table-wrap"><table><thead><tr><th>Date</th><th>Reference</th><th>Account</th><th>Debit</th><th>Credit</th></tr></thead><tbody>${ledgerRows || '<tr><td colspan="5">No ledger entries yet.</td></tr>'}</tbody></table></div>
        </article>
      `,
    )
  }

  return `
    <section class="crm-shell">
      ${moduleHero(
        'Accounting',
        'Financial Control',
        'Keep expense capture, billing, receivables, and the ledger inside the same CRM-style operational surface.',
        `${state.ledger.length} ledger entries tracked`,
        accountingHighlights,
      )}
      ${moduleStageStrip(accountingSectionButtons, state.accountingOpenSection, 'data-accounting-section')}
      ${activeAccountingSection ? `<div class="crm-active-caption">Open stage: <strong>${escapeHtml(activeAccountingSection.label)}</strong></div>` : ''}
      ${accountingSectionContent}
    </section>
  `
}

function investment(state: AppState): string {
  const totalInvestments = state.investments.reduce((sum, entry) => sum + entry.investment_amount, 0)
  const uniquePartners = new Set(state.investments.map((entry) => normalizeSearchText(entry.partner_name)).filter(Boolean)).size
  const accountingRevenue = state.financeSummary?.revenue ?? 0
  const accountingExpenses = state.financeSummary?.expenses ?? 0
  const totalProfit = accountingRevenue - accountingExpenses
  const capitalInvestments = state.investments
    .filter((entry) => entry.investment_type === 'Capital Investment')
    .reduce((sum, entry) => sum + entry.investment_amount, 0)
  const partnerLoans = state.investments
    .filter((entry) => entry.investment_type === 'Loan to company')
    .reduce((sum, entry) => sum + entry.investment_amount, 0)
  const additionalFunding = state.investments
    .filter((entry) => entry.investment_type === 'Additional Funding')
    .reduce((sum, entry) => sum + entry.investment_amount, 0)
  const partnerRollup = new Map<string, { partnerName: string; totalInvested: number; shareOfPartner: number | null }>()
  state.investments.forEach((entry) => {
    const partnerKey = normalizeSearchText(entry.partner_name) || entry.partner_name
    const existingPartner = partnerRollup.get(partnerKey)
    if (existingPartner) {
      existingPartner.totalInvested += entry.investment_amount
      if (existingPartner.shareOfPartner == null && entry.share_of_partner != null) {
        existingPartner.shareOfPartner = entry.share_of_partner
      }
      return
    }
    partnerRollup.set(partnerKey, {
      partnerName: entry.partner_name,
      totalInvested: entry.investment_amount,
      shareOfPartner: entry.share_of_partner ?? null,
    })
  })
  const partners = Array.from(partnerRollup.values())
  const totalDeclaredShare = partners.reduce((sum, partner) => sum + (partner.shareOfPartner ?? 0), 0)
  const distributableProfit = totalProfit > 0 && totalDeclaredShare > 0 ? totalProfit : 0

  const investmentHighlights: ModuleHighlight[] = [
    { label: 'Total Funding', value: currency(totalInvestments), tone: 'good' },
    { label: 'Revenue', value: currency(accountingRevenue), tone: 'good' },
    { label: 'Expenses', value: currency(accountingExpenses), tone: 'alert' },
    { label: 'Profit', value: currency(totalProfit), tone: totalProfit >= 0 ? 'good' : 'alert' },
    { label: 'Partners', value: uniquePartners, tone: 'active' },
  ]

  const investmentRows = state.investments
    .map(
      (entry) => `
        <tr>
          <td><strong>${escapeHtml(entry.partner_name)}</strong><div class="cell-sub">${escapeHtml(entry.reference_number)}</div></td>
          <td>${escapeHtml(dateLabel(entry.investment_date))}</td>
          <td>${escapeHtml(entry.investment_time_period ?? 'Not set')}</td>
          <td>${escapeHtml(entry.share_of_partner != null ? `${entry.share_of_partner.toFixed(2)}%` : 'Not set')}</td>
          <td>${currency(entry.investment_amount)}</td>
          <td>${chip(entry.mode)}</td>
          <td>${chip(entry.investment_type)}</td>
        </tr>
      `,
    )
    .join('')
  const allocationRows = partners
    .map((partner) => {
      const shareOfPartner = partner.shareOfPartner ?? 0
      const profitAllocation =
        distributableProfit > 0 && totalDeclaredShare > 0 ? distributableProfit * shareOfPartner / totalDeclaredShare : 0
      return `
        <tr>
          <td><strong>${escapeHtml(partner.partnerName)}</strong></td>
          <td>${escapeHtml(partner.shareOfPartner != null ? `${partner.shareOfPartner.toFixed(2)}%` : 'Not set')}</td>
          <td>${currency(partner.totalInvested)}</td>
          <td>${currency(profitAllocation)}</td>
        </tr>
      `
    })
    .join('')

  const investmentSectionButtons: ModuleStageButton[] = [
    {
      id: 'capture',
      label: 'Investment Capture',
      detail: 'Record fresh partner funding',
      meta: `${state.investments.length} posted entries`,
    },
    {
      id: 'ledger',
      label: 'Partner Ledger',
      detail: 'Review all partner investment records',
      meta: `${currency(totalInvestments)} tracked`,
    },
    {
      id: 'allocation',
      label: 'Profit Allocation',
      detail: 'Distribute profit by partner share holding',
      meta: `${currency(totalProfit)} profit calculated`,
    },
  ]

  const activeInvestmentSection = investmentSectionButtons.find((section) => section.id === state.investmentOpenSection)

  let investmentSectionContent = ''

  if (state.investmentOpenSection === 'capture') {
    investmentSectionContent = moduleStage(
      'Stage one',
      'Investment Capture',
      'Record partner funding with the same card-led workflow used in every other Athena module.',
      `${state.investments.length} entries posted`,
      `
        <div class="module-grid crm-section-grid crm-split-grid">
          <article class="panel crm-panel-card">
            <div class="crm-panel-copy">
              <p class="eyebrow">Funding input</p>
              <div class="panel-head"><h2>Partner Investment Ledger</h2><span>Each entry posts to the general ledger</span></div>
            </div>
            <form id="partner-investment-form" class="card-form">
              <input name="partner_name" placeholder="Partner name" required />
              <input name="investment_date" type="date" required />
              <input name="investment_time_period" placeholder="Investment time period" />
              <input name="share_of_partner" type="number" min="0" max="100" step="0.01" placeholder="Share of partner (%)" required />
              <input name="investment_amount" type="number" min="0" step="0.01" placeholder="Investment amount" required />
              <select name="mode" required>${options(['Cash', 'Online'].map((value) => ({ value, label: value })), 'Online')}</select>
              <select name="investment_type" required>${options(['Capital Investment', 'Loan to company', 'Additional Funding'].map((value) => ({ value, label: value })), 'Capital Investment')}</select>
              <button type="submit">Record investment</button>
            </form>
          </article>
          <article class="panel crm-panel-card crm-panel-card-fit">
            <div class="crm-panel-copy">
              <p class="eyebrow">Funding snapshot</p>
              <div class="panel-head"><h2>Investment Pulse</h2><span>Partner funding mix at a glance</span></div>
            </div>
            <div class="mini-grid">
              <div class="mini-card"><span>Total Entries</span><strong>${state.investments.length}</strong></div>
              <div class="mini-card"><span>Unique Partners</span><strong>${uniquePartners}</strong></div>
              <div class="mini-card"><span>Capital</span><strong>${currency(capitalInvestments)}</strong></div>
              <div class="mini-card"><span>Loans</span><strong>${currency(partnerLoans)}</strong></div>
              <div class="mini-card"><span>Profit</span><strong>${currency(totalProfit)}</strong></div>
              <div class="mini-card"><span>Declared Shares</span><strong>${escapeHtml(totalDeclaredShare.toFixed(2))}%</strong></div>
            </div>
          </article>
        </div>
      `,
    )
  }

  if (state.investmentOpenSection === 'ledger') {
    investmentSectionContent = moduleStage(
      'Stage two',
      'Partner Ledger',
      'Review partner capital, loans, and additional funding in the same register treatment used across Athena.',
      `${state.investments.length} posted entries`,
      `
        <article class="panel crm-panel-card crm-table-panel">
          <div class="crm-panel-copy">
            <p class="eyebrow">Investment register</p>
            <div class="panel-head"><h2>Partner Investment Ledger</h2><span>${state.investments.length} entries</span></div>
          </div>
          <div class="table-wrap"><table><thead><tr><th>Partner</th><th>Date</th><th>Time Period</th><th>Share</th><th>Amount</th><th>Mode</th><th>Investment Type</th></tr></thead><tbody>${investmentRows || '<tr><td colspan="7">No partner investments yet.</td></tr>'}</tbody></table></div>
        </article>
      `,
    )
  }

  if (state.investmentOpenSection === 'allocation') {
    investmentSectionContent = moduleStage(
      'Stage three',
      'Profit Allocation',
      'Fetch revenue and expenses from accounting, calculate profit inside the investment module, and distribute it to partners by declared share holding.',
      `${partners.length} partners in allocation`,
      `
        <div class="module-grid crm-section-grid crm-split-grid">
          <article class="panel crm-panel-card crm-panel-card-fit">
            <div class="crm-panel-copy">
              <p class="eyebrow">Accounting-linked profit base</p>
              <div class="panel-head"><h2>Profit Base</h2><span>Revenue and expenses sourced from accounting</span></div>
            </div>
            <div class="mini-grid">
              <div class="mini-card"><span>Total Revenue</span><strong>${currency(accountingRevenue)}</strong></div>
              <div class="mini-card"><span>Total Expenses</span><strong>${currency(accountingExpenses)}</strong></div>
              <div class="mini-card"><span>Total Profit</span><strong>${currency(totalProfit)}</strong></div>
              <div class="mini-card"><span>Distributable Profit</span><strong>${currency(distributableProfit)}</strong></div>
            </div>
          </article>
          <article class="panel crm-panel-card crm-panel-card-fit">
            <div class="crm-panel-copy">
              <p class="eyebrow">Share base</p>
              <div class="panel-head"><h2>Partner Share Holding</h2><span>Allocations normalize across declared shares</span></div>
            </div>
            <div class="mini-grid">
              <div class="mini-card"><span>Partners</span><strong>${partners.length}</strong></div>
              <div class="mini-card"><span>Declared Shares</span><strong>${escapeHtml(totalDeclaredShare.toFixed(2))}%</strong></div>
              <div class="mini-card"><span>Capital Funding</span><strong>${currency(capitalInvestments)}</strong></div>
              <div class="mini-card"><span>Additional Funding</span><strong>${currency(additionalFunding)}</strong></div>
            </div>
          </article>
        </div>
        <article class="panel crm-panel-card crm-table-panel">
          <div class="crm-panel-copy">
            <p class="eyebrow">Distribution register</p>
            <div class="panel-head"><h2>Profit Allocation To Partner</h2><span>${partners.length} partners</span></div>
          </div>
          <div class="table-wrap"><table><thead><tr><th>Partner</th><th>Share Holding</th><th>Total Invested</th><th>Profit Allocation</th></tr></thead><tbody>${allocationRows || '<tr><td colspan="4">No partner share data available yet.</td></tr>'}</tbody></table></div>
          <div class="crm-contact-toolbar">
            <p class="crm-search-caption">${totalProfit > 0 ? 'Profit allocation is calculated from accounting revenue minus accounting expenses.' : 'No positive profit is currently available for allocation.'}</p>
            <span class="crm-stage-pill">${escapeHtml(totalDeclaredShare.toFixed(2))}% declared share</span>
          </div>
        </article>
      `,
    )
  }

  return `
    <section class="crm-shell">
      ${moduleHero(
        'Investment',
        'Capital Management',
        'Track partner funding, capital injections, and shareholder loans in the same staged control surface as the rest of the ERP.',
        `${state.investments.length} partner investments tracked`,
        investmentHighlights,
      )}
      ${moduleStageStrip(investmentSectionButtons, state.investmentOpenSection, 'data-investment-section')}
      ${activeInvestmentSection ? `<div class="crm-active-caption">Open stage: <strong>${escapeHtml(activeInvestmentSection.label)}</strong></div>` : ''}
      ${investmentSectionContent}
    </section>
  `
}

function activeSection(state: AppState): string {
  switch (state.activeSection) {
    case 'dashboard':
      return overview(state)
    case 'crm':
      return crm(state)
    case 'sales':
      return sales(state)
    case 'projects':
      return projects(state)
    case 'hrm':
      return hrm(state)
    case 'accounting':
      return accounting(state)
    case 'investment':
      return investment(state)
  }
}

export function renderApp(state: AppState): string {
  return `
    <div class="app-shell">
      <header class="topbar">
        <div class="brand-block">
          <p class="eyebrow">Athena</p>
          <h1>Zappizo ERP Control Center</h1>
          <p class="brand-copy">Trace every commercial, delivery, workforce, investment, and accounting event from one place.</p>
        </div>
        <div class="status-block">
          <div class="status-meta">
            <span class="connection-pill ${state.apiAvailable ? 'online' : 'offline'}">${state.apiAvailable ? 'API connected' : 'API unavailable'}</span>
            <span class="connection-copy">${state.saving ? 'Saving changes...' : state.loading ? 'Refreshing data...' : 'Synchronized workflow view'}</span>
          </div>
          <button
            type="button"
            class="ghost-button topbar-refresh-button"
            data-refresh-app="true"
            ${state.loading || state.saving ? 'disabled' : ''}
          >
            ${state.loading ? 'Refreshing workspace...' : state.apiAvailable ? 'Refresh workspace' : 'Retry connection'}
          </button>
        </div>
      </header>
      <div class="workspace-shell">
        <section class="sidebar module-menu-shell">
          <div class="sidebar-card module-menu-card">
            <div class="module-menu-head">
              <div>
                <p class="eyebrow">Modules</p>
                <h3>Workspace Navigation</h3>
              </div>
              <p class="module-menu-copy">Use the full workspace width below for every module card.</p>
            </div>
            <nav class="nav-stack module-nav-grid">${nav(state)}</nav>
          </div>
        </section>
        <main class="workspace">
          ${state.message ? `<div class="notice success">${escapeHtml(state.message)}</div>` : ''}
          ${state.error ? `<div class="notice error">${escapeHtml(state.error)}</div>` : ''}
          ${activeSection(state)}
        </main>
      </div>
    </div>
  `
}
