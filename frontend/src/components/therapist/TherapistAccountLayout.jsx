import { NavLink, Outlet } from 'react-router-dom'
import './therapist-account-layout.css'

const TABS = [
  { to: '/therapist/profile', label: 'Profile', end: true },
  { to: '/therapist/profile/vault', label: 'Vault', end: false },
]

export function TherapistAccountLayout() {
  return (
    <div className="therapist-account">
      <nav className="therapist-account__tabs" aria-label="Account sections">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) =>
              `therapist-account__tab${isActive ? ' therapist-account__tab--active' : ''}`
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  )
}
