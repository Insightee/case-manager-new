/**
 * Layout wrapper for report builder screens.
 * sidebar: optional React node for left sidebar
 * topBar: optional React node for top action bar
 */
export function ClinicalAppShell({ sidebar, topBar, children, className = '' }) {
  return (
    <div className={`clinical-app-shell ${className}`.trim()}>
      {sidebar}
      <div className="clinical-app-shell__content">
        {topBar}
        <main className="clinical-app-shell__main">
          {children}
        </main>
      </div>
    </div>
  )
}
