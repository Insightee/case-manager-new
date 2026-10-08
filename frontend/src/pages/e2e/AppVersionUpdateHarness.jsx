import { useSearchParams } from 'react-router-dom'
import { PortalInstallProvider } from '../../context/PortalInstallContext.jsx'
import { AppVersionNotice } from '../../components/shared/AppVersionNotice.jsx'

const PORTALS = ['parent', 'therapist', 'admin']

/**
 * Dev/e2e-only page to exercise the version notice (as seen inside an old installed app)
 * and the ?reinstall=1 landing without production polling. ?portal=parent|therapist|admin
 */
export function AppVersionUpdateHarness() {
  const [searchParams] = useSearchParams()
  const requested = searchParams.get('portal')
  const portal = PORTALS.includes(requested) ? requested : 'therapist'
  const notice = {
    show: true,
    buildKey: 'i1008',
    remoteNewer: true,
    reinstallFallback: true,
  }

  return (
    <PortalInstallProvider portal={portal}>
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
          portalId={portal}
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
