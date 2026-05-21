import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

function initials(name) {
  if (!name) return '?'
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join('')
}

const AVATAR_COLORS = [
  'bg-indigo-100 text-indigo-700',
  'bg-violet-100 text-violet-700',
  'bg-teal-100 text-teal-700',
  'bg-rose-100 text-rose-700',
  'bg-amber-100 text-amber-700',
  'bg-sky-100 text-sky-700',
]

function avatarColor(id) {
  return AVATAR_COLORS[Number(id) % AVATAR_COLORS.length]
}

export function AdminTherapistPicker({
  caseId,
  productModule,
  value,
  onChange,
  disabled,
  mode = 'allotment',
}) {
  const [therapists, setTherapists] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    const url =
      mode === 'allotment' && productModule
        ? `/api/v1/admin/allotment/therapists?product_module=${encodeURIComponent(productModule)}`
        : caseId
          ? `/api/v1/booking/therapists?case_id=${caseId}`
          : null
    if (!url) {
      setTherapists([])
      setLoading(false)
      return
    }
    apiFetch(url)
      .then(setTherapists)
      .catch(() => setTherapists([]))
      .finally(() => setLoading(false))
  }, [caseId, productModule, mode])

  // Card-based picker for allotment — gives admin a richer view
  if (mode === 'allotment') {
    if (loading) {
      return (
        <div className="mt-2 flex items-center gap-2 text-sm text-slate-500">
          <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          Loading therapists…
        </div>
      )
    }
    if (!therapists.length) {
      return (
        <p className="mt-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          No therapists are approved for this module yet.
        </p>
      )
    }
    return (
      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {therapists.map((t) => {
          const tid = String(t.therapist_user_id)
          const name = t.therapist_name || t.full_name || `Therapist #${tid}`
          const selected = value === tid
          return (
            <button
              key={tid}
              type="button"
              disabled={disabled}
              onClick={() => onChange(selected ? '' : tid)}
              className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-all ${
                selected
                  ? 'border-indigo-500 bg-indigo-50 shadow-sm ring-1 ring-indigo-400'
                  : 'border-slate-200 bg-white hover:border-indigo-300 hover:bg-slate-50'
              } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <span
                className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-sm font-bold ${avatarColor(tid)}`}
              >
                {initials(name)}
              </span>
              <span className="flex-1 min-w-0">
                <span className="block truncate text-sm font-semibold text-slate-800">{name}</span>
                <span className="block text-xs text-slate-400">ID #{tid}</span>
              </span>
              {selected && (
                <svg className="h-4 w-4 flex-shrink-0 text-indigo-600" viewBox="0 0 20 20" fill="currentColor">
                  <path
                    fillRule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414L8.414 15l-4.121-4.121a1 1 0 111.414-1.414L8.414 12.172l7.293-7.293a1 1 0 011.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
              )}
            </button>
          )
        })}
      </div>
    )
  }

  // Default dropdown for other modes (assigned, etc.)
  return (
    <select
      className="admin-input"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled || loading || (mode === 'assigned' && !caseId)}
    >
      <option value="">{loading ? 'Loading therapists…' : 'Select therapist…'}</option>
      {therapists.map((t) => (
        <option key={t.therapist_user_id} value={String(t.therapist_user_id)}>
          {t.therapist_name || t.full_name || `Therapist #${t.therapist_user_id}`}
        </option>
      ))}
    </select>
  )
}
