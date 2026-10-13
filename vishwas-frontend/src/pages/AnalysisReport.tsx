import { useEffect, useState } from 'react'
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  FileAudioIcon,
  FileTextIcon,
  InfoIcon,
  MicVocalIcon,
  ShieldIcon,
  ShieldOffIcon,
  UserSearchIcon,
  XCircleIcon,
  ZapIcon,
} from 'lucide-react'
import { apiClient, type AnalysisReportResponse } from '../services/api'

/**
 * Analysis Report page.
 *
 * Presents the structured report populated with real backend results.
 * All sections dynamically render data from the API response including
 * v3 Trust Engine fields: category scores, fired rules, verification,
 * voice evidence, and killchain stage.
 */

interface ReportSectionProps {
  icon: React.ReactNode
  title: string
  id: string
  children: React.ReactNode
}

function ReportSection({ icon, title, id, children }: ReportSectionProps) {
  return (
    <section className="report-section" aria-labelledby={id}>
      <div className="report-section__header">
        <div className="report-section__icon" aria-hidden="true">
          {icon}
        </div>
        <h2 id={id} className="report-section__title">
          {title}
        </h2>
      </div>
      <div className="report-section__body">{children}</div>
    </section>
  )
}

function PendingBlock({ label }: { label: string }) {
  return (
    <div className="report-pending">
      <ClockIcon size={14} aria-hidden="true" className="report-pending__icon" />
      <span className="report-pending__text">{label}</span>
    </div>
  )
}

interface AnalysisReportProps {
  /** Optional: call ID to fetch the report for. */
  callId?: string
  /** Optional: name of the recording being reported on. */
  recordingName?: string
  /** Optional: date/time the analysis was submitted. */
  submittedAt?: string
  onBack?: () => void
}

export function AnalysisReport({
  callId,
  recordingName,
  submittedAt,
  onBack,
}: AnalysisReportProps) {
  const [report, setReport] = useState<AnalysisReportResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!callId) return

    async function fetchReport() {
      setLoading(true)
      setError(null)
      const data = await apiClient.getReport(callId!)
      if (data) {
        setReport(data)
      } else {
        setError('Failed to load report. The backend may be unavailable.')
      }
      setLoading(false)
    }

    fetchReport()
  }, [callId])

  /** Map severity to a display-friendly badge style. */
  function severityToBadgeClass(severity: string): string {
    switch (severity.toLowerCase()) {
      case 'critical': return 'report-finding-badge--fail'
      case 'high': return 'report-finding-badge--fail'
      case 'medium': return 'report-finding-badge--warning'
      case 'low': return 'report-finding-badge--pass'
      default: return 'report-finding-badge--warning'
    }
  }

  /** Format a signal name to be more readable. */
  function formatSignal(signal: string): string {
    return signal
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase())
  }

  /** Get risk badge CSS class from level string. */
  function riskLevelClass(level: string): string {
    switch (level.toUpperCase()) {
      case 'CRITICAL': return 'report-risk-badge--critical'
      case 'HIGH': return 'report-risk-badge--high'
      case 'MEDIUM': return 'report-risk-badge--medium'
      case 'LOW': return 'report-risk-badge--low'
      default: return ''
    }
  }

  /** Category score bar. */
  function CategoryBar({ label, value, max }: { label: string; value: number | null | undefined; max: number }) {
    const v = value ?? 0
    const pct = Math.min(100, (v / max) * 100)
    const color = v === 0 ? 'var(--color-surface-alt)' : v >= max * 0.8 ? 'var(--color-critical)' : v >= max * 0.5 ? 'var(--color-warn)' : 'var(--color-accent)'
    return (
      <div className="category-bar">
        <div className="category-bar__label">{label}</div>
        <div className="category-bar__track">
          <div className="category-bar__fill" style={{ width: `${pct}%`, backgroundColor: color }} />
        </div>
        <div className="category-bar__value">{v}/{max}</div>
      </div>
    )
  }

  return (
    <div className="page-content">
      {/* Page heading */}
      <div className="report-page-heading">
        {onBack && (
          <button
            className="btn-ghost btn-ghost--sm report-back-btn"
            onClick={onBack}
            aria-label="Go back"
          >
            ← Back
          </button>
        )}
        <div className="page-heading">
          <div className="page-heading__icon-wrap" aria-hidden="true">
            <FileTextIcon size={20} strokeWidth={1.75} />
          </div>
          <div>
            <h1 className="page-heading__title">Analysis Report</h1>
            <p className="page-heading__subtitle">
              {recordingName
                ? `Report for: ${recordingName}`
                : report
                  ? `Report for call: ${report.call_id.slice(0, 8)}...`
                  : 'No recording selected for this report.'}
            </p>
          </div>
        </div>
      </div>

      {/* Status message */}
      {loading && (
        <aside className="info-card" aria-live="polite">
          <InfoIcon size={14} aria-hidden="true" className="info-card__icon" />
          <p className="info-card__text">Loading report...</p>
        </aside>
      )}
      {error && (
        <aside className="info-card info-card--warn" aria-label="Error loading report">
          <InfoIcon size={14} aria-hidden="true" className="info-card__icon" />
          <p className="info-card__text">
            <strong>Error:</strong> {error}
          </p>
        </aside>
      )}
      {!callId && !report && (
        <aside className="info-card info-card--warn" aria-label="Backend status notice">
          <InfoIcon size={14} aria-hidden="true" className="info-card__icon" />
          <p className="info-card__text">
            <strong>Analysis not yet available.</strong> This report layout is ready to receive
            results once the backend service is connected. No analysis has been performed and no
            results are shown below.
          </p>
        </aside>
      )}

      {/* 1. Recording information */}
      <ReportSection
        icon={<FileAudioIcon size={16} strokeWidth={1.75} />}
        title="Recording Information"
        id="report-recording-info"
      >
        <dl className="report-dl">
          <div className="report-dl__row">
            <dt>File name</dt>
            <dd>{recordingName ?? (report ? report.call_id : <PendingBlock label="No file selected" />)}</dd>
          </div>
          <div className="report-dl__row">
            <dt>Submitted</dt>
            <dd>
              {submittedAt ?? (report ? new Date(report.created_at).toLocaleString() : <PendingBlock label="Not submitted" />)}
            </dd>
          </div>
          <div className="report-dl__row">
            <dt>Completed</dt>
            <dd>
              {report?.completed_at
                ? new Date(report.completed_at).toLocaleString()
                : <PendingBlock label="Available after analysis" />}
            </dd>
          </div>
          <div className="report-dl__row">
            <dt>Analysis mode</dt>
            <dd>
              {report
                ? <span className="report-status-badge report-status-badge--completed">{report.analysis_mode.toUpperCase()}</span>
                : <PendingBlock label="Available after analysis" />}
            </dd>
          </div>
          {report?.killchain_stage && (
            <div className="report-dl__row">
              <dt>Kill-chain stage</dt>
              <dd>
                <span className="report-status-badge report-status-badge--killchain">
                  {report.killchain_stage}
                </span>
              </dd>
            </div>
          )}
        </dl>
      </ReportSection>

      {/* 2. Risk Assessment — primary score + category breakdown */}
      <ReportSection
        icon={<ShieldIcon size={16} strokeWidth={1.75} />}
        title="Risk Assessment"
        id="report-risk"
      >
        {report ? (
          <>
            <div className="report-risk-result">
              <div className={`report-risk-badge ${riskLevelClass(report.level)}`}>
                {report.level.toUpperCase()}
              </div>
              <p className="report-risk-score">
                Score: <strong>{report.score}</strong>/100
              </p>
            </div>

            {/* Category score bars */}
            {report.category_scores && (
              <div className="category-bars" aria-label="Category score breakdown">
                <CategoryBar label="Identity" value={report.category_scores.identity} max={25} />
                <CategoryBar label="Requests" value={report.category_scores.request} max={30} />
                <CategoryBar label="Behavior" value={report.category_scores.behavior} max={20} />
                <CategoryBar label="Channel" value={report.category_scores.channel} max={15} />
                <CategoryBar label="Voice" value={report.category_scores.voice} max={10} />
              </div>
            )}

            {/* Fired rules */}
            {report.fired_rules && report.fired_rules.length > 0 && (
              <div className="fired-rules">
                <h3 className="report-subsection-title">Triggered Rules</h3>
                <div className="fired-rules__list">
                  {report.fired_rules.map((rule, idx) => (
                    <span key={idx} className="fired-rule-chip">
                      <ZapIcon size={10} aria-hidden="true" />
                      {rule}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="report-risk-placeholder">
            <ShieldOffIcon
              size={32}
              strokeWidth={1.25}
              className="report-risk-placeholder__icon"
              aria-hidden="true"
            />
            <p className="report-risk-placeholder__label">Risk level not determined</p>
            <p className="report-risk-placeholder__body">
              A risk assessment requires a completed backend analysis. No score has been
              generated and no risk level has been assigned.
            </p>
          </div>
        )}
      </ReportSection>

      {/* 3. Voice-authenticity findings */}
      <ReportSection
        icon={<MicVocalIcon size={16} strokeWidth={1.75} />}
        title="Voice-Authenticity Findings"
        id="report-voice-auth"
      >
        {/* Voice layer status */}
        {report?.voice ? (
          <div className="voice-evidence">
            <dl className="report-dl">
              <div className="report-dl__row">
                <dt>Status</dt>
                <dd>
                  <span className={`report-status-badge report-status-badge--${
                    report.voice.status === 'ok' ? 'completed' : 'pending'
                  }`}>
                    {report.voice.status === 'ok' ? (
                      <><CheckCircleIcon size={12} aria-hidden="true" /> Analysed</>
                    ) : report.voice.status === 'inconclusive' ? (
                      <><InfoIcon size={12} aria-hidden="true" /> Inconclusive</>
                    ) : (
                      <><XCircleIcon size={12} aria-hidden="true" /> Unavailable</>
                    )}
                  </span>
                </dd>
              </div>
              {report.voice.spoof_prob != null && (
                <div className="report-dl__row">
                  <dt>Spoof probability</dt>
                  <dd>
                    <strong>{(report.voice.spoof_prob * 100).toFixed(1)}%</strong>
                    <span className="report-caption">
                      {report.voice.spoof_prob >= 0.8
                        ? ' — High risk of synthetic speech'
                        : report.voice.spoof_prob >= 0.6
                        ? ' — Moderate risk of synthetic speech'
                        : ' — Low risk indicators'}
                    </span>
                  </dd>
                </div>
              )}
              {report.voice.windows_analyzed != null && (
                <div className="report-dl__row">
                  <dt>Windows analysed</dt>
                  <dd>{report.voice.windows_analyzed}</dd>
                </div>
              )}
              {report.voice.model && (
                <div className="report-dl__row">
                  <dt>Model</dt>
                  <dd className="report-caption">{report.voice.model}</dd>
                </div>
              )}
            </dl>
            {report.voice.status !== 'ok' && (
              <p className="report-caption">
                Voice analysis was not available for this recording. This does not confirm or deny
                voice authenticity.
              </p>
            )}
          </div>
        ) : report?.agent_findings && report.agent_findings.length > 0 ? (
          <dl className="report-dl">
            {report.agent_findings.map((finding, idx) => (
              <div key={idx} className="report-dl__row">
                <dt>{formatSignal(finding.signal)}</dt>
                <dd>
                  <span className={`report-finding-badge ${severityToBadgeClass(finding.severity)}`}>
                    {finding.severity}
                  </span>
                  {' '}
                  {finding.evidence_text}
                  {finding.confidence != null && finding.confidence > 0 && (
                    <span className="report-caption"> (confidence: {(finding.confidence * 100).toFixed(0)}%)</span>
                  )}
                  <span className="report-caption"> — Agent: {finding.agent}</span>
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <>
            <PendingBlock label="No voice-authenticity analysis available — backend not connected." />
            <p className="report-caption">
              This section will show whether the voice in the recording exhibits characteristics
              consistent with AI synthesis or voice cloning, as determined by the backend model.
            </p>
          </>
        )}
      </ReportSection>

      {/* 4. Social-engineering and behavioural evidence */}
      <ReportSection
        icon={<UserSearchIcon size={16} strokeWidth={1.75} />}
        title="Social-Engineering Evidence"
        id="report-social-eng"
      >
        {report?.reasons && report.reasons.length > 0 ? (
          <ul className="report-list">
            {report.reasons.map((reason, idx) => (
              <li key={idx}>{reason}</li>
            ))}
          </ul>
        ) : (
          <>
            <PendingBlock label="No behavioural evidence available — backend not connected." />
            <p className="report-caption">
              When analysis is complete, this section will list identified linguistic patterns,
              urgency signals, authority claims, and other social-engineering indicators detected
              in the call.
            </p>
          </>
        )}
      </ReportSection>

      {/* 5. Verification recommendation */}
      {report?.verification && (
        <ReportSection
          icon={<CheckCircleIcon size={16} strokeWidth={1.75} />}
          title="Verification Recommendation"
          id="report-verification"
        >
          <dl className="report-dl">
            {report.verification.action && (
              <div className="report-dl__row">
                <dt>Action</dt>
                <dd><strong>{report.verification.action}</strong></dd>
              </div>
            )}
            {report.verification.target && (
              <div className="report-dl__row">
                <dt>Recommendation</dt>
                <dd>{report.verification.target}</dd>
              </div>
            )}
          </dl>
        </ReportSection>
      )}

      {/* 6. Explanation and recommended actions */}
      <ReportSection
        icon={<AlertTriangleIcon size={16} strokeWidth={1.75} />}
        title="Explanation & Recommended Actions"
        id="report-explanation"
      >
        {report && (report.recommended_actions.length > 0 || report.warnings.length > 0) ? (
          <>
            {report.warnings.length > 0 && (
              <>
                <h3 className="report-subsection-title">Warnings</h3>
                <ul className="report-list">
                  {report.warnings.map((warning, idx) => (
                    <li key={idx}>{warning}</li>
                  ))}
                </ul>
              </>
            )}
            {report.recommended_actions.length > 0 && (
              <>
                <h3 className="report-subsection-title">Recommended Actions</h3>
                <ul className="report-list">
                  {report.recommended_actions.map((action, idx) => (
                    <li key={idx}>{action}</li>
                  ))}
                </ul>
              </>
            )}
          </>
        ) : (
          <>
            <PendingBlock label="Explanation not available — backend not connected." />
            <p className="report-caption">
              This section will describe the basis for the risk assessment and list recommended
              verification steps (e.g. call-back on a verified number, identity confirmation,
              report to fraud team) once the backend provides results.
            </p>
          </>
        )}
      </ReportSection>

      {/* 7. Transcript */}
      <ReportSection
        icon={<FileTextIcon size={16} strokeWidth={1.75} />}
        title="Transcript"
        id="report-transcript"
      >
        {report?.transcript?.segments && report.transcript.segments.length > 0 ? (
          <div className="report-transcript">
            {report.transcript.segments.map((segment, idx) => (
              <p key={idx} className="report-transcript__segment">
                <strong>[{segment.speaker ?? 'Speaker'}]</strong> {segment.text}
                <span className="report-caption"> ({segment.start.toFixed(1)}s–{segment.end.toFixed(1)}s)</span>
              </p>
            ))}
          </div>
        ) : (
          <>
            <PendingBlock label="Transcript not available — backend not connected." />
            <p className="report-caption">
              Transcripts are generated server-side. A transcript will only be shown here when
              a genuine one is returned by the backend — this section will never display guessed
              or fabricated text.
            </p>
          </>
        )}
      </ReportSection>
    </div>
  )
}
