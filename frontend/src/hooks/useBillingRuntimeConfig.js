import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../lib/apiClient.js'
import { isClientBillingVisible } from '../lib/productFeatureFlags.js'

const DEFAULT = {
  billingEnabled: false,
  ledgerWritesEnabled: false,
  cutoverComplete: false,
  zohoConfigured: false,
}

/**
 * One coherent answer for client-billing visibility + liveness.
 * Visibility: VITE_ENABLE_CLIENT_BILLING (prod-forced-off).
 * Liveness/writes/Zoho: backend runtime-config (ENABLE_BILLING / LEDGER_WRITES / CUTOVER / ZOHO key).
 */
export function useBillingRuntimeConfig({ enabled = true } = {}) {
  const visible = isClientBillingVisible()
  const [config, setConfig] = useState(DEFAULT)
  const [loading, setLoading] = useState(Boolean(enabled && visible))
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    if (!enabled || !visible) {
      setConfig(DEFAULT)
      setLoading(false)
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch('/api/v1/admin/client-billing/runtime-config')
      setConfig({
        billingEnabled: Boolean(data?.billingEnabled),
        ledgerWritesEnabled: Boolean(data?.ledgerWritesEnabled),
        cutoverComplete: Boolean(data?.cutoverComplete),
        zohoConfigured: Boolean(data?.zohoConfigured),
      })
    } catch (err) {
      setError(err?.message || 'Could not load billing runtime config')
      setConfig(DEFAULT)
    } finally {
      setLoading(false)
    }
  }, [enabled, visible])

  useEffect(() => {
    load()
  }, [load])

  return useMemo(() => {
    const provisional = visible && !config.cutoverComplete
    const writesEnabled = Boolean(config.ledgerWritesEnabled && config.billingEnabled)
    return {
      visible,
      loading,
      error,
      reload: load,
      billingEnabled: config.billingEnabled,
      ledgerWritesEnabled: config.ledgerWritesEnabled,
      cutoverComplete: config.cutoverComplete,
      zohoConfigured: config.zohoConfigured,
      provisional,
      live: visible && config.cutoverComplete,
      writesEnabled,
    }
  }, [visible, loading, error, load, config])
}
