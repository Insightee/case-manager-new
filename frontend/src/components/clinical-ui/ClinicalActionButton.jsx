/** Primary / secondary / ghost buttons using existing app colours. */
export function ClinicalActionButton({
  children,
  variant = 'primary',
  className = '',
  as: Tag = 'button',
  type = 'button',
  ...props
}) {
  const cls = {
    primary: 'clinical-btn-primary',
    secondary: 'clinical-btn-secondary',
    ghost: 'clinical-btn-ghost',
  }[variant] || 'clinical-btn-primary'

  return (
    <Tag className={`${cls} ${className}`.trim()} type={Tag === 'button' ? type : undefined} {...props}>
      {children}
    </Tag>
  )
}
