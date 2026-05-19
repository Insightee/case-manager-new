import { useCallback, useMemo, useSyncExternalStore } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import {
  THERAPIST_USAGE_EVENT,
  getFrequentTherapistActions,
  hasPersonalizedUsage,
  recordTherapistAction,
} from '../lib/therapistActions.js'

function subscribe(callback) {
  window.addEventListener(THERAPIST_USAGE_EVENT, callback)
  window.addEventListener('storage', callback)
  return () => {
    window.removeEventListener(THERAPIST_USAGE_EVENT, callback)
    window.removeEventListener('storage', callback)
  }
}

export function useTherapistFrequentActions(limit = 4) {
  const { user } = useAuth()
  const userId = user?.id

  const version = useSyncExternalStore(subscribe, () => {
    if (!userId) return '0'
    try {
      return localStorage.getItem(`insightcase:therapist-usage:${userId}`) || '0'
    } catch {
      return '0'
    }
  })

  const actions = useMemo(() => {
    void version
    return getFrequentTherapistActions(userId, limit)
  }, [userId, limit, version])

  const personalized = useMemo(() => {
    void version
    return hasPersonalizedUsage(userId)
  }, [userId, version])

  const trackClick = useCallback(
    (actionId) => {
      recordTherapistAction(userId, actionId)
    },
    [userId],
  )

  return { actions, personalized, trackClick }
}
