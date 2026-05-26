import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { AdminPageHeader, AdminPanel } from './ui/index.js'
import { AdminCaseAllotmentWizard } from './AdminCaseAllotmentWizard.jsx'
import { AdminCasesPipelineTable } from './AdminCasesPipelineTable.jsx'
import { caseStateFromLegacyStatus, defaultPipelineFilters } from '../../lib/adminCasePipeline.js'

export function AdminCasesPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { can, isViewOnly } = useAuth()
  const [showCreate, setShowCreate] = useState(false)
  const [initialFilters, setInitialFilters] = useState(() => defaultPipelineFilters())

  const canCreateCase = can('case.create') && !isViewOnly

  useEffect(() => {
    if (searchParams.get('allot') === '1' && canCreateCase) {
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
        eyebrow="Case management"
        title="Cases"
        subtitle="Action queue first — filter by status, case manager, therapist, client, and dates. Use row actions to allot, assign, review, or open the case file."
        actions={
          canCreateCase ? (
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setShowCreate((v) => !v)}>
              {showCreate ? 'Close form' : '+ New case'}
            </button>
          ) : null
        }
      />

      {showCreate && canCreateCase ? (
        <AdminCaseAllotmentWizard
          onComplete={async (created) => {
            setShowCreate(false)
            if (created?.id) navigate(`/admin/cases/${created.id}`)
          }}
          onCancel={() => setShowCreate(false)}
        />
      ) : null}

      <AdminPanel title="Case board" padded={false}>
        <div className="admin-panel__body" style={{ padding: '12px 16px 16px' }}>
          <AdminCasesPipelineTable initialFilters={initialFilters} />
        </div>
      </AdminPanel>
    </div>
  )
}
