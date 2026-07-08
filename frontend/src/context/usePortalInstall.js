import { useContext } from 'react'
import { PortalInstallContext } from './portalInstallContext.js'

export function usePortalInstall() {
  const value = useContext(PortalInstallContext)
  if (!value) {
    throw new Error('usePortalInstall must be used within PortalInstallProvider')
  }
  return value
}
