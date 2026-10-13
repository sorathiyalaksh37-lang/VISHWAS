import { MenuIcon, WifiOffIcon } from 'lucide-react'

interface HeaderProps {
  title: string
  subtitle: string
  onMobileMenuOpen: () => void
}

export function Header({ title, subtitle, onMobileMenuOpen }: HeaderProps) {
  return (
    <header className="topbar" role="banner">
      {/* Mobile hamburger */}
      <button
        className="topbar__menu-btn"
        onClick={onMobileMenuOpen}
        aria-label="Open navigation menu"
      >
        <MenuIcon size={20} />
      </button>

      {/* Page title block */}
      <div className="topbar__titles">
        <h1 className="topbar__title">{title}</h1>
        <p className="topbar__subtitle">{subtitle}</p>
      </div>

      {/* Backend connection indicator */}
      <div className="topbar__status" aria-label="Backend connection status: Not connected">
        <WifiOffIcon size={14} aria-hidden="true" className="topbar__status-icon" />
        <span className="topbar__status-label">Not connected</span>
      </div>
    </header>
  )
}
