import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getApiBaseUrl, getTokens } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { isFinanceDeskUser } from '../../lib/financeDesk.js'
import { AdminPageHeader, AdminPanel } from './ui/index.js'
import { AdminCaseAllotmentWizard } from './AdminCaseAllotmentWizard.jsx'
import { AdminCasesPipelineTable } from './AdminCasesPipelineTable.jsx'
import { caseStateFromLegacyStatus, defaultPipelineFilters } from '../../lib/adminCasePipeline.js'

async function downloadCaseRecordsExport() {
  const { access } = getTokens()
  const res = await fetch(`${getApiBaseUrl()}/api/v1/admin/cases/export/records.csv`, {
    headers: access ? { Authorization: `Bearer ${access}` } : {},
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(detail || 'Could not export case records.')
  }
  const blob = await res.blob()
  const stamp = new Date().toISOString().slice(0, 10)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `case-records-${stamp}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

export function AdminCasesPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { can, isViewOnly, user } = useAuth()
  const financeDesk = isFinanceDeskUser(user)
  const canCreateCase = can('case.create') && !isViewOnly && !financeDesk
  const [showCreate, setShowCreate] = useState(false)
  const [wizardKey, setWizardKey] = useState(0)
  const [initialFilters, setInitialFilters] = useState(() => defaultPipelineFilters())
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')

  useEffect(() => {
    if (searchParams.get('allot') === '1' && canCreateCase) {
      setWizardKey((k) => k + 1)
      setShowCreate(true)
    }
    const status = searchParams.get('status')
    const queue = searchParams.get('queue')
    const next = defaultPipelineFilters()
    if (status) next.caseState = caseStateFromLegacyStatus(status)
    if (queue) next.queue = queue
    if (status || queue) setInitialFilters(next)
  }, [searchParams, canCreateCase])

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow={financeDesk ? 'Finance' : 'Case management'}
        title="Cases"
        subtitle={
          financeDesk
            ? 'View-only caseload for payout and invoice cross-check. Open a case for overview, activity, session dates, and billing.'
            : 'Full caseload by default — filter by status, case manager, therapist, client, and dates. Use row actions to allot, assign, review, or open the case file.'
        }
        actions={
          canCreateCase ? (
            <button
              type="button"
              className="admin-btn admin-btn--primary admin-btn--sm"
              onClick={() => {
                if (showCreate) {
                  setShowCreate(false)
                  return
                }
                setWizardKey((k) => k + 1)
                setShowCreate(true)
              }}
            >
              {showCreate ? 'Close form' : '+ New case'}
            </button>
          ) : null
        }
      />

      {showCreate && canCreateCase ? (
        <AdminCaseAllotmentWizard
          key={wizardKey}
          onComplete={async (created) => {
            setShowCreate(false)
            if (created?.id) navigate(`/admin/cases/${created.id}`)
          }}
          onCancel={() => setShowCreate(false)}
        />
      ) : null}

      <AdminPanel
        title="Case board"
        className="admin-panel--case-board"
        padded={false}
        actions={
          financeDesk ? null : (
          <button
            type="button"
            className="admin-btn admin-btn--ghost admin-btn--sm"
            disabled={exporting}
            onClick={() => {
              setExportError('')
              setExporting(true)
              downloadCaseRecordsExport()
                .catch((err) => setExportError(err.message || 'Could not export case records.'))
                .finally(() => setExporting(false))
            }}
          >
            {exporting ? 'Exporting…' : 'Export records'}
          </button>
          )
        }
      >
        {exportError ? (
          <p className="admin-alert admin-alert--warning" style={{ margin: '12px 16px 0' }}>
            {exportError}
          </p>
        ) : null}
        <div className="admin-panel__body admin-panel__body--case-board">
          <AdminCasesPipelineTable initialFilters={initialFilters} />
        </div>
      </AdminPanel>
    </div>
  )
}
