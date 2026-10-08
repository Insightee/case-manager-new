import { useEffect, useState } from 'react'
import { REINSTALL_LANDING_EVENT, readReinstallLanding } from '../lib/pwaReinstall.js'

/** Whether this tab is on the ?reinstall=1 landing (sticky across login redirects). */
export function useReinstallLanding() {
  const [state, setState] = useState(() => readReinstallLanding())
  useEffect(() => {
    const sync = () => setState(readReinstallLanding())
    window.addEventListener(REINSTALL_LANDING_EVENT, sync)
    window.addEventListener('popstate', sync)
    return () => {
      window.removeEventListener(REINSTALL_LANDING_EVENT, sync)
      window.removeEventListener('popstate', sync)
    }
  }, [])
  return state
}
