import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { normalizePathname } from '../lib/normalizePathname.js'

/** Redirects to a cleaned pathname when email clients append invisible Unicode. */
export function PathnameSanitizer({ children }) {
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    const clean = normalizePathname(location.pathname)
    if (clean !== location.pathname) {
      navigate({ pathname: clean, search: location.search, hash: location.hash }, { replace: true })
    }
  }, [location.pathname, location.search, location.hash, navigate])

  return children
}
