/** Horizontal case tabs — underline active state, mobile scroll. */
export function ClinicalTabs({ tabs = [], activeTab, onTabChange, className = '', ariaLabel = 'Case sections' }) {
  return (
    <nav className={`clinical-tabs cp-tabs ic-case-tabs ${className}`.trim()} aria-label={ariaLabel}>
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`clinical-tabs__btn ic-case-tabs__btn cp-tabs__btn${activeTab === t.id ? ' is-active' : ''}`}
          onClick={() => onTabChange(t.id)}
        >
          <span className="ic-case-tabs__label-full">{t.label}</span>
          {t.shortLabel ? <span className="ic-case-tabs__label-short">{t.shortLabel}</span> : null}
        </button>
      ))}
    </nav>
  )
}

/** @deprecated Use ClinicalTabs */
export { ClinicalTabs as ClinicalTabBar }
