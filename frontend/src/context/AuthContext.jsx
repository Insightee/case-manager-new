import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import {
  apiFetch,
  clearTokens,
  ensureAccessToken,
  getTokens,
  isAuthSessionError,
  setTokens,
  tryRefreshSession,
} from '../lib/apiClient.js'
import {
  canWriteFeature,
  canWriteModule,
  canWriteProduct,
  hasModule,
  isGlobalViewOnly,
  moduleAccess,
  navItemVisible,
} from '../lib/moduleAccess.js'
import {
  portalMismatchMessage,
  resolveAuthPortal,
  STAFF_LOGIN_ROLES,
  userMatchesLoginPortal,
} from '../lib/portalLogin.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedPortal, setSelectedPortal] = useState(() => {
    return localStorage.getItem('insightcase_login_portal') || null
  })

  const updateLoginPortal = useCallback((p) => {
    setSelectedPortal(p)
    if (p) {
      localStorage.setItem('insightcase_login_portal', p)
    } else {
      localStorage.removeItem('insightcase_login_portal')
    }
  }, [])

  const loadMe = useCallback(async () => {
    setLoading(true)
    const access = await ensureAccessToken()
    if (!access) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const me = await apiFetch('/api/v1/auth/me')
      setUser(me)
    } catch (err) {
      if (isAuthSessionError(err)) {
        clearTokens()
        setUser(null)
      }
      // Connection/API errors: keep existing user — do not logout on network blips.
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadMe()
  }, [loadMe])

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return
      if (!getTokens().refresh) return
      void tryRefreshSession()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [])

  const clearSessionForPortalRetry = useCallback(() => {
    clearTokens()
    setUser(null)
    setLoading(false)
  }, [])

  const login = useCallback(async (email, password, portal = null, rememberMe = false) => {
    clearTokens()
    setUser(null)
    const body = { email, password, remember_me: rememberMe }
    if (portal) {
      body.portal = portal === 'admin' ? 'staff' : portal
    }
    try {
      const data = await apiFetch('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      let signedInUser = data.user
      if (!signedInUser) {
        setTokens(data.access_token, data.refresh_token)
        signedInUser = await apiFetch('/api/v1/auth/me')
      }
      if (portal && signedInUser && !userMatchesLoginPortal(signedInUser, portal)) {
        throw new Error(portalMismatchMessage())
      }
      setTokens(data.access_token, data.refresh_token)
      setUser(signedInUser)
      setLoading(false)
      return { ...data, user: signedInUser }
    } catch (err) {
      clearTokens()
      setUser(null)
      setLoading(false)
      throw err
    }
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
    updateLoginPortal(null)
  }, [updateLoginPortal])

  const portal = useMemo(() => resolveAuthPortal(user, selectedPortal), [user, selectedPortal])

  const can = useCallback(
    (permission) => {
      if (!user?.permissions) return false
      return user.permissions.includes(permission) || user.permissions.includes('admin.override')
    },
    [user],
  )

  const hasFeature = useCallback(
    (feature) => {
      if (!user) return false
      const features = user.features
      if (!features?.length) return false
      if (features.includes('*')) return true
      return features.includes(feature)
    },
    [user],
  )

  const hasModuleAccess = useCallback((moduleId) => hasModule(user, moduleId), [user])

  const getModuleAccess = useCallback((moduleId) => moduleAccess(user, moduleId), [user])

  const canWriteModuleFn = useCallback((moduleId) => canWriteModule(user, moduleId), [user])

  const canWriteProductFn = useCallback(
    (productModule) => canWriteProduct(user, productModule),
    [user],
  )

  const canWriteFeatureFn = useCallback(
    (featureId, productModule = null) => canWriteFeature(user, featureId, productModule),
    [user],
  )

  const isViewOnly = useMemo(() => isGlobalViewOnly(user), [user])

  const navVisible = useCallback(
    (item) =>
      navItemVisible(item, {
        can,
        hasFeature,
        hasModule: hasModuleAccess,
      }),
    [can, hasFeature, hasModuleAccess],
  )

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      logout,
      portal,
      selectedPortal,
      clearSessionForPortalRetry,
      updateLoginPortal,
      can,
      hasFeature,
      hasModule: hasModuleAccess,
      getModuleAccess,
      canWriteModule: canWriteModuleFn,
      canWriteProduct: canWriteProductFn,
      canWriteFeature: canWriteFeatureFn,
      navVisible,
      isViewOnly,
      reload: loadMe,
    }),
    [
      user,
      loading,
      login,
      logout,
      portal,
      selectedPortal,
      clearSessionForPortalRetry,
      updateLoginPortal,
      can,
      hasFeature,
      hasModuleAccess,
      getModuleAccess,
      canWriteModuleFn,
      canWriteProductFn,
      canWriteFeatureFn,
      navVisible,
      isViewOnly,
      loadMe,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
