import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function AdminTherapistPicker({ caseId, value, onChange, disabled }) {
  const [therapists, setTherapists] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!caseId) {
      setTherapists([])
      return
    }
    setLoading(true)
    apiFetch(`/api/v1/booking/therapists?case_id=${caseId}`)
      .then(setTherapists)
      .catch(() => setTherapists([]))
      .finally(() => setLoading(false))
  }, [caseId])

  return (
    <select
      className="admin-input"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled || !caseId || loading}
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
