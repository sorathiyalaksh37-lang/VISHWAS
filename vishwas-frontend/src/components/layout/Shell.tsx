import { useState } from 'react'
import { Header } from './Header'
import { Sidebar, type NavItem } from './Sidebar'

/** Map each nav item to its page title and subtitle shown in the top header */
const PAGE_META: Record<NavItem, { title: string; subtitle: string }> = {
  overview: {
    title: 'VISHWAS',
    subtitle: 'A voice can be cloned. Trust must be verified.',
  },
  'trust-graph': {
    title: 'Trust Graph',
    subtitle: 'Explore trusted relationships, verification status, and connections relevant to call security.',
  },
  analyse: {
    title: 'Analyse a Call',
    subtitle: 'Verify voice authenticity and assess potential social-engineering risk.',
  },
  history: {
    title: 'Call History',
    subtitle: 'Review previously analysed calls and their security findings.',
  },
  settings: {
    title: 'Privacy & Settings',
    subtitle: 'Manage data handling policies, connection status, and interface preferences.',
  },
}

interface ShellProps {
  /** Page content rendered inside the main scroll area */
  children: React.ReactNode
  activeItem: NavItem
  onNavigate: (item: NavItem) => void
}

export function Shell({ children, activeItem, onNavigate }: ShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const meta = PAGE_META[activeItem]

  return (
    <div className="shell">
      <Sidebar
        activeItem={activeItem}
        onNavigate={onNavigate}
        mobileOpen={mobileOpen}
        onMobileClose={() => setMobileOpen(false)}
      />

      <div className="shell__main">
        <Header
          title={meta.title}
          subtitle={meta.subtitle}
          onMobileMenuOpen={() => setMobileOpen(true)}
        />

        <main className="shell__content" id="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  )
}
