import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { AdminEmptyState, AdminSearchInput, AdminToolbar } from './ui/index.js'
import { AdminCaseAssignDrawer } from './AdminCaseAssignDrawer.jsx'
import { AdminBulkAssignModal } from './AdminBulkAssignModal.jsx'
import './admin-cases-kanban.css'

const VISIBLE_COLUMNS = [
  'pending_allotment',
  'needs_therapist',
  'reassignment',
  'reports_logs',
  'iep',
  'compliance',
  'active',
]

const DROP_ACTION_COLUMNS = new Set(['pending_allotment', 'needs_therapist', 'reassignment', 'closed'])
const BULK_SELECT_COLUMNS = new Set(['needs_therapist', 'reassignment'])

function countTone(tone) {
  if (tone === 'danger') return 'danger'
  if (tone === 'warning') return 'warning'
  if (tone === 'success') return 'success'
  return ''
}

function CaseKanbanCardContent({ card }) {
  const flags = []
  if (card.missing_logs > 0) flags.push({ label: `${card.missing_logs} log(s)`, warn: true })
  if (card.reports_under_review > 0) flags.push({ label: `${card.reports_under_review} report(s)`, warn: true })
  if (!card.has_iep) flags.push({ label: 'No IEP', warn: true })
  else if (!card.iep_acknowledged) flags.push({ label: 'IEP pending ack', warn: true })
  if (card.open_tickets > 0) flags.push({ label: `${card.open_tickets} ticket(s)`, danger: true })
  if (card.open_incidents > 0) flags.push({ label: `${card.open_incidents} incident(s)`, danger: true })

  return (
    <>
      <p className="admin-case-card__code">{card.case_code}</p>
      <p className="admin-case-card__child">{card.child_name || '—'}</p>
      <p className="admin-case-card__meta">
        {card.service_type}
        {card.therapist_name ? ` · ${card.therapist_name}` : ''}
        {card.assignment_end_date ? ` · ends ${card.assignment_end_date}` : ''}
      </p>
      {card.next_action ? <p className="admin-case-card__action">{card.next_action}</p> : null}
      {flags.length > 0 ? (
        <div className="admin-case-card__flags">
          {flags.map((f) => (
            <span
              key={f.label}
              className={`admin-case-card__flag ${f.danger ? 'admin-case-card__flag--danger' : f.warn ? 'admin-case-card__flag--warn' : ''}`}
            >
              {f.label}
            </span>
          ))}
        </div>
      ) : null}
    </>
  )
}

function DraggableCaseCard({ card, selectable, selected, onToggleSelect, dragDisabled }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `case-${card.id}`,
    data: { card },
    disabled: dragDisabled,
  })

  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`, opacity: isDragging ? 0.5 : 1 }
    : undefined

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`admin-case-card admin-case-card--draggable ${isDragging ? 'admin-case-card--dragging' : ''}`}
    >
      {selectable ? (
        <label className="admin-case-card__select" onClick={(e) => e.stopPropagation()}>
          <input type="checkbox" checked={selected} onChange={() => onToggleSelect(card.id)} />
        </label>
      ) : null}
      <div className="admin-case-card__drag-handle" {...listeners} {...attributes} title="Drag to another column">
        ⋮⋮
      </div>
      <Link to={`/admin/cases/${card.id}`} className="admin-case-card__link">
        <CaseKanbanCardContent card={card} />
      </Link>
    </div>
  )
}

function DroppableColumn({ col, children, isDropTarget }) {
  const { setNodeRef, isOver } = useDroppable({
    id: col.id,
    data: { columnId: col.id },
  })

  return (
    <section
      ref={setNodeRef}
      className={`admin-cases-kanban__column ${isDropTarget && isOver ? 'admin-cases-kanban__column--over' : ''}`}
      role="listitem"
      aria-label={col.title}
    >
      {children}
    </section>
  )
}

export function AdminCasesKanban({ productFilter = 'all' }) {
  const { can, canWriteProduct, isViewOnly } = useAuth()
  const navigate = useNavigate()
  const [board, setBoard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [hideClosed, setHideClosed] = useState(true)
  const [activeCard, setActiveCard] = useState(null)
  const [assignCard, setAssignCard] = useState(null)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [toast, setToast] = useState('')

  const canAssignGlobal = can('case.assign') && !isViewOnly
  const canDnD = canAssignGlobal

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }))

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch('/api/v1/admin/cases/pipeline')
      setBoard(data)
    } catch (err) {
      setError(err.message || 'Could not load pipeline')
      setBoard(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(''), 4000)
    return () => clearTimeout(t)
  }, [toast])

  const columns = useMemo(() => {
    if (!board?.columns) return []
    const q = search.trim().toLowerCase()
    const colIds = hideClosed ? VISIBLE_COLUMNS : [...VISIBLE_COLUMNS, 'closed']
    return board.columns
      .filter((col) => colIds.includes(col.id))
      .map((col) => {
        let cases = col.cases
        if (productFilter !== 'all') {
          cases = cases.filter((c) => c.product_module === productFilter)
        }
        if (q) {
          cases = cases.filter((c) => {
            const hay = `${c.case_code} ${c.child_name} ${c.service_type} ${c.therapist_name || ''}`.toLowerCase()
            return hay.includes(q)
          })
        }
        return { ...col, cases, count: cases.length }
      })
  }, [board, search, hideClosed, productFilter])

  const selectedCards = useMemo(() => {
    const all = columns.flatMap((c) => c.cases)
    return all.filter((c) => selectedIds.has(c.id))
  }, [columns, selectedIds])

  function toggleSelect(id) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function selectAllInColumn(col) {
    if (!BULK_SELECT_COLUMNS.has(col.id)) return
    setSelectedIds((prev) => {
      const next = new Set(prev)
      col.cases.forEach((c) => next.add(c.id))
      return next
    })
  }

  async function closeCase(card) {
    if (!window.confirm(`Close case ${card.case_code}?`)) return
    try {
      await apiFetch(`/api/v1/cases/${card.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'CLOSED' }),
      })
      await load()
    } catch (err) {
      setToast(err.message || 'Could not close case')
    }
  }

  function handleDragEnd(event) {
    const { active, over } = event
    setActiveCard(null)
    if (!over || !canDnD) return

    const card = active.data.current?.card
    const targetColumn = over.id
    if (!card || !DROP_ACTION_COLUMNS.has(targetColumn)) {
      if (over.id && !DROP_ACTION_COLUMNS.has(over.id)) {
        setToast('This column is read-only — open the case for reports, IEP, or compliance work.')
      }
      return
    }

    if (targetColumn === 'needs_therapist' || targetColumn === 'reassignment') {
      setAssignCard(card)
      return
    }
    if (targetColumn === 'pending_allotment') {
      navigate(`/admin/cases/${card.id}?tab=assignments`)
      return
    }
    if (targetColumn === 'closed') {
      closeCase(card)
    }
  }

  const totalVisible = columns.reduce((n, c) => n + c.cases.length, 0)

  if (loading) {
    return <p className="admin-muted">Loading pipeline…</p>
  }

  if (error) {
    return (
      <div>
        <p className="admin-alert admin-alert--error">{error}</p>
        <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={load}>
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="admin-cases-kanban">
      <AdminToolbar>
        <AdminSearchInput value={search} onChange={setSearch} placeholder="Search board…" />
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.8125rem', color: '#64748b' }}>
          <input type="checkbox" checked={hideClosed} onChange={(e) => setHideClosed(e.target.checked)} />
          Hide closed
        </label>
        {canAssignGlobal && selectedIds.size > 0 ? (
          <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setBulkOpen(true)}>
            Bulk assign ({selectedIds.size})
          </button>
        ) : null}
        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={load}>
          Refresh
        </button>
      </AdminToolbar>

      {toast ? <p className="admin-alert admin-alert--warning" style={{ marginBottom: 12 }}>{toast}</p> : null}

      {canDnD ? (
        <p className="admin-muted" style={{ fontSize: '0.8rem', marginBottom: 12 }}>
          Drag cards to Needs therapist, Reassignment, Pending allotment, or Closed to take action. Other columns are
          informational.
        </p>
      ) : null}

      {totalVisible === 0 ? (
        <AdminEmptyState title="No cases on the board" description="Adjust search or filters, or create a new case." />
      ) : (
        <DndContext
          sensors={sensors}
          onDragStart={(e) => setActiveCard(e.active.data.current?.card)}
          onDragEnd={handleDragEnd}
          onDragCancel={() => setActiveCard(null)}
        >
          <div className="admin-cases-kanban__board" role="list">
            {columns.map((col) => {
              const ColumnWrap = canDnD ? DroppableColumn : ({ children }) => (
                <section className="admin-cases-kanban__column" role="listitem" aria-label={col.title}>
                  {children}
                </section>
              )
              return (
                <ColumnWrap key={col.id} col={col} isDropTarget={canDnD && DROP_ACTION_COLUMNS.has(col.id)}>
                  <div className="admin-cases-kanban__column-head">
                    <h3 className="admin-cases-kanban__column-title">{col.title}</h3>
                    <span className={`admin-cases-kanban__count admin-cases-kanban__count--${countTone(col.tone)}`}>
                      {col.count}
                    </span>
                  </div>
                  {canAssignGlobal && BULK_SELECT_COLUMNS.has(col.id) && col.cases.length > 0 ? (
                    <button
                      type="button"
                      className="admin-btn admin-btn--ghost admin-btn--sm"
                      style={{ marginBottom: 8, width: '100%' }}
                      onClick={() => selectAllInColumn(col)}
                    >
                      Select all
                    </button>
                  ) : null}
                  <div className="admin-cases-kanban__cards">
                    {col.cases.length === 0 ? (
                      <p className="admin-muted" style={{ fontSize: '0.75rem', margin: 0 }}>
                        —
                      </p>
                    ) : canDnD ? (
                      col.cases.map((card) => (
                        <DraggableCaseCard
                          key={card.id}
                          card={card}
                          dragDisabled={!canWriteProduct(card.product_module)}
                          selectable={
                            canAssignGlobal &&
                            canWriteProduct(card.product_module) &&
                            BULK_SELECT_COLUMNS.has(col.id)
                          }
                          selected={selectedIds.has(card.id)}
                          onToggleSelect={toggleSelect}
                        />
                      ))
                    ) : (
                      col.cases.map((card) => (
                        <Link key={card.id} to={`/admin/cases/${card.id}`} className="admin-case-card">
                          <CaseKanbanCardContent card={card} />
                        </Link>
                      ))
                    )}
                  </div>
                </ColumnWrap>
              )
            })}
          </div>
          {canDnD ? (
            <DragOverlay>
              {activeCard ? (
                <div className="admin-case-card admin-case-card--overlay">
                  <CaseKanbanCardContent card={activeCard} />
                </div>
              ) : null}
            </DragOverlay>
          ) : null}
        </DndContext>
      )}

      <AdminCaseAssignDrawer
        open={!!assignCard}
        caseCard={assignCard}
        onClose={() => setAssignCard(null)}
        onDone={() => {
          setAssignCard(null)
          load()
        }}
      />

      <AdminBulkAssignModal
        open={bulkOpen}
        caseCards={selectedCards}
        onClose={() => setBulkOpen(false)}
        onDone={() => {
          setSelectedIds(new Set())
          setBulkOpen(false)
          load()
        }}
      />
    </div>
  )
}
