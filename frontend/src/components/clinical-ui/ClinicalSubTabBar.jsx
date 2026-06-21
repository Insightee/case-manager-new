/** Report section pill sub-tabs — compact pill active state. */
export function ClinicalSubTabs({ tabs = [], activeTab, onTabChange, className = '', ariaLabel = 'Report sections' }) {
  return (
    <nav className={`clinical-subtabs cp-subtabs ${className}`.trim()} aria-label={ariaLabel}>
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`clinical-subtabs__btn cp-subtabs__btn${activeTab === t.id ? ' is-active' : ''}`}
          onClick={() => onTabChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  )
}

/** @deprecated Use ClinicalSubTabs */
export { ClinicalSubTabs as ClinicalSubTabBar }
