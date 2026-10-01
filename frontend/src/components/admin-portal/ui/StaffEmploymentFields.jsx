const EMPLOYMENT_TYPES = [
  { value: '', label: 'Not set' },
  { value: 'PROBATION', label: 'Probation' },
  { value: 'CONSULTANT', label: 'Consultant' },
  { value: 'EMPLOYEE', label: 'Employee' },
]

export function StaffEmploymentFields({ value, onChange, disabled = false }) {
  const type = value.staff_employment_type || ''
  const showProbation = type === 'PROBATION'

  function set(field, next) {
    onChange({ ...value, [field]: next })
  }

  return (
    <div className="admin-form-grid" style={{ gridColumn: '1 / -1' }}>
      <p className="admin-muted" style={{ gridColumn: '1 / -1', margin: '0 0 4px', fontSize: '0.85rem' }}>
        Employment & leave (staff only — not used for therapists)
      </p>
      <label>
        Employment type
        <select
          className="admin-input"
          value={type}
          disabled={disabled}
          onChange={(e) => {
            const nextType = e.target.value
            onChange({
              ...value,
              staff_employment_type: nextType,
              staff_probation_months: nextType === 'PROBATION' ? value.staff_probation_months : '',
            })
          }}
        >
          {EMPLOYMENT_TYPES.map((opt) => (
            <option key={opt.value || 'empty'} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>
      {showProbation ? (
        <label>
          Probation period (months)
          <input
            className="admin-input"
            type="number"
            min={1}
            max={24}
            value={value.staff_probation_months ?? ''}
            disabled={disabled}
            onChange={(e) => set('staff_probation_months', e.target.value ? Number(e.target.value) : '')}
          />
        </label>
      ) : null}
      <label>
        Employment start date
        <input
          className="admin-input"
          type="date"
          value={value.staff_employment_start_date || ''}
          disabled={disabled}
          onChange={(e) => set('staff_employment_start_date', e.target.value || '')}
        />
      </label>
      <label>
        Leave credits (opening balance)
        <input
          className="admin-input"
          type="number"
          min={0}
          value={value.staff_leave_credit_balance ?? ''}
          disabled={disabled}
          onChange={(e) =>
            set('staff_leave_credit_balance', e.target.value === '' ? '' : Number(e.target.value))
          }
        />
      </label>
    </div>
  )
}

export function staffEmploymentPayload(value) {
  const payload = {}
  if (value.staff_employment_type) payload.staff_employment_type = value.staff_employment_type
  else if (value.staff_employment_type === '') payload.staff_employment_type = null
  if (value.staff_probation_months !== '' && value.staff_probation_months != null) {
    payload.staff_probation_months = Number(value.staff_probation_months)
  }
  if (value.staff_employment_start_date) {
    payload.staff_employment_start_date = value.staff_employment_start_date
  }
  if (value.staff_leave_credit_balance !== '' && value.staff_leave_credit_balance != null) {
    payload.staff_leave_credit_balance = Number(value.staff_leave_credit_balance)
  }
  return payload
}
