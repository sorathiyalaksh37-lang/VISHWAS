import {
  BarChart2,
  ClockIcon,
  GitFork,
  MicVocalIcon,
  Settings2,
  ShieldCheckIcon,
  X,
} from 'lucide-react'

export type NavItem = 'overview' | 'trust-graph' | 'analyse' | 'history' | 'settings'

interface NavEntry {
  id: NavItem
  label: string
  icon: React.ReactNode
}

const NAV_ITEMS: NavEntry[] = [
  {
    id: 'overview',
    label: 'Overview',
    icon: <BarChart2 size={18} aria-hidden="true" />,
  },
  {
    id: 'trust-graph',
    label: 'Trust Graph',
    icon: <GitFork size={18} aria-hidden="true" />,
  },
  {
    id: 'analyse',
    label: 'Analyse a Call',
    icon: <MicVocalIcon size={18} aria-hidden="true" />,
  },
  {
    id: 'history',
    label: 'Call History',
    icon: <ClockIcon size={18} aria-hidden="true" />,
  },
  {
    id: 'settings',
    label: 'Privacy & Settings',
    icon: <Settings2 size={18} aria-hidden="true" />,
  },
]

interface SidebarProps {
  activeItem: NavItem
  onNavigate: (item: NavItem) => void
  mobileOpen: boolean
  onMobileClose: () => void
}

export function Sidebar({
  activeItem,
  onNavigate,
  mobileOpen,
  onMobileClose,
}: SidebarProps) {
  return (
    <>
      {/* Mobile overlay backdrop */}
      {mobileOpen && (
        <div
          className="sidebar-backdrop"
          aria-hidden="true"
          onClick={onMobileClose}
        />
      )}

      <aside
        className={`sidebar${mobileOpen ? ' sidebar--open' : ''}`}
        aria-label="Main navigation"
      >
        {/* Brand */}
        <div className="sidebar__brand">
          <div className="sidebar__logo" aria-hidden="true">
            <ShieldCheckIcon size={22} strokeWidth={2} />
          </div>
          <div className="sidebar__brand-text">
            <span className="sidebar__name">VISHWAS</span>
            <span className="sidebar__tagline">Voice Security AI</span>
          </div>

          {/* Mobile close button */}
          <button
            className="sidebar__close-btn"
            onClick={onMobileClose}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        {/* Divider */}
        <div className="sidebar__divider" />

        {/* Navigation */}
        <nav>
          <ul className="sidebar__nav" role="list">
            {NAV_ITEMS.map(({ id, label, icon }) => {
              const isActive = activeItem === id
              return (
                <li key={id}>
                  <button
                    className={`sidebar__nav-item${isActive ? ' sidebar__nav-item--active' : ''}`}
                    onClick={() => {
                      onNavigate(id)
                      onMobileClose()
                    }}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <span className="sidebar__nav-icon">{icon}</span>
                    <span className="sidebar__nav-label">{label}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>

        {/* Bottom spacer — future: user profile / logout */}
        <div className="sidebar__footer">
          <p className="sidebar__version">v0.1.0-alpha</p>
        </div>
      </aside>
    </>
  )
}
