/** Inline styles so Send stays visible in admin, therapist, and parent portals. */
export const logCommentSendButtonStyle = (disabled = false) => ({
  flexShrink: 0,
  padding: '8px 18px',
  fontSize: '0.8125rem',
  fontWeight: 600,
  borderRadius: 8,
  border: 'none',
  background: disabled ? '#a5b4fc' : '#4f46e5',
  color: '#fff',
  cursor: disabled ? 'not-allowed' : 'pointer',
  opacity: disabled ? 0.85 : 1,
})

export const logCommentFieldStyle = {
  width: '100%',
  boxSizing: 'border-box',
  padding: '8px 10px',
  fontSize: '0.8125rem',
  borderRadius: 6,
  border: '1px solid #cbd5e1',
  outline: 'none',
  background: '#fff',
}
