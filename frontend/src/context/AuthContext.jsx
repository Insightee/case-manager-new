import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { apiFetch, clearTokens, getTokens, setTokens } from '../lib/apiClient.js'
import {
  canWriteFeature,
  canWriteModule,
  canWriteProduct,
  hasModule,
  isGlobalViewOnly,
  moduleAccess,
  navItemVisible,
} from '../lib/moduleAccess.js'

const AuthContext = createContext(null)

const ADMIN_ROLES = [
  'SUPER_ADMIN',
  'ADMIN',
  'MODULE_ADMIN',
  'VIEWER',
  'CASE_MANAGER',
  'SUPERVISOR',
  'FINANCE',
  'HR',
  'SCHOOL_COORDINATOR',
]

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadMe = useCallback(async () => {
    const { access } = getTokens()
    if (!access) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const me = await apiFetch('/api/v1/auth/me')
      setUser(me)
    } catch {
      clearTokens()
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadMe()
  }, [loadMe])

  const login = async (email, password) => {
    clearTokens()
    const data = await apiFetch('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    setTokens(data.access_token, data.refresh_token)
    await loadMe()
    return data
  }

  const logout = () => {
    clearTokens()
    setUser(null)
  }

  const portal = useMemo(() => {
    if (!user?.roles?.length) return null
    if (user.roles.includes('PARENT')) return 'parent'
    if (user.roles.some((r) => ADMIN_ROLES.includes(r))) return 'admin'
    if (user.roles.includes('THERAPIST')) return 'therapist'
    return 'admin'
  }, [user])

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
      portal,
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
