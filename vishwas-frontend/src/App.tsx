import { useEffect, useState } from 'react'
import './App.css'
import { AuthProvider } from './contexts/AuthContext'
import { Shell } from './components/layout/Shell'
import { AnalyseACall } from './pages/AnalyseACall'
import { AnalysisReport } from './pages/AnalysisReport'
import { CallHistory } from './pages/CallHistory'
import { Overview } from './pages/Overview'
import { LiveAnalysisPage } from './pages/LiveAnalysisPage'
import { PrivacySettings } from './pages/PrivacySettings'
import { TrustGraphPage } from './pages/TrustGraphPage'
import { VoiceDetectionPage } from './pages/VoiceDetectionPage'
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

function AppContent() {
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
    if (item !== 'analyse' && item !== 'history') {
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
      case 'live':
        return (
          <LiveAnalysisPage
            onViewReport={(callId) => {
              setSelectedCallId(callId)
              setShowReport(true)
              setActiveItem('analyse')
            }}
          />
        )
      case 'analyse':
        return showReport ? (
          <AnalysisReport callId={selectedCallId || undefined} onBack={() => setShowReport(false)} />
        ) : (
          <AnalyseACall onViewReport={(callId) => { setSelectedCallId(callId); setShowReport(true) }} />
        )
      case 'history':
        return showReport ? (
          <AnalysisReport callId={selectedCallId || undefined} onBack={() => { setShowReport(false); setSelectedCallId(null) }} />
        ) : (
          <CallHistory onViewReport={(callId) => { setSelectedCallId(callId); setShowReport(true) }} />
        )
      case 'voice-detection':
        return <VoiceDetectionPage />
      case 'settings':
        return <PrivacySettings />
    }
  }
  // AUTHENTICATION DISABLED - Direct access to dashboard
  // Show main app without authentication
  return (
    <Shell activeItem={activeItem} onNavigate={handleNavigate}>
      {renderPage()}
    </Shell>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}
