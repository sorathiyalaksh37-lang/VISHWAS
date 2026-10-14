import { useEffect, useState } from 'react'
import {
  AlertTriangleIcon,
  ArrowRightIcon,
  ClockIcon,
  GitForkIcon,
  MicVocalIcon,
  PhoneCallIcon,
  ShieldCheckIcon,
  UsersIcon,
  WifiIcon,
  WifiOffIcon,
} from 'lucide-react'
import { SummaryCard } from '../components/overview/SummaryCard'
import { TrustGraphPreview } from '../components/overview/TrustGraphPreview'
import { RiskScoreGauge } from '../components/shared/RiskScoreGauge'
import { apiClient, type CallListItem } from '../services/api'
import type { NavItem } from '../components/layout/Sidebar'

interface OverviewProps {
  onNavigate: (item: NavItem) => void
}

const CARD_CONFIG = [
  { variant: 'accent'   as const, icon: <UsersIcon       size={18} strokeWidth={1.75} /> },
  { variant: 'muted'    as const, icon: <PhoneCallIcon    size={18} strokeWidth={1.75} /> },
  { variant: 'critical' as const, icon: <AlertTriangleIcon size={18} strokeWidth={1.75} /> },
  { variant: 'warn'     as const, icon: <ClockIcon        size={18} strokeWidth={1.75} /> },
]

const RISK_BADGE: Record<string, string> = {
  completed:   'badge--low',
  processing:  'badge--medium',
  queued:      'badge--medium',
  failed:      'badge--high',
}

const STATUS_LABEL: Record<string, string> = {
  completed:  'Completed',
  processing: 'Processing',
  queued:     'Queued',
  failed:     'Failed',
}

/**
 * Overview page — live dashboard.
 * Fetches real stats from the backend API and falls back to
 * empty states when the backend is unavailable.
 */
export function Overview({ onNavigate }: OverviewProps) {
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null)
  const [calls, setCalls] = useState<CallListItem[]>([])
  const [totalCalls, setTotalCalls] = useState(0)
  const [loading, setLoading] = useState(true)
  const [demoRiskScore, setDemoRiskScore] = useState(42) // Demo risk score

  useEffect(() => {
    async function loadData() {
      setLoading(true)

      // Check backend health
      const health = await apiClient.checkHealth()
      setBackendOnline(health !== null)

      // Load call history
      const response = await apiClient.listCalls(1, 10)
      if (response) {
        setCalls(response.calls)
        setTotalCalls(response.pagination.total)
      }

      setLoading(false)
    }

    loadData()
  }, [])

  // Compute metrics from real data
  const completedCount = calls.filter(c => c.status === 'completed').length
  const failedCount = calls.filter(c => c.status === 'failed').length
  const processingCount = calls.filter(c => c.status === 'processing' || c.status === 'queued').length

  const metrics = [
    { label: 'Total Analyses', value: String(totalCalls) },
    { label: 'Completed', value: String(completedCount) },
    { label: 'Failed / Errors', value: String(failedCount) },
    { label: 'In Progress', value: String(processingCount) },
  ]

  function formatDate(dateString: string): string {
    try {
      const date = new Date(dateString)
      const now = new Date()
      const diffMs = now.getTime() - date.getTime()
      const diffMins = Math.floor(diffMs / 60000)
      const diffHours = Math.floor(diffMs / 3600000)

      if (diffMins < 1) return 'Just now'
      if (diffMins < 60) return `${diffMins} min ago`
      if (diffHours < 24) return `${diffHours}h ago`

      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      })
    } catch {
      return dateString
    }
  }

  return (
    <div className="overview-page">
      {/* Page heading */}
      <div className="overview-page__heading">
        <h1 className="overview-page__title">Call Security Overview</h1>
        <p className="overview-page__subtitle">
          Monitor call security, explore trust relationships, and manage verification status.
        </p>
      </div>

      {/* Backend connection indicator */}
      <div
        className={`backend-indicator ${
          backendOnline === null
            ? ''
            : backendOnline
            ? 'backend-indicator--ok'
            : 'backend-indicator--error'
        }`}
        role="status"
        aria-live="polite"
      >
        {backendOnline === null ? (
          <><ClockIcon size={13} aria-hidden="true" /> <span>Checking backend...</span></>
        ) : backendOnline ? (
          <><WifiIcon size={13} aria-hidden="true" /> <span>Backend connected</span></>
        ) : (
          <><WifiOffIcon size={13} aria-hidden="true" /> <span>Backend unreachable — showing cached data</span></>
        )}
      </div>

      {/* ── A. Summary cards ─────────────────────────────────────── */}
      <div className="summary-cards" role="list" aria-label="Dashboard summary">
        {metrics.map((metric, i) => (
          <SummaryCard
            key={metric.label}
            label={metric.label}
            value={loading ? '—' : metric.value}
            icon={CARD_CONFIG[i].icon}
            variant={CARD_CONFIG[i].variant}
          />
        ))}
      </div>

      {/* ── Risk Score Gauge (Demo) ──────────────────────────────── */}
      <section className="overview-section" aria-labelledby="risk-score-heading">
        <div className="overview-section__header">
          <h2 id="risk-score-heading" className="section-title">
            System Risk Assessment
          </h2>
          <span className="demo-badge">DEMO DATA</span>
        </div>

        <RiskScoreGauge 
          score={demoRiskScore} 
          showControls={true}
          animated={true}
        />

        <p className="overview-note">
          The Risk Score gauge demonstrates real-time risk assessment visualization.
          In production, this would connect to the AI risk analysis engine to display
          actual threat levels based on call analysis data.
        </p>
      </section>

      {/* ── B. Trust Graph Preview ───────────────────────────────── */}
      <section className="overview-section" aria-labelledby="trust-preview-heading">
        <div className="overview-section__header">
          <h2 id="trust-preview-heading" className="section-title">
            Trust Graph Preview
          </h2>
          <span className="demo-badge">DEMO DATA</span>
        </div>

        <div className="trust-preview-card">
          <p className="trust-preview-card__description">
            The Trust Graph represents known relationships and verification status to help
            assess whether a caller's claimed identity matches established trust relationships.
          </p>

          <TrustGraphPreview />

          <button
            className="btn-primary btn-primary--with-icon"
            onClick={() => onNavigate('trust-graph')}
            aria-label="Open the full Trust Graph page"
          >
            View Full Trust Graph
            <ArrowRightIcon size={15} aria-hidden="true" />
          </button>
        </div>
      </section>

      {/* ── C. Recent Activity (live) ────────────────────────────── */}
      <section className="overview-section" aria-labelledby="recent-activity-heading">
        <div className="overview-section__header">
          <h2 id="recent-activity-heading" className="section-title">
            Recent Activity
          </h2>
          {backendOnline && <span className="demo-badge demo-badge--live">LIVE</span>}
        </div>

        {loading && (
          <div className="activity-notice" role="note">
            Loading recent activity...
          </div>
        )}

        {!loading && calls.length === 0 && (
          <div className="activity-notice" role="note">
            No analyses yet. Upload a recording to get started.
          </div>
        )}

        {!loading && calls.length > 0 && (
          <div className="activity-list" role="list">
            {calls.slice(0, 5).map((entry) => (
              <div key={entry.call_id} className="activity-item" role="listitem">
                <div className="activity-item__contact">{entry.original_filename}</div>
                <div className="activity-item__status">{entry.call_id.slice(0, 8)}...</div>
                <div className="activity-item__meta">
                  <span className={`risk-badge ${RISK_BADGE[entry.status] ?? ''}`}>
                    {STATUS_LABEL[entry.status] ?? entry.status}
                  </span>
                  <span className="activity-item__time">{formatDate(entry.created_at)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── D. Quick Actions ────────────────────────────────────── */}
      <section className="overview-section" aria-labelledby="quick-actions-heading">
        <h2 id="quick-actions-heading" className="section-title">
          Quick Actions
        </h2>
        <div className="quick-actions">
          <button
            className="quick-action-btn"
            onClick={() => onNavigate('analyse')}
            aria-label="Go to Analyse a Call"
          >
            <span className="quick-action-btn__icon quick-action-btn__icon--accent">
              <MicVocalIcon size={18} aria-hidden="true" />
            </span>
            <span className="quick-action-btn__label">Analyse a Call</span>
            <ArrowRightIcon size={14} className="quick-action-btn__arrow" aria-hidden="true" />
          </button>

          <button
            className="quick-action-btn"
            onClick={() => onNavigate('trust-graph')}
            aria-label="Go to Trust Graph"
          >
            <span className="quick-action-btn__icon quick-action-btn__icon--muted">
              <GitForkIcon size={18} aria-hidden="true" />
            </span>
            <span className="quick-action-btn__label">View Trust Graph</span>
            <ArrowRightIcon size={14} className="quick-action-btn__arrow" aria-hidden="true" />
          </button>

          <button
            className="quick-action-btn"
            onClick={() => onNavigate('history')}
            aria-label="Go to Call History"
          >
            <span className="quick-action-btn__icon quick-action-btn__icon--warn">
              <ShieldCheckIcon size={18} aria-hidden="true" />
            </span>
            <span className="quick-action-btn__label">View Call History</span>
            <ArrowRightIcon size={14} className="quick-action-btn__arrow" aria-hidden="true" />
          </button>
        </div>
      </section>
    </div>
  )
}
