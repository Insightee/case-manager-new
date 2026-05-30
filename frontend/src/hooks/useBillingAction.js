import { useCallback, useState } from 'react'

/**
 * Wraps async finance mutations with loading, error, and success messages.
 */
export function useBillingAction() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const clearMessages = useCallback(() => {
    setError('')
    setSuccessMessage('')
  }, [])

  const run = useCallback(async (fn, { successMsg } = {}) => {
    setLoading(true)
    setError('')
    setSuccessMessage('')
    try {
      const result = await fn()
      if (successMsg) setSuccessMessage(successMsg)
      return result
    } catch (err) {
      setError(err?.message || 'Request failed')
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { loading, error, successMessage, clearMessages, run, setError, setSuccessMessage }
}
