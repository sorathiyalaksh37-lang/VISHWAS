import { useEffect, useState } from 'react'
import './App.css'
import { Shell } from './components/layout/Shell'
import { AnalyseACall } from './pages/AnalyseACall'
import { AnalysisReport } from './pages/AnalysisReport'
import { CallHistory } from './pages/CallHistory'
import { Overview } from './pages/Overview'
import { PrivacySettings } from './pages/PrivacySettings'
import { TrustGraphPage } from './pages/TrustGraphPage'
import type { NavItem } from './components/layout/Sidebar'

const PREFS_KEY = 'vishwas:ui-prefs'

function readCompactPref(): boolean {
  try {
    const raw = localStorage.getItem(PREFS_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Record<string, unknown>
      return parsed.compactLayout === true
    }
  } catch {
    // Ignore
  }
  return false
}

/**
 * Root application component.
 *
 * Reads the compact-layout preference on mount and applies
 * data-compact="true" to <html> so the CSS selector in index.css activates.
 *
 * Navigation state lives here. `showReport` tracks whether the inline
 * report sub-view is active on the Analyse a Call page.
 */
function App() {
  const [activeItem, setActiveItem] = useState<NavItem>('overview')
  const [showReport, setShowReport] = useState(false)
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null)

  // Apply / remove the compact-layout attribute on <html>
  useEffect(() => {
    function applyCompact() {
      const isCompact = readCompactPref()
      if (isCompact) {
        document.documentElement.setAttribute('data-compact', 'true')
      } else {
        document.documentElement.removeAttribute('data-compact')
      }
    }

    applyCompact()

    const handleStorage = () => applyCompact()
    window.addEventListener('storage', handleStorage)
    window.addEventListener('vishwas:prefs-changed', handleStorage)

    return () => {
      window.removeEventListener('storage', handleStorage)
      window.removeEventListener('vishwas:prefs-changed', handleStorage)
    }
  }, [])

  // Reset the report sub-view when navigating away from the analyse page
  function handleNavigate(item: NavItem) {
    setActiveItem(item)
    if (item !== 'analyse') {
      setShowReport(false)
      setSelectedCallId(null)
    }
  }

  function renderPage() {
    switch (activeItem) {
      case 'overview':
        return <Overview onNavigate={handleNavigate} />
      case 'trust-graph':
        return <TrustGraphPage />
      case 'analyse':
        return showReport ? (
          <AnalysisReport callId={selectedCallId || undefined} onBack={() => setShowReport(false)} />
        ) : (
          <AnalyseACall onViewReport={(callId) => { setSelectedCallId(callId); setShowReport(true) }} />
        )
      case 'history':
        return <CallHistory />
      case 'settings':
        return <PrivacySettings />
    }
  }

  return (
    <Shell activeItem={activeItem} onNavigate={handleNavigate}>
      {renderPage()}
    </Shell>
  )
}

export default App
