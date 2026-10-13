import { useEffect, useState } from 'react'
import {
  AlertTriangleIcon,
  ClockIcon,
  FileAudioIcon,
  FileTextIcon,
  InfoIcon,
  MicVocalIcon,
  ShieldIcon,
  ShieldOffIcon,
  UserSearchIcon,
} from 'lucide-react'
import { apiClient, type AnalysisReportResponse } from '../services/api'

/**
 * Analysis Report page.
 *
 * Presents the structured report layout that will be populated once the
 * backend returns real results. All sections show honest "not yet analysed"
 * states — no fabricated scores, probabilities, or detection results.
 *
 * This page is shown when the user navigates to a specific call's report.
 * The backend integration will supply props / URL params to fill the sections.
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
            <dt>Duration</dt>
            <dd>
              <PendingBlock label="Available after analysis" />
            </dd>
          </div>
          <div className="report-dl__row">
            <dt>Sample rate</dt>
            <dd>
              <PendingBlock label="Available after analysis" />
            </dd>
          </div>
        </dl>
      </ReportSection>

      {/* 2. Analysis status */}
      <ReportSection
        icon={<ClockIcon size={16} strokeWidth={1.75} />}
        title="Analysis Status"
        id="report-status"
      >
        {report ? (
          <>
            <div className="report-status-badge report-status-badge--completed">
              <ShieldIcon size={14} aria-hidden="true" />
              <span>Completed</span>
            </div>
            <p className="report-caption">
              Analysis mode: {report.analysis_mode}
            </p>
          </>
        ) : (
          <>
            <div className="report-status-badge report-status-badge--pending">
              <ClockIcon size={14} aria-hidden="true" />
              <span>Awaiting backend connection</span>
            </div>
            <p className="report-caption">
              Analysis will be initiated once the backend service is available. The status will update
              automatically when results are received.
            </p>
          </>
        )}
      </ReportSection>

      {/* 3. Voice-authenticity findings */}
      <ReportSection
        icon={<MicVocalIcon size={16} strokeWidth={1.75} />}
        title="Voice-Authenticity Findings"
        id="report-voice-auth"
      >
        {report?.agent_findings && report.agent_findings.length > 0 ? (
          <>
            <dl className="report-dl">
              {report.agent_findings.map((finding, idx) => (
                <div key={idx} className="report-dl__row">
                  <dt>{finding.check_name}</dt>
                  <dd>
                    <span className={`report-finding-badge report-finding-badge--${finding.status}`}>
                      {finding.status}
                    </span>
                    {' '}
                    {finding.details}
                    {finding.confidence > 0 && (
                      <span className="report-caption"> (confidence: {(finding.confidence * 100).toFixed(0)}%)</span>
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          </>
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

      {/* 5. Trust / risk assessment */}
      <ReportSection
        icon={<ShieldIcon size={16} strokeWidth={1.75} />}
        title="Risk Assessment"
        id="report-risk"
      >
        {report ? (
          <div className="report-risk-result">
            <div className={`report-risk-badge report-risk-badge--${report.risk_level}`}>
              {report.risk_level.toUpperCase()}
            </div>
            {report.risk_score !== undefined && (
              <p className="report-caption">
                Score: {report.risk_score.toFixed(2)}
              </p>
            )}
          </div>
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
                <strong>[{segment.speaker}]</strong> {segment.text}
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
