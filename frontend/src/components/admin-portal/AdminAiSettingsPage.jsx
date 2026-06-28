import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function AdminAiSettingsPage() {
  const [settings, setSettings] = useState(null)
  const [audit, setAudit] = useState([])

  const load = useCallback(async () => {
    const [s, a] = await Promise.all([
      apiFetch('/api/v1/admin/ai/settings'),
      apiFetch('/api/v1/admin/ai/audit'),
    ])
    setSettings(s)
    setAudit(a.items || [])
  }, [])

  useEffect(() => { load() }, [load])

  if (!settings) return <p>Loading AI settings…</p>

  return (
    <div className="admin-page" style={{ maxWidth: 960, margin: '0 auto', padding: '1rem' }}>
      <h1>AI Settings & Audit</h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.75rem' }}>
        <div><strong>AI enabled</strong><div>{String(settings.ai_enabled)}</div></div>
        <div><strong>Provider</strong><div>{settings.provider}</div></div>
        <div><strong>Insights model</strong><div>{settings.insights_model}</div></div>
        <div><strong>Daily budget (INR)</strong><div>{settings.daily_budget_inr || '—'}</div></div>
        <div><strong>Monthly budget (INR)</strong><div>{settings.monthly_budget_inr || '—'}</div></div>
        <div><strong>Generations this month</strong><div>{settings.generations_this_month}</div></div>
        <div><strong>Failed generations</strong><div>{settings.failed_generations}</div></div>
        <div><strong>Mock mode</strong><div>{String(settings.mock_mode)}</div></div>
      </div>

      <h2 style={{ marginTop: '1.5rem' }}>Recent generations</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
        <thead>
          <tr>
            <th align="left">Date</th>
            <th align="left">Feature</th>
            <th align="left">Provider</th>
            <th align="left">Case</th>
          </tr>
        </thead>
        <tbody>
          {audit.map((row) => (
            <tr key={row.id}>
              <td>{row.created_at?.slice(0, 10)}</td>
              <td>{row.feature}</td>
              <td>{row.provider}</td>
              <td>{row.case_id ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
