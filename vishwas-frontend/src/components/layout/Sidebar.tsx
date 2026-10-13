import {
  BarChart2,
  ClockIcon,
  GitFork,
  LogOut,
  MicVocalIcon,
  Settings2,
  ShieldCheckIcon,
  User,
  X,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

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
  const { user, logout } = useAuth()

  const handleLogout = () => {
    logout()
    onMobileClose()
  }

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

        {/* Bottom spacer — user profile / logout */}
        <div className="sidebar__footer">
          {user && (
            <div className="mb-3 p-3 bg-slate-800/50 rounded-lg border border-slate-700/50">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
                  <User size={16} className="text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate">
                    {user.full_name || user.email.split('@')[0]}
                  </p>
                  <p className="text-xs text-slate-400 truncate">{user.email}</p>
                </div>
              </div>
              <button
                onClick={handleLogout}
                className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-slate-700/50 hover:bg-slate-700 rounded text-sm text-slate-300 hover:text-white transition-colors"
              >
                <LogOut size={14} />
                <span>Sign Out</span>
              </button>
            </div>
          )}
          <p className="sidebar__version">v0.1.0-alpha</p>
        </div>
      </aside>
    </>
  )
}
