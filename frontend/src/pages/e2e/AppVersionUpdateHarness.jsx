import { PortalInstallProvider } from '../../context/PortalInstallContext.jsx'
import { AppVersionNotice } from '../../components/shared/AppVersionNotice.jsx'

/**
 * Dev/e2e-only page to exercise version notice without production polling.
 */
export function AppVersionUpdateHarness() {
  const notice = {
    show: true,
    buildKey: 'i1008',
    remoteNewer: true,
    reinstallFallback: true,
  }

  return (
    <PortalInstallProvider portal="therapist">
      <div
        id="app-version-harness"
        style={{
          minHeight: '100dvh',
          padding: '16px',
          paddingBottom: 'calc(80px + env(safe-area-inset-bottom, 0px))',
          background: '#f7f8f5',
        }}
      >
        <AppVersionNotice
          portalId="therapist"
          variant="banner"
          testOverrides={{
            embeddedReleaseLabel: 'i1006',
            remoteReleaseLabel: 'i1008',
            notice,
            standalone: true,
          }}
        />
      </div>
    </PortalInstallProvider>
  )
}
