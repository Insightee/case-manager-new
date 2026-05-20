import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

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
