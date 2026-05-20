import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

const FALLBACK_URL = import.meta.env.VITE_POLICIES_BOT_URL || ''

export function PoliciesBotButton({ infoPath = '/api/v1/support/info', policiesBotUrl = null, className = '' }) {
  const [url, setUrl] = useState(policiesBotUrl || FALLBACK_URL)

  useEffect(() => {
    if (policiesBotUrl) {
      setUrl(policiesBotUrl)
      return
    }
    apiFetch(infoPath)
      .then((info) => {
        if (info?.policies_bot_url) setUrl(info.policies_bot_url)
      })
      .catch(() => {})
  }, [infoPath, policiesBotUrl])

  if (!url) {
    return (
      <span className={`ticket-policies-bot ticket-policies-bot--disabled ${className}`.trim()} title="Policies bot URL not configured">
        Policies bot (coming soon)
      </span>
    )
  }

  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className={`ticket-policies-bot ${className}`.trim()}
    >
      Policies bot
    </a>
  )
}
