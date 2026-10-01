import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { formatTimestampDateIN } from '../../lib/datetime.js'
import { AdminEmptyState, AdminPageHeader, AdminPanel, StatusBadge } from './ui/index.js'
import {
  ACCESS_TOKEN_OPTIONS,
  INFO_ACCESS,
  KEY_TTL_OPTIONS,
  WEBHOOK_EVENTS,
  accessTokenLabel,
  emptyKeyDraft,
  emptyWebhookDraft,
  infoLabel,
  integrationApiOrigin,
  keyDraftFromClient,
  keyPayloadFromDraft,
  keyTtlLabel,
  mcpConnectionSnippet,
  scopesFromDraft,
  tokenRequestSnippet,
  validateKeyDraft,
  validateWebhookDraft,
} from '../../lib/integrationDesk.js'
import { IntegrationCaseGrantPicker } from './IntegrationCaseGrantPicker.jsx'
import './admin-integrations.css'

const TABS = [
  { id: 'keys', label: 'API keys' },
  { id: 'webhooks', label: 'Webhooks' },
  { id: 'mcp', label: 'MCP' },
]

function AccessSwitch({ id, checked, onChange, label, hint, badge }) {
  return (
    <div className="integrations-switch">
      <div className="integrations-switch__copy">
        <label htmlFor={id}>{label}</label>
        {badge ? <span className="integrations-pill integrations-pill--quiet">{badge}</span> : null}
        {hint ? <p>{hint}</p> : null}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        className={`integrations-switch__control${checked ? ' is-on' : ''}`}
        onClick={() => onChange(!checked)}
      >
        <span />
      </button>
    </div>
  )
}

function CopyButton({ value, label = 'Copy' }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      className="admin-btn admin-btn--secondary admin-btn--sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value)
          setCopied(true)
          window.setTimeout(() => setCopied(false), 1600)
        } catch {
          setCopied(false)
        }
      }}
    >
      {copied ? 'Copied' : label}
    </button>
  )
}

function SecretReveal({ reveal, onClose }) {
  if (!reveal) return null
  return (
    <div className="integrations-secret" role="status">
      <p className="integrations-note">
        Store this secret now. InsighteCase will not show it again. Use it only to request a short-lived access token.
      </p>
      <dl>
        <dt>Client ID</dt>
        <dd>
          <code>{reveal.client_id}</code>
          <CopyButton value={reveal.client_id} />
        </dd>
        <dt>Client secret</dt>
        <dd>
          <code>{reveal.client_secret}</code>
          <CopyButton value={reveal.client_secret} />
        </dd>
      </dl>
      <div className="integrations-sheet__actions" style={{ marginTop: 12 }}>
        <button type="button" className="admin-btn admin-btn--primary" onClick={onClose}>
          I've stored this key
        </button>
      </div>
    </div>
  )
}

export function AdminIntegrationsPage() {
  const { can } = useAuth()
  const allowed = can('admin.override')
  const [tab, setTab] = useState('keys')
  const [clients, setClients] = useState([])
  const [webhooks, setWebhooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [sheet, setSheet] = useState(null)
  const [draft, setDraft] = useState(emptyKeyDraft)
  const [guidance, setGuidance] = useState('')
  const [saving, setSaving] = useState(false)
  const [reveal, setReveal] = useState(null)
  const [webhookSheet, setWebhookSheet] = useState(false)
  const [webhookDraft, setWebhookDraft] = useState(emptyWebhookDraft)
  const [webhookGuidance, setWebhookGuidance] = useState('')
  const [webhookReveal, setWebhookReveal] = useState(null)
  const [confirmRevokeId, setConfirmRevokeId] = useState(null)
  const origin = integrationApiOrigin()

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const [keyRows, hookRows] = await Promise.all([
        apiFetch('/api/v1/admin/integration-clients'),
        apiFetch('/api/v1/admin/integration-webhooks'),
      ])
      setClients(Array.isArray(keyRows) ? keyRows : [])
      setWebhooks(Array.isArray(hookRows) ? hookRows : [])
    } catch (err) {
      setLoadError(err.message || 'We could not load integrations just now. You can try again in a moment.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!allowed) {
      setLoading(false)
      return
    }
    void load()
  }, [allowed, load])

  const activeClients = clients.filter((client) => client.status === 'active')
  const kpis = useMemo(
    () => [
      { label: 'Active keys', value: activeClients.length },
      { label: 'Write enabled', value: activeClients.filter((client) => client.allow_write).length },
      { label: 'Webhooks', value: webhooks.filter((hook) => hook.status === 'active').length },
      { label: 'MCP on', value: activeClients.filter((client) => client.mcp_enabled).length },
    ],
    [activeClients, webhooks],
  )

  const openCreate = () => {
    setReveal(null)
    setGuidance('')
    setDraft(emptyKeyDraft())
    setSheet({ mode: 'create' })
  }

  const openEdit = (client) => {
    setReveal(null)
    setGuidance('')
    setDraft(keyDraftFromClient(client))
    setSheet({ mode: 'edit', id: client.id, signals: client.recent_signals || [] })
    apiFetch(`/api/v1/admin/integration-clients/${client.id}`)
      .then((detail) => {
        setDraft(keyDraftFromClient(detail))
        setSheet({ mode: 'edit', id: client.id, signals: detail.recent_signals || [] })
      })
      .catch(() => {})
  }

  const patchDraft = (partial) => setDraft((current) => ({ ...current, ...partial }))

  const toggleInfo = (id) => {
    setDraft((current) => {
      const has = current.infoAccess.includes(id)
      return {
        ...current,
        infoAccess: has ? current.infoAccess.filter((item) => item !== id) : [...current.infoAccess, id],
      }
    })
  }

  const saveKey = async () => {
    const message = validateKeyDraft(draft)
    if (message) {
      setGuidance(message)
      return
    }
    setGuidance('')
    setSaving(true)
    const payload = keyPayloadFromDraft(draft)
    const optimisticId = sheet?.mode === 'edit' ? sheet.id : `tmp-${Date.now()}`
    const optimistic = {
      id: optimisticId,
      name: payload.name,
      status: 'active',
      allow_read: payload.allow_read,
      allow_write: payload.allow_write,
      info_access: payload.info_access,
      access_token_minutes: payload.access_token_minutes,
      key_ttl_days: payload.key_ttl_days,
      mcp_enabled: payload.mcp_enabled,
      case_ids: payload.case_ids,
      scopes: scopesFromDraft(draft),
      public_client_id: sheet?.mode === 'edit'
        ? clients.find((client) => client.id === sheet.id)?.public_client_id
        : 'Saving…',
    }
    setClients((current) => {
      if (sheet?.mode === 'edit') return current.map((client) => (client.id === sheet.id ? { ...client, ...optimistic } : client))
      return [optimistic, ...current]
    })
    try {
      const saved = sheet?.mode === 'edit'
        ? await apiFetch(`/api/v1/admin/integration-clients/${sheet.id}`, {
            method: 'PATCH',
            body: JSON.stringify(payload),
          })
        : await apiFetch('/api/v1/admin/integration-clients', {
            method: 'POST',
            body: JSON.stringify(payload),
          })
      setClients((current) => {
        const withoutTemp = current.filter((client) => client.id !== optimisticId)
        const next = withoutTemp.filter((client) => client.id !== saved.id)
        return [saved, ...next]
      })
      if (saved.client_secret) {
        setReveal({ client_id: saved.client_id, client_secret: saved.client_secret })
      } else {
        setSheet(null)
      }
    } catch (err) {
      setGuidance(err.message || 'We still need a few details before we can save this key.')
      void load()
    } finally {
      setSaving(false)
    }
  }

  const rotateKey = async (client) => {
    setSaving(true)
    setGuidance('')
    try {
      const saved = await apiFetch(`/api/v1/admin/integration-clients/${client.id}/rotate-secret`, { method: 'POST' })
      setReveal({ client_id: saved.client_id, client_secret: saved.client_secret })
      setSheet({ mode: 'edit', id: client.id })
      setDraft(keyDraftFromClient(client))
      void load()
    } catch (err) {
      setLoadError(err.message || 'We could not rotate that key just now.')
    } finally {
      setSaving(false)
    }
  }

  const revokeKey = async (client) => {
    if (confirmRevokeId !== client.id) {
      setConfirmRevokeId(client.id)
      return
    }
    setClients((current) => current.map((row) => (row.id === client.id ? { ...row, status: 'revoked' } : row)))
    setConfirmRevokeId(null)
    try {
      const saved = await apiFetch(`/api/v1/admin/integration-clients/${client.id}/revoke`, { method: 'POST' })
      setClients((current) => current.map((row) => (row.id === saved.id ? saved : row)))
    } catch (err) {
      setLoadError(err.message || 'We could not revoke that key just now.')
      void load()
    }
  }

  const saveWebhook = async () => {
    const message = validateWebhookDraft(webhookDraft)
    if (message) {
      setWebhookGuidance(message)
      return
    }
    setWebhookGuidance('')
    setSaving(true)
    try {
      const saved = await apiFetch('/api/v1/admin/integration-webhooks', {
        method: 'POST',
        body: JSON.stringify({
          integration_client_id: Number(webhookDraft.integrationClientId),
          url: webhookDraft.url.trim(),
          events: webhookDraft.events,
        }),
      })
      setWebhooks((current) => [saved, ...current.filter((hook) => hook.id !== saved.id)])
      setWebhookReveal({ signing_secret: saved.signing_secret, url: saved.url })
    } catch (err) {
      setWebhookGuidance(err.message || 'Looks like we still need a few details before we can save this webhook.')
    } finally {
      setSaving(false)
    }
  }

  const rotateWebhook = async (hook) => {
    setSaving(true)
    setWebhookGuidance('')
    try {
      const saved = await apiFetch(`/api/v1/admin/integration-webhooks/${hook.id}/rotate-secret`, { method: 'POST' })
      setWebhookDraft({
        integrationClientId: String(hook.integration_client_id),
        url: hook.url,
        events: hook.events || [],
        status: hook.status,
      })
      setWebhookReveal({ signing_secret: saved.signing_secret, url: saved.url })
      setWebhookSheet(true)
    } catch (err) {
      setLoadError(err.message || 'We could not rotate that webhook secret just now.')
    } finally {
      setSaving(false)
    }
  }

  const toggleWebhook = async (hook) => {
    const nextStatus = hook.status === 'active' ? 'paused' : 'active'
    setWebhooks((current) => current.map((row) => (row.id === hook.id ? { ...row, status: nextStatus } : row)))
    try {
      const saved = await apiFetch(`/api/v1/admin/integration-webhooks/${hook.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      })
      setWebhooks((current) => current.map((row) => (row.id === saved.id ? saved : row)))
    } catch (err) {
      setLoadError(err.message || 'We could not update that webhook just now.')
      void load()
    }
  }

  if (!allowed) {
    return (
      <div className="admin-page integrations">
        <AdminPageHeader
          eyebrow="Super admin"
          title="Integrations"
          subtitle="API keys, webhooks, and MCP access for this project."
        />
        <AdminPanel>
          <AdminEmptyState
            title="Super admin access required"
            description="Integrations are available to super admin accounts only."
          />
        </AdminPanel>
      </div>
    )
  }

  const previewScopes = scopesFromDraft(draft)
  const footerLabel = tab === 'webhooks' ? 'New webhook' : 'New API key'
  const onFooter = () => {
    if (tab === 'webhooks') {
      setWebhookReveal(null)
      setWebhookGuidance('')
      setWebhookDraft({
        ...emptyWebhookDraft(),
        integrationClientId: activeClients[0] ? String(activeClients[0].id) : '',
      })
      setWebhookSheet(true)
      return
    }
    openCreate()
  }

  return (
    <div className="admin-page integrations">
      <AdminPageHeader
        eyebrow="Super admin"
        title="Integrations"
        subtitle="Issue an API key, choose what it can read or write, and connect webhooks or MCP. Secrets are shown once."
        actions={
          <button type="button" className="admin-btn admin-btn--primary" onClick={openCreate}>
            New API key
          </button>
        }
      />

      <section className="integrations-kpis" aria-label="Integration summary">
        {kpis.map((kpi) => (
          <article key={kpi.label} className="integrations-kpi">
            <p className="integrations-kpi__value">{loading ? '—' : kpi.value}</p>
            <p className="integrations-kpi__label">{kpi.label}</p>
          </article>
        ))}
      </section>

      <div className="integrations-tabs" role="tablist" aria-label="Integration areas">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={tab === item.id ? 'is-active' : ''}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {loadError ? <p className="integrations-guidance">{loadError}</p> : null}

      {tab === 'keys' ? (
        <div className="integrations-list" role="tabpanel">
          {!loading && clients.length === 0 ? (
            <AdminPanel>
              <AdminEmptyState
                title="No API keys yet"
                description="Generate one when a partner or agent needs structured access to this project."
                hints={[
                  'Turn on only the information that partner should see.',
                  'Write submits structured signals for review. It never completes a report.',
                  'Store the secret as soon as it appears.',
                ]}
                action={
                  <button type="button" className="admin-btn admin-btn--primary" onClick={openCreate}>
                    New API key
                  </button>
                }
              />
            </AdminPanel>
          ) : null}
          {clients.map((client) => (
            <article key={client.id} className="integrations-card">
              <div className="integrations-card__top">
                <div>
                  <h3 className="integrations-card__name">{client.name}</h3>
                  <p className="integrations-card__id">{client.public_client_id || 'Key id appears after save'}</p>
                  <p className="integrations-card__meta">
                    {client.allow_read ? 'Read' : 'No read'}
                    {client.allow_write ? ' · Write' : ''}
                    {' · '}
                    {accessTokenLabel(client.access_token_minutes)} token
                    {' · '}
                    {keyTtlLabel(client.key_ttl_days)} key
                    {client.created_at ? ` · ${formatTimestampDateIN(client.created_at) || ''}` : ''}
                  </p>
                </div>
                <StatusBadge status={client.status} />
              </div>
              <div className="integrations-pills">
                {(client.info_access || []).map((id) => (
                  <span key={id} className="integrations-pill">{infoLabel(id)}</span>
                ))}
                {client.mcp_enabled ? <span className="integrations-pill integrations-pill--quiet">MCP</span> : null}
                {client.allow_write ? <span className="integrations-pill integrations-pill--write">Write</span> : null}
              </div>
              <p className="integrations-note">
                {(client.case_ids || []).length
                  ? `Granted cases: ${client.case_ids.join(', ')}`
                  : 'No case grants yet. Add case IDs before this key can see case data.'}
              </p>
              {client.status === 'active' ? (
                <div className="integrations-card__actions">
                  <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => openEdit(client)}>
                    Edit access
                  </button>
                  <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => rotateKey(client)} disabled={saving}>
                    Rotate key
                  </button>
                  <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => revokeKey(client)}>
                    {confirmRevokeId === client.id ? 'Confirm revoke' : 'Revoke'}
                  </button>
                </div>
              ) : null}
              {confirmRevokeId === client.id ? (
                <p className="integrations-note">Revoke this key? Partners using it will need a new one.</p>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}

      {tab === 'webhooks' ? (
        <div className="integrations-list" role="tabpanel">
          <p className="integrations-note">
            Webhooks send event names and identifiers. They do not send report narratives or child details.
          </p>
          {!loading && webhooks.length === 0 ? (
            <AdminPanel>
              <AdminEmptyState
                title="No webhooks yet"
                description="Add an https endpoint when a partner should hear about sessions, drafts, or incidents."
                action={
                  <button type="button" className="admin-btn admin-btn--primary" onClick={onFooter}>
                    New webhook
                  </button>
                }
              />
            </AdminPanel>
          ) : null}
          {webhooks.map((hook) => (
            <article key={hook.id} className="integrations-card">
              <div className="integrations-card__top">
                <div>
                  <h3 className="integrations-card__name">{hook.client_name || 'API key'}</h3>
                  <p className="integrations-card__id">{hook.url}</p>
                </div>
                <StatusBadge status={hook.status === 'active' ? 'active' : 'paused'} />
              </div>
              <div className="integrations-pills">
                {(hook.events || []).map((event) => (
                  <span key={event} className="integrations-pill integrations-pill--quiet">{event}</span>
                ))}
              </div>
              <div className="integrations-card__actions">
                <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => toggleWebhook(hook)}>
                  {hook.status === 'active' ? 'Pause' : 'Resume'}
                </button>
                <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => rotateWebhook(hook)} disabled={saving}>
                  Rotate secret
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {tab === 'mcp' ? (
        <div className="integrations-mcp-grid" role="tabpanel">
          <AdminPanel title="Connect MCP" subtitle="Clinical tools stay read-only. Therapist profile create is available when that area and Write are on.">
            <p className="integrations-note">
              Request a short-lived token with the client id and secret, then put that token in the MCP header. Do not paste the long-lived secret into the agent config.
            </p>
            <pre className="integrations-pre">{tokenRequestSnippet(origin)}</pre>
            <pre className="integrations-pre">{mcpConnectionSnippet(origin)}</pre>
            <div className="integrations-card__actions">
              <CopyButton value={mcpConnectionSnippet(origin)} label="Copy MCP config" />
            </div>
          </AdminPanel>
          <AdminPanel title="Keys with MCP" subtitle="Turn MCP off on a key from Edit access.">
            {activeClients.filter((client) => client.mcp_enabled).length === 0 ? (
              <AdminEmptyState
                title="MCP is off for every key"
                description="Create a key and leave Allow MCP on, or turn it on while editing."
              />
            ) : (
              <div className="integrations-list">
                {activeClients.filter((client) => client.mcp_enabled).map((client) => (
                  <article key={client.id} className="integrations-card">
                    <h3 className="integrations-card__name">{client.name}</h3>
                    <p className="integrations-card__id">{client.public_client_id}</p>
                    <p className="integrations-note">
                      {(client.info_access || []).map(infoLabel).join(' · ') || 'No information areas'}
                    </p>
                  </article>
                ))}
              </div>
            )}
          </AdminPanel>
        </div>
      ) : null}

      {tab !== 'mcp' ? (
        <div className="integrations-footer">
          <button type="button" className="admin-btn admin-btn--primary" onClick={onFooter}>
            {footerLabel}
          </button>
        </div>
      ) : null}

      {sheet ? (
        <>
          <button type="button" className="integrations-backdrop" aria-label="Close" onClick={() => !saving && setSheet(null)} />
          <aside className="integrations-sheet" role="dialog" aria-modal="true" aria-labelledby="integration-sheet-title">
            <div className="integrations-sheet__handle" />
            <h3 id="integration-sheet-title" className="integrations-sheet__title">
              {sheet.mode === 'create' ? 'New API key' : 'Edit access'}
            </h3>
            <p className="integrations-sheet__sub">
              Read returns masked structured fields. Write can submit signals for review or create a therapist profile. It cannot finish a report, assign a diagnosis, or replace a therapist’s notes.
            </p>
            {reveal ? <SecretReveal reveal={reveal} onClose={() => { setReveal(null); setSheet(null) }} /> : (
              <>
                <div className="integrations-field">
                  <label htmlFor="integration-name">Name</label>
                  <input
                    id="integration-name"
                    value={draft.name}
                    onChange={(event) => patchDraft({ name: event.target.value })}
                    placeholder="School reporting agent"
                    maxLength={128}
                  />
                </div>
                <p className="integrations-section-label" style={{ marginTop: 16 }}>Permissions</p>
                <AccessSwitch
                  id="integration-read"
                  label="Read"
                  hint="Return the information areas you turn on."
                  checked={draft.allowRead}
                  onChange={(allowRead) => patchDraft({ allowRead })}
                />
                <AccessSwitch
                  id="integration-write"
                  label="Write"
                  hint="Submit structured signals for review, or create therapist profiles when that area is on. Reports, IEP, pending items, and operations stay read-only."
                  checked={draft.allowWrite}
                  onChange={(allowWrite) => patchDraft({ allowWrite })}
                />
                <p className="integrations-section-label" style={{ marginTop: 16 }}>Access token life</p>
                <div className="integrations-chips" role="group" aria-label="Access token life">
                  {ACCESS_TOKEN_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={draft.accessTokenMinutes === option.value ? 'is-active' : ''}
                      onClick={() => patchDraft({ accessTokenMinutes: option.value })}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                <p className="integrations-section-label" style={{ marginTop: 16 }}>API key validity</p>
                <div className="integrations-chips" role="group" aria-label="API key validity">
                  {KEY_TTL_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={draft.keyTtlDays === option.value ? 'is-active' : ''}
                      onClick={() => patchDraft({ keyTtlDays: option.value })}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                <p className="integrations-section-label" style={{ marginTop: 16 }}>Information access</p>
                {INFO_ACCESS.map((item) => (
                  <AccessSwitch
                    key={item.id}
                    id={`info-${item.id}`}
                    label={item.label}
                    hint={item.hint}
                    badge={draft.allowWrite && !item.writeScope ? 'Read only' : null}
                    checked={draft.infoAccess.includes(item.id)}
                    onChange={() => toggleInfo(item.id)}
                  />
                ))}
                <div className="integrations-field">
                  <label htmlFor="integration-cases-search">Granted cases</label>
                  <p className="integrations-note">
                    Blank means this key cannot see any case. Filter the list, then tap cases to grant.
                  </p>
                  <IntegrationCaseGrantPicker
                    value={draft.caseIdsText}
                    onChange={(caseIdsText) => patchDraft({ caseIdsText })}
                  />
                </div>
                <AccessSwitch
                  id="integration-mcp"
                  label="Allow MCP"
                  hint="Lets this key call MCP tools with a short-lived token, including therapist profile list and create when those scopes are on."
                  checked={draft.mcpEnabled}
                  onChange={(mcpEnabled) => patchDraft({ mcpEnabled })}
                />
                <p className="integrations-section-label" style={{ marginTop: 12 }}>Scopes stored on this key</p>
                <div className="integrations-scopes">
                  {previewScopes.length
                    ? previewScopes.map((scope) => <code key={scope}>{scope}</code>)
                    : <span className="integrations-note">Turn on access to see the scopes.</span>}
                </div>
                {sheet.signals?.length ? (
                  <div className="integrations-field">
                    <p className="integrations-section-label">Recent structured writes</p>
                    <ul className="integrations-note">
                      {sheet.signals.map((signal) => (
                        <li key={signal.id}>
                          {signal.domain} · {signal.signal_key}
                          {signal.level ? ` · level ${signal.level}` : ''} · {signal.status.replaceAll('_', ' ')}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {guidance ? <p className="integrations-guidance" style={{ marginTop: 12 }}>{guidance}</p> : null}
                <div className="integrations-sheet__actions" style={{ marginTop: 16 }}>
                  <button type="button" className="admin-btn admin-btn--primary" onClick={saveKey} disabled={saving}>
                    {saving ? 'Saving…' : sheet.mode === 'create' ? 'Generate key' : 'Save access'}
                  </button>
                  <button type="button" className="admin-btn admin-btn--ghost" onClick={() => setSheet(null)} disabled={saving}>
                    Close
                  </button>
                </div>
              </>
            )}
          </aside>
        </>
      ) : null}

      {webhookSheet ? (
        <>
          <button type="button" className="integrations-backdrop" aria-label="Close webhook" onClick={() => !saving && setWebhookSheet(false)} />
          <aside className="integrations-sheet" role="dialog" aria-modal="true" aria-labelledby="webhook-sheet-title">
            <div className="integrations-sheet__handle" />
            <h3 id="webhook-sheet-title" className="integrations-sheet__title">New webhook</h3>
            <p className="integrations-sheet__sub">
              Events carry identifiers and status flags. The signing secret is shown once.
            </p>
            {webhookReveal ? (
              <div className="integrations-secret">
                <p className="integrations-note">Store this signing secret now. It will not be shown again.</p>
                <dl>
                  <dt>Endpoint</dt>
                  <dd><code>{webhookReveal.url}</code></dd>
                  <dt>Signing secret</dt>
                  <dd>
                    <code>{webhookReveal.signing_secret}</code>
                    <CopyButton value={webhookReveal.signing_secret} />
                  </dd>
                </dl>
                <div className="integrations-sheet__actions" style={{ marginTop: 12 }}>
                  <button type="button" className="admin-btn admin-btn--primary" onClick={() => { setWebhookReveal(null); setWebhookSheet(false) }}>
                    I've stored this secret
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="integrations-field">
                  <label htmlFor="webhook-key">API key</label>
                  <select
                    id="webhook-key"
                    value={webhookDraft.integrationClientId}
                    onChange={(event) => setWebhookDraft((current) => ({ ...current, integrationClientId: event.target.value }))}
                  >
                    <option value="">Choose a key</option>
                    {activeClients.map((client) => (
                      <option key={client.id} value={client.id}>{client.name}</option>
                    ))}
                  </select>
                </div>
                <div className="integrations-field">
                  <label htmlFor="webhook-url">HTTPS endpoint</label>
                  <input
                    id="webhook-url"
                    value={webhookDraft.url}
                    onChange={(event) => setWebhookDraft((current) => ({ ...current, url: event.target.value }))}
                    placeholder="https://partner.example/hooks/insightcase"
                  />
                </div>
                <p className="integrations-section-label" style={{ marginTop: 16 }}>Events</p>
                {WEBHOOK_EVENTS.map((event) => (
                  <AccessSwitch
                    key={event.id}
                    id={`event-${event.id}`}
                    label={event.label}
                    hint={event.hint}
                    checked={webhookDraft.events.includes(event.id)}
                    onChange={() => {
                      setWebhookDraft((current) => {
                        const has = current.events.includes(event.id)
                        return {
                          ...current,
                          events: has ? current.events.filter((id) => id !== event.id) : [...current.events, event.id],
                        }
                      })
                    }}
                  />
                ))}
                {webhookGuidance ? <p className="integrations-guidance" style={{ marginTop: 12 }}>{webhookGuidance}</p> : null}
                <div className="integrations-sheet__actions" style={{ marginTop: 16 }}>
                  <button type="button" className="admin-btn admin-btn--primary" onClick={saveWebhook} disabled={saving}>
                    {saving ? 'Saving…' : 'Generate webhook'}
                  </button>
                  <button type="button" className="admin-btn admin-btn--ghost" onClick={() => setWebhookSheet(false)} disabled={saving}>
                    Close
                  </button>
                </div>
              </>
            )}
          </aside>
        </>
      ) : null}
    </div>
  )
}
