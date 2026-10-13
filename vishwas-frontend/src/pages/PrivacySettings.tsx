import { useEffect, useState } from 'react'
import {
  CheckCircleIcon,
  DatabaseIcon,
  LayoutIcon,
  LoaderIcon,
  MonitorIcon,
  RotateCcwIcon,
  Settings2Icon,
  WifiOffIcon,
} from 'lucide-react'
import { apiClient, type HealthResponse } from '../services/api'

// ──────────────────────────────────────────────────────────────────────────────
// Preferences stored in localStorage
// Only harmless interface preferences are persisted — never recordings,
// transcripts, or analysis data.
// ──────────────────────────────────────────────────────────────────────────────
const PREFS_KEY = 'vishwas:ui-prefs'

interface UIPrefs {
  compactLayout: boolean
}

const DEFAULT_PREFS: UIPrefs = { compactLayout: false }

function loadPrefs(): UIPrefs {
  try {
    const raw = localStorage.getItem(PREFS_KEY)
    if (raw) return { ...DEFAULT_PREFS, ...JSON.parse(raw) }
  } catch {
    // If parsing fails, fall through to defaults
  }
  return { ...DEFAULT_PREFS }
}

function savePrefs(prefs: UIPrefs) {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs))
    // Notify App.tsx (same tab) so it can apply or remove data-compact immediately
    window.dispatchEvent(new Event('vishwas:prefs-changed'))
  } catch {
    // Silently ignore storage errors (e.g. private-browsing quota)
  }
}

/**
 * Privacy & Settings page.
 *
 * Sections:
 *  1. Privacy and Data Handling — honest, factual statements only
 *  2. Connection Status       — static "not connected"; no fake health checks
 *  3. Interface Preferences   — compact-layout toggle, reset; persisted in localStorage
 */
export function PrivacySettings() {
  const [prefs, setPrefs] = useState<UIPrefs>(loadPrefs)
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'checking' | 'connected' | 'failed'>('idle')
  const [backendInfo, setBackendInfo] = useState<HealthResponse | null>(null)

  // Persist whenever prefs change
  useEffect(() => {
    savePrefs(prefs)
  }, [prefs])

  function toggleCompactLayout() {
    setPrefs((p) => ({ ...p, compactLayout: !p.compactLayout }))
  }

  function resetPrefs() {
    const defaults = { ...DEFAULT_PREFS }
    setPrefs(defaults)
    savePrefs(defaults)
  }

  async function handleCheckConnection() {
    setConnectionStatus('checking')
    setBackendInfo(null)

    try {
      const health = await apiClient.checkHealth()
      
      if (health) {
        setConnectionStatus('connected')
        setBackendInfo(health)
      } else {
        setConnectionStatus('failed')
      }
    } catch (error) {
      console.error('Connection check failed:', error)
      setConnectionStatus('failed')
    }
  }

  return (
    <div className="page-content">
      {/* Page heading */}
      <div className="page-heading">
        <div className="page-heading__icon-wrap" aria-hidden="true">
          <Settings2Icon size={20} strokeWidth={1.75} />
        </div>
        <div>
          <h1 className="page-heading__title">Privacy &amp; Settings</h1>
          <p className="page-heading__subtitle">
            Manage data handling policies, connection status, and interface preferences.
          </p>
        </div>
      </div>

      {/* ── Section 1: Privacy and Data Handling ─────────────────────────── */}
      <section className="settings-section" aria-labelledby="privacy-heading">
        <div className="settings-section__header">
          <div className="settings-section__icon" aria-hidden="true">
            <DatabaseIcon size={16} strokeWidth={1.75} />
          </div>
          <h2 id="privacy-heading" className="settings-section__title">
            Privacy and Data Handling
          </h2>
        </div>

        <div className="settings-section__body">
          <div className="privacy-statement">
            <ul className="privacy-list" role="list">
              <li className="privacy-list__item">
                <span className="privacy-list__dot" aria-hidden="true" />
                <span>
                  <strong>No recordings are uploaded.</strong> This frontend does not transmit audio
                  files to any server. Files you select remain in your browser memory only.
                </span>
              </li>
              <li className="privacy-list__item">
                <span className="privacy-list__dot" aria-hidden="true" />
                <span>
                  <strong>Analysis requires backend integration.</strong> Voice-authenticity checks
                  and risk assessments are performed by the backend service, which is not currently
                  connected.
                </span>
              </li>
              <li className="privacy-list__item">
                <span className="privacy-list__dot" aria-hidden="true" />
                <span>
                  <strong>Local preferences only.</strong> The only data stored in your browser is
                  harmless interface preferences (e.g. layout toggle). No recordings, transcripts,
                  or analysis results are persisted locally.
                </span>
              </li>
              <li className="privacy-list__item">
                <span className="privacy-list__dot privacy-list__dot--warn" aria-hidden="true" />
                <span>
                  <strong>Unverified claims excluded.</strong> Encryption standards, automatic
                  deletion schedules, and regulatory certifications are not claimed here because
                  they have not been verified in the current codebase.
                </span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* ── Section 2: Connection Status ─────────────────────────────────── */}
      <section className="settings-section" aria-labelledby="connection-heading">
        <div className="settings-section__header">
          <div className="settings-section__icon" aria-hidden="true">
            <MonitorIcon size={16} strokeWidth={1.75} />
          </div>
          <h2 id="connection-heading" className="settings-section__title">
            Connection Status
          </h2>
        </div>

        <div className="settings-section__body">
          <div className="connection-row">
            <div className="connection-status">
              <WifiOffIcon size={14} aria-hidden="true" className="connection-status__icon" />
              <span className="connection-status__label">Backend not connected</span>
            </div>

            <button
              className="btn-ghost btn-ghost--sm"
              onClick={handleCheckConnection}
              aria-label="Check backend connection"
            >
              Check Connection
            </button>
          </div>

          {connectionStatus === 'checking' && (
            <div className="connection-notice connection-notice--checking" role="status" aria-live="polite">
              <LoaderIcon size={14} className="analysis-status__spinner" aria-hidden="true" />
              <span>Checking backend connection...</span>
            </div>
          )}

          {connectionStatus === 'connected' && backendInfo && (
            <div className="connection-notice connection-notice--success" role="status" aria-live="polite">
              <CheckCircleIcon size={14} aria-hidden="true" />
              <div>
                <strong>Backend connected</strong>
                <span> • {backendInfo.service} v{backendInfo.version}</span>
              </div>
            </div>
          )}

          {connectionStatus === 'failed' && (
            <div className="connection-notice connection-notice--error" role="alert" aria-live="assertive">
              <WifiOffIcon size={14} aria-hidden="true" />
              <div>
                <strong>Connection failed</strong>
                <span> • Make sure the backend is running on port 8000</span>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ── Section 3: Interface Preferences ─────────────────────────────── */}
      <section className="settings-section" aria-labelledby="prefs-heading">
        <div className="settings-section__header">
          <div className="settings-section__icon" aria-hidden="true">
            <LayoutIcon size={16} strokeWidth={1.75} />
          </div>
          <h2 id="prefs-heading" className="settings-section__title">
            Interface Preferences
          </h2>
        </div>

        <div className="settings-section__body">
          {/* Compact layout toggle */}
          <div className="pref-row">
            <div className="pref-row__text">
              <span className="pref-row__label">Compact Layout</span>
              <span className="pref-row__description">
                Reduces padding and spacing throughout the interface. Takes effect immediately.
              </span>
            </div>
            <button
              role="switch"
              aria-checked={prefs.compactLayout}
              aria-label="Toggle compact layout"
              className={`toggle${prefs.compactLayout ? ' toggle--on' : ''}`}
              onClick={toggleCompactLayout}
            >
              <span className="toggle__thumb" />
            </button>
          </div>

          <div className="pref-divider" />

          {/* Reset preferences */}
          <div className="pref-row">
            <div className="pref-row__text">
              <span className="pref-row__label">Reset Preferences</span>
              <span className="pref-row__description">
                Restore all interface preferences to their defaults.
              </span>
            </div>
            <button
              className="btn-ghost btn-ghost--sm btn-ghost--destructive"
              onClick={resetPrefs}
              aria-label="Reset interface preferences to default"
            >
              <RotateCcwIcon size={13} aria-hidden="true" />
              Reset
            </button>
          </div>

          {/* Stored-data note */}
          <p className="prefs-note" role="note">
            Preferences are stored in your browser&apos;s localStorage under the key&nbsp;
            <code>{PREFS_KEY}</code>. No sensitive data is persisted.
          </p>
        </div>
      </section>
    </div>
  )
}
