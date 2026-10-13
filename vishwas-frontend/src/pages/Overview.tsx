import {
  AlertTriangleIcon,
  ArrowRightIcon,
  ClockIcon,
  GitForkIcon,
  MicVocalIcon,
  PhoneCallIcon,
  ShieldCheckIcon,
  UsersIcon,
} from 'lucide-react'
import { SummaryCard } from '../components/overview/SummaryCard'
import { TrustGraphPreview } from '../components/overview/TrustGraphPreview'
import {
  DEMO_ACTIVITY,
  DEMO_METRICS,
} from '../data/sampleData'
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
  low:    'badge--low',
  medium: 'badge--medium',
  high:   'badge--high',
}

const RISK_LABEL: Record<string, string> = {
  low:    'Low risk',
  medium: 'Medium risk',
  high:   'High risk',
}

/**
 * Overview page — redesigned dashboard.
 * All metrics, contacts, and activity entries are illustrative demo data only.
 */
export function Overview({ onNavigate }: OverviewProps) {
  return (
    <div className="overview-page">
      {/* Page heading */}
      <div className="overview-page__heading">
        <h1 className="overview-page__title">Call Security Overview</h1>
        <p className="overview-page__subtitle">
          Monitor call security, explore trust relationships, and manage verification status.
        </p>
      </div>

      {/* ── A. Summary cards ─────────────────────────────────────── */}
      <div className="summary-cards" role="list" aria-label="Dashboard summary">
        {DEMO_METRICS.map((metric, i) => (
          <SummaryCard
            key={metric.label}
            label={metric.label}
            value={metric.value}
            icon={CARD_CONFIG[i].icon}
            variant={CARD_CONFIG[i].variant}
          />
        ))}
      </div>

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

      {/* ── C. Recent Activity ───────────────────────────────────── */}
      <section className="overview-section" aria-labelledby="recent-activity-heading">
        <div className="overview-section__header">
          <h2 id="recent-activity-heading" className="section-title">
            Recent Activity
          </h2>
          <span className="demo-badge">DEMO DATA</span>
        </div>

        <div className="activity-notice" role="note">
          Illustrative demo data — not real call records.
        </div>

        <div className="activity-list" role="list">
          {DEMO_ACTIVITY.map((entry) => (
            <div key={entry.id} className="activity-item" role="listitem">
              <div className="activity-item__contact">{entry.contact}</div>
              <div className="activity-item__status">{entry.trustStatus}</div>
              <div className="activity-item__meta">
                <span className={`risk-badge ${RISK_BADGE[entry.riskLevel]}`}>
                  {RISK_LABEL[entry.riskLevel]}
                </span>
                <span className="activity-item__time">{entry.time}</span>
              </div>
            </div>
          ))}
        </div>
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
