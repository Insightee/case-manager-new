import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function TherapistAssignedCasesPanel() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch('/api/v1/cases?assigned=true')
      .then(setCases)
      .catch(() => setCases([]))
      .finally(() => setLoading(false))
  }, [])

  const withAddress = cases.filter((c) => c.service_address?.formatted)

  if (loading) return <p className="text-sm text-slate-500">Loading assigned cases…</p>
  if (!withAddress.length) return null

  return (
    <section className="mb-6 rounded-2xl border border-[#E2E8F0] bg-white p-4 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">Homecare visit addresses</h2>
      <ul className="mt-3 space-y-3">
        {withAddress.map((c) => (
          <li key={c.id} className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-sm">
            <p className="font-semibold text-slate-800">
              {c.case_code} · {c.child_name}
            </p>
            <p className="mt-1 text-slate-600">{c.service_address.formatted}</p>
            {c.maps_url ? (
              <a
                href={c.maps_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-block font-semibold text-indigo-600 hover:underline"
              >
                Open in Google Maps
              </a>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  )
}
