export function InternalVsFamilyBanner({ variant = 'internal' }) {
  if (variant === 'family') {
    return (
      <p className="cp-hint" style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: 8, padding: '0.5rem 0.75rem' }}>
        Family update — visible to parents after case manager publishes this report.
      </p>
    )
  }
  return (
    <p className="cp-hint" style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.5rem 0.75rem' }}>
      Internal clinical note — not shared with parents unless included in a published family section.
    </p>
  )
}
