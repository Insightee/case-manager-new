import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'
import {
  AdminCollapsibleFilters,
  AdminEmptyState,
  AdminFilterGrid,
  AdminPageHeader,
  AdminPanel,
  FilterDateRange,
  FilterSelect,
} from './ui/index.js'
import './admin-reports.css'

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'OPEN', label: 'Open' },
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'RESOLVED', label: 'Resolved' },
  { value: 'CLOSED', label: 'Closed' },
]

const CATEGORY_OPTIONS = [
  { value: '', label: 'All categories' },
  { value: 'FINANCE', label: 'Finance' },
  { value: 'HR', label: 'HR' },
  { value: 'SERVICE', label: 'Service' },
  { value: 'TECH', label: 'Tech' },
  { value: 'OTHER', label: 'Other' },
  { value: 'POSH', label: 'POSH' },
  { value: 'CPP', label: 'CPP' },
]

const MODULE_OPTIONS = [
  { value: '', label: 'All modules' },
  { value: 'shadow_support', label: 'Shadow support' },
  { value: 'homecare', label: 'Homecare' },
  { value: 'b2b', label: 'B2B' },
  { value: 'none', label: 'No module' },
]

function istToday() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

function currentMonthStart() {
  return `${istToday().slice(0, 8)}01`
}

function reportQuery(filters) {
  const qs = new URLSearchParams()
  if (filters.status) qs.set('status', filters.status)
  if (filters.category) qs.set('category', filters.category)
  if (filters.productModule) qs.set('product_module', filters.productModule)
  if (filters.assignedTo) qs.set('assigned_to', filters.assignedTo)
  if (filters.dateFrom) qs.set('date_from', filters.dateFrom)
  if (filters.dateTo) qs.set('date_to', filters.dateTo)
  return qs.toString()
}

function ReportTable({ columns, rows, empty }) {
  if (!rows?.length) {
    return <p className="support-ticket-report__note">{empty || 'Nothing in this view yet.'}</p>
  }
  return (
    <div className="admin-table-wrap">
      <table className="admin-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={column.numeric ? 'support-ticket-report__num' : undefined}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key ?? row.id ?? row.label ?? row.role}>
              {columns.map((column) => (
                <td key={column.key} className={column.numeric ? 'support-ticket-report__num' : undefined}>
                  {column.render ? column.render(row) : row[column.key] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function dash(value) {
  return value == null || value === '' ? '—' : value
}

export function AdminSupportTicketReportPage({ embedded = false }) {
  const [status, setStatus] = useState('')
  const [category, setCategory] = useState('')
  const [productModule, setProductModule] = useState('')
  const [assignedTo, setAssignedTo] = useState('')
  const [dateFrom, setDateFrom] = useState(currentMonthStart)
  const [dateTo, setDateTo] = useState(istToday)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')

  const filters = useMemo(
    () => ({ status, category, productModule, assignedTo, dateFrom, dateTo }),
    [status, category, productModule, assignedTo, dateFrom, dateTo],
  )

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const data = await apiFetch(`/api/v1/admin/support/ticket-report?${reportQuery(filters)}`)
      setReport(data)
    } catch (err) {
      setReport(null)
      setLoadError(err.message || 'Looks like we still need a few details before we can show this report.')
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    load()
  }, [load])

  const assigneeOptions = useMemo(() => {
    const options = [{ value: '', label: 'Any assignee' }, { value: 'unassigned', label: 'Unassigned' }]
    for (const person of report?.assignee_options || []) {
      options.push({ value: String(person.id), label: person.name || `Staff #${person.id}` })
    }
    if (assignedTo && !options.some((option) => option.value === assignedTo)) {
      options.push({ value: assignedTo, label: `Assignee #${assignedTo}` })
    }
    return options
  }, [report, assignedTo])

  const moduleOptions = useMemo(() => {
    const known = new Set(MODULE_OPTIONS.map((option) => option.value))
    const extras = (report?.by_module || [])
      .filter((row) => row.module && !known.has(row.module))
      .map((row) => ({ value: row.module, label: row.label }))
    return [...MODULE_OPTIONS, ...extras]
  }, [report])

  const activeChips = useMemo(() => {
    return [
      status ? STATUS_OPTIONS.find((option) => option.value === status)?.label : null,
      category ? CATEGORY_OPTIONS.find((option) => option.value === category)?.label : null,
      productModule ? moduleOptions.find((option) => option.value === productModule)?.label : null,
      assignedTo ? assigneeOptions.find((option) => option.value === assignedTo)?.label : null,
      dateFrom && dateTo ? `${dateFrom} to ${dateTo}` : null,
    ].filter(Boolean)
  }, [status, category, productModule, assignedTo, dateFrom, dateTo, moduleOptions, assigneeOptions])

  function resetFilters() {
    setStatus('')
    setCategory('')
    setProductModule('')
    setAssignedTo('')
    setDateFrom(currentMonthStart())
    setDateTo(istToday())
  }

  async function downloadExcel() {
    setExporting(true)
    setExportError('')
    try {
      const filename = `support-tickets-report-${dateFrom}-to-${dateTo}.xlsx`
      await apiDownload(`/api/v1/admin/support/ticket-report.xlsx?${reportQuery(filters)}`, filename)
    } catch (err) {
      setExportError(err.message || 'The Excel file did not download. Try again in a moment.')
    } finally {
      setExporting(false)
    }
  }

  const aging = report?.aging
  const agingRows = aging
    ? [
        { key: 'open-none', label: 'Open with no reply yet', count: aging.open_no_reply },
        { key: 'open-7', label: 'Open, no reply, 7 days or newer', count: aging.open_no_reply_within_7_days },
        { key: 'open-30', label: 'Open, no reply, 8 to 30 days', count: aging.open_no_reply_8_to_30_days },
        { key: 'open-old', label: 'Open, no reply, older than 30 days', count: aging.open_no_reply_older_than_30_days },
        { key: 'open-oldest', label: 'Oldest open ticket (days)', count: dash(aging.oldest_open_days) },
        { key: 'ip', label: 'In progress', count: aging.in_progress },
        { key: 'ip-7', label: 'In progress, older than 7 days', count: aging.in_progress_older_than_7_days },
        { key: 'ip-30', label: 'In progress, older than 30 days', count: aging.in_progress_older_than_30_days },
        { key: 'ip-oldest', label: 'Oldest in-progress ticket (days)', count: dash(aging.oldest_in_progress_days) },
      ]
    : []

  const downloadLabel = exporting ? 'Preparing Excel…' : 'Download Excel'

  return (
    <div className={`support-ticket-report${embedded ? '' : ' admin-page'}`}>
      {embedded ? null : (
        <AdminPageHeader
          eyebrow="Support"
          title="Ticket report"
          subtitle="Read-only counts for the tickets you already handle. Nothing on this page replies, closes, or changes a ticket."
        />
      )}

      <AdminCollapsibleFilters activeChips={activeChips} activeCount={activeChips.length} defaultOpen={false}>
        <AdminFilterGrid ariaLabel="Ticket report filters">
          <FilterSelect
            label="Status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            options={STATUS_OPTIONS}
          />
          <FilterSelect
            label="Category"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            options={CATEGORY_OPTIONS}
          />
          <FilterSelect
            label="Module"
            value={productModule}
            onChange={(event) => setProductModule(event.target.value)}
            options={moduleOptions}
          />
          <FilterSelect
            label="Assignee"
            value={assignedTo}
            onChange={(event) => setAssignedTo(event.target.value)}
            options={assigneeOptions}
          />
          <FilterDateRange
            label="Opened"
            from={dateFrom}
            to={dateTo}
            onFromChange={(event) => setDateFrom(event.target.value)}
            onToChange={(event) => setDateTo(event.target.value)}
          />
          <button type="button" className="admin-btn admin-btn--secondary" onClick={resetFilters}>
            This month
          </button>
        </AdminFilterGrid>
      </AdminCollapsibleFilters>

      <p className="support-ticket-report__note">
        Dates use Asia/Kolkata. The queue lists open and in-progress tickets only. POSH and CPP stay in the
        counts and are not listed. Staff names and case codes are shown. Child names, parent contacts, message
        text, and attachments are not.
      </p>

      {loadError ? <p className="admin-alert admin-alert--error">{loadError}</p> : null}
      {exportError ? <p className="admin-alert admin-alert--error">{exportError}</p> : null}

      {loading && !report ? <p className="support-ticket-report__note">Gathering tickets for this range…</p> : null}

      {report ? (
        <>
          <div className="admin-reports__kpis support-ticket-report__kpis">
            {[
              { value: '', label: 'In this range', count: report.total },
              { value: 'OPEN', label: 'Open', count: report.by_status?.find((row) => row.status === 'OPEN')?.tickets ?? 0 },
              {
                value: 'IN_PROGRESS',
                label: 'In progress',
                count: report.by_status?.find((row) => row.status === 'IN_PROGRESS')?.tickets ?? 0,
              },
              {
                value: 'RESOLVED',
                label: 'Resolved',
                count: report.by_status?.find((row) => row.status === 'RESOLVED')?.tickets ?? 0,
              },
              {
                value: 'CLOSED',
                label: 'Closed',
                count: report.by_status?.find((row) => row.status === 'CLOSED')?.tickets ?? 0,
              },
            ].map((card) => (
              <button
                key={card.label}
                type="button"
                className={`admin-reports__kpi${status === card.value ? ' is-active' : ''}`}
                onClick={() => setStatus(card.value)}
              >
                <div className="admin-reports__kpi-value">{loading ? '…' : card.count}</div>
                <div className="admin-reports__kpi-label">{card.label}</div>
              </button>
            ))}
          </div>

          <AdminPanel
            title="Counts by status"
            subtitle={`${report.in_flight} open or in progress in this view.`}
          >
            <ReportTable
              columns={[
                { key: 'label', label: 'Status' },
                { key: 'tickets', label: 'Tickets', numeric: true },
                { key: 'share', label: 'Share', numeric: true, render: (row) => `${row.share_pct}%` },
              ]}
              rows={(report.by_status || []).map((row) => ({ ...row, key: row.status }))}
            />
          </AdminPanel>

          <AdminPanel
            title="Open and in progress"
            subtitle={
              report.queue_truncated
                ? `Showing ${report.queue.length} of ${report.queue_total}, oldest first.`
                : `${report.queue_total} in the queue.`
            }
          >
            {report.restricted_omitted ? (
              <p className="support-ticket-report__note">
                {report.restricted_omitted} POSH or CPP {report.restricted_omitted === 1 ? 'ticket is' : 'tickets are'}{' '}
                in the counts and left out of this list.
              </p>
            ) : null}
            <ReportTable
              empty="No open or in-progress tickets for these filters."
              columns={[
                {
                  key: 'id',
                  label: 'Ticket',
                  render: (row) => (
                    <Link to={`/admin/support?tab=tickets&ticket=${row.id}`}>#{row.id}</Link>
                  ),
                },
                { key: 'status_label', label: 'Status' },
                { key: 'category_label', label: 'Category' },
                { key: 'module_label', label: 'Module' },
                { key: 'case_code', label: 'Case code', render: (row) => row.case_code || '—' },
                { key: 'raised_by', label: 'Raised by' },
                { key: 'assignee', label: 'Assignee' },
                { key: 'opened_on', label: 'Opened' },
                { key: 'age_days', label: 'Age (days)', numeric: true },
                {
                  key: 'awaiting_first_reply',
                  label: 'No reply yet',
                  render: (row) => (row.awaiting_first_reply ? 'Yes' : 'No'),
                },
              ]}
              rows={report.queue || []}
            />
          </AdminPanel>

          <AdminPanel title="Counts by category" subtitle="POSH and CPP are counts only. No suggested reply.">
            <ReportTable
              columns={[
                { key: 'label', label: 'Category' },
                { key: 'open', label: 'Open', numeric: true },
                { key: 'in_progress', label: 'In progress', numeric: true },
                { key: 'resolved', label: 'Resolved', numeric: true },
                { key: 'closed', label: 'Closed', numeric: true },
                { key: 'total', label: 'Total', numeric: true },
                { key: 'still_open', label: 'Still open', numeric: true },
              ]}
              rows={(report.by_category || []).map((row) => ({ ...row, key: row.category }))}
            />
          </AdminPanel>

          <AdminPanel title="Counts by module" subtitle="Shadow support, homecare, B2B, and tickets with no module.">
            <ReportTable
              columns={[
                { key: 'label', label: 'Module' },
                { key: 'open', label: 'Open', numeric: true },
                { key: 'in_progress', label: 'In progress', numeric: true },
                { key: 'resolved', label: 'Resolved', numeric: true },
                { key: 'closed', label: 'Closed', numeric: true },
                { key: 'total', label: 'Total', numeric: true },
                { key: 'still_open', label: 'Still open', numeric: true },
              ]}
              rows={(report.by_module || []).map((row) => ({ ...row, key: row.module }))}
            />
          </AdminPanel>

          <AdminPanel
            title="Who raised tickets"
            subtitle="Counted by role. A person with two roles is counted in each."
          >
            <ReportTable
              empty="No tickets in this range."
              columns={[
                { key: 'label', label: 'Role' },
                { key: 'tickets', label: 'Tickets', numeric: true },
              ]}
              rows={(report.raised_by_role || []).map((row) => ({ ...row, key: row.role }))}
            />
          </AdminPanel>

          <AdminPanel
            title="Who wrote staff replies"
            subtitle="Replies from someone other than the person who raised the ticket, when that person is staff."
          >
            <ReportTable
              empty="No staff replies in this range."
              columns={[
                { key: 'name', label: 'Name' },
                { key: 'roles', label: 'Roles', render: (row) => (row.roles || []).join(', ') },
                { key: 'replies', label: 'Replies', numeric: true },
                { key: 'tickets', label: 'Tickets', numeric: true },
                { key: 'first_replies', label: 'First replies', numeric: true },
              ]}
              rows={(report.staff_replies || []).map((row, index) => ({ ...row, key: `${row.name}-${index}` }))}
            />
          </AdminPanel>

          <AdminPanel
            title="Hours until the first reply"
            subtitle="Median hours until someone other than the raiser replies, by category."
          >
            <ReportTable
              columns={[
                { key: 'label', label: 'Category' },
                {
                  key: 'median_hours',
                  label: 'Median hours',
                  numeric: true,
                  render: (row) => dash(row.median_hours),
                },
                { key: 'tickets_with_reply', label: 'Tickets with a reply', numeric: true },
              ]}
              rows={(report.first_reply_hours || []).map((row) => ({ ...row, key: row.category }))}
            />
          </AdminPanel>

          <AdminPanel
            title="Waiting and aging"
            subtitle="Open tickets with no reply yet, and in-progress tickets older than 7 days and older than 30 days."
          >
            <ReportTable
              columns={[
                { key: 'label', label: 'Metric' },
                { key: 'count', label: 'Count', numeric: true },
              ]}
              rows={agingRows}
            />
          </AdminPanel>

          <AdminPanel
            title="Repeating questions"
            subtitle="One group per ticket, from words in the subject and the opening message. Still open means open or in progress."
          >
            <ReportTable
              columns={[
                { key: 'label', label: 'Type' },
                { key: 'total', label: 'All', numeric: true },
                { key: 'still_open', label: 'Still open', numeric: true },
              ]}
              rows={(report.question_groups || []).map((row) => ({ ...row, key: row.key }))}
            />
          </AdminPanel>
        </>
      ) : null}

      {!loading && !report && !loadError ? (
        <AdminEmptyState
          title="No tickets in this range yet."
          description="Would you like to try another set of dates?"
          action={
            <button type="button" className="admin-btn admin-btn--secondary" onClick={resetFilters}>
              Show this month
            </button>
          }
        />
      ) : null}

      <footer className="support-ticket-report__footer">
        <button
          type="button"
          className="admin-btn admin-btn--primary"
          onClick={downloadExcel}
          disabled={exporting || loading || !report}
        >
          {downloadLabel}
        </button>
      </footer>
    </div>
  )
}
