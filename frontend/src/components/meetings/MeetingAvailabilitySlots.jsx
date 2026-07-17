export function MeetingAvailabilitySlots({
  slots,
  loading,
  selectedTime,
  onSelectTime,
  onSelectDate,
  targetDate,
  label = 'Available slots',
}) {
  const availableSlots = Array.isArray(slots?.slots) ? slots.slots.filter((s) => s.available) : []
  const allBusy = slots && availableSlots.length === 0
  const altSuggestions = slots?.alternate_suggestions || []

  return (
    <div style={{ marginBottom: 14 }}>
      <p style={{ fontSize: '0.8rem', fontWeight: 600, color: '#475569', margin: '0 0 8px' }}>{label}</p>
      {loading ? (
        <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: 0 }}>Checking availability…</p>
      ) : slots ? (
        <>
          {allBusy ? (
            <div style={{ background: '#fef3c7', border: '1px solid #fde68a', borderRadius: 10, padding: '10px 12px', fontSize: '0.8rem', color: '#92400e', marginBottom: 8 }}>
              <strong>
                No slots available on{' '}
                {new Date(`${targetDate}T12:00:00`).toLocaleDateString('en-IN', {
                  weekday: 'long',
                  day: 'numeric',
                  month: 'short',
                })}
                .
              </strong>
              {altSuggestions.length > 0 ? (
                <>
                  <p style={{ margin: '6px 0 6px', fontWeight: 600 }}>Try one of these dates instead:</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {altSuggestions.map((alt) => (
                      <button
                        key={alt.date}
                        type="button"
                        style={{
                          border: '1px solid #fcd34d',
                          background: '#fffbeb',
                          borderRadius: 8,
                          padding: '5px 12px',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          color: '#78350f',
                        }}
                        onClick={() => {
                          onSelectDate?.(alt.date)
                          onSelectTime?.(alt.slots[0])
                        }}
                      >
                        {new Date(`${alt.date}T12:00:00`).toLocaleDateString('en-IN', {
                          weekday: 'short',
                          day: 'numeric',
                          month: 'short',
                        })}{' '}
                        · {alt.slots[0]}
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <p style={{ margin: '6px 0 0' }}>No availability in the next 7 days. Try another date or adjust attendees.</p>
              )}
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
                {slots.slots.map((s) => (
                  <button
                    key={s.time}
                    type="button"
                    title={s.available ? undefined : s.reason}
                    disabled={!s.available}
                    style={{
                      border: `2px solid ${selectedTime === s.time ? '#4f46e5' : s.available ? '#c7d2fe' : '#e2e8f0'}`,
                      background: selectedTime === s.time ? '#4f46e5' : s.available ? '#eef2ff' : '#f8fafc',
                      color: selectedTime === s.time ? '#fff' : s.available ? '#3730a3' : '#94a3b8',
                      borderRadius: 8,
                      padding: '6px 14px',
                      fontSize: '0.82rem',
                      fontWeight: 700,
                      cursor: s.available ? 'pointer' : 'not-allowed',
                      textDecoration: !s.available ? 'line-through' : 'none',
                    }}
                    onClick={() => onSelectTime?.(s.time)}
                  >
                    {s.time}
                  </button>
                ))}
              </div>
              {!selectedTime ? (
                <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: 0 }}>Tap an open slot to continue.</p>
              ) : null}
            </>
          )}
        </>
      ) : (
        <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: 0 }}>Select a date to see available slots.</p>
      )}
    </div>
  )
}
