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
  /** Optional: name of the recording being reported on. */
  recordingName?: string
  /** Optional: date/time the analysis was submitted. */
  submittedAt?: string
  onBack?: () => void
}

export function AnalysisReport({
  recordingName,
  submittedAt,
  onBack,
}: AnalysisReportProps) {
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

      {/* Frontend-only notice */}
      <aside className="info-card info-card--warn" aria-label="Backend status notice">
        <InfoIcon size={14} aria-hidden="true" className="info-card__icon" />
        <p className="info-card__text">
          <strong>Analysis not yet available.</strong> This report layout is ready to receive
          results once the backend service is connected. No analysis has been performed and no
          results are shown below.
        </p>
      </aside>

      {/* 1. Recording information */}
      <ReportSection
        icon={<FileAudioIcon size={16} strokeWidth={1.75} />}
        title="Recording Information"
        id="report-recording-info"
      >
        <dl className="report-dl">
          <div className="report-dl__row">
            <dt>File name</dt>
            <dd>{recordingName ?? <PendingBlock label="No file selected" />}</dd>
          </div>
          <div className="report-dl__row">
            <dt>Submitted</dt>
            <dd>
              {submittedAt ?? <PendingBlock label="Not submitted" />}
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
        <div className="report-status-badge report-status-badge--pending">
          <ClockIcon size={14} aria-hidden="true" />
          <span>Awaiting backend connection</span>
        </div>
        <p className="report-caption">
          Analysis will be initiated once the backend service is available. The status will update
          automatically when results are received.
        </p>
      </ReportSection>

      {/* 3. Voice-authenticity findings */}
      <ReportSection
        icon={<MicVocalIcon size={16} strokeWidth={1.75} />}
        title="Voice-Authenticity Findings"
        id="report-voice-auth"
      >
        <PendingBlock label="No voice-authenticity analysis available — backend not connected." />
        <p className="report-caption">
          This section will show whether the voice in the recording exhibits characteristics
          consistent with AI synthesis or voice cloning, as determined by the backend model.
        </p>
      </ReportSection>

      {/* 4. Social-engineering and behavioural evidence */}
      <ReportSection
        icon={<UserSearchIcon size={16} strokeWidth={1.75} />}
        title="Social-Engineering Evidence"
        id="report-social-eng"
      >
        <PendingBlock label="No behavioural evidence available — backend not connected." />
        <p className="report-caption">
          When analysis is complete, this section will list identified linguistic patterns,
          urgency signals, authority claims, and other social-engineering indicators detected
          in the call.
        </p>
      </ReportSection>

      {/* 5. Trust / risk assessment */}
      <ReportSection
        icon={<ShieldIcon size={16} strokeWidth={1.75} />}
        title="Risk Assessment"
        id="report-risk"
      >
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
      </ReportSection>

      {/* 6. Explanation and recommended actions */}
      <ReportSection
        icon={<AlertTriangleIcon size={16} strokeWidth={1.75} />}
        title="Explanation & Recommended Actions"
        id="report-explanation"
      >
        <PendingBlock label="Explanation not available — backend not connected." />
        <p className="report-caption">
          This section will describe the basis for the risk assessment and list recommended
          verification steps (e.g. call-back on a verified number, identity confirmation,
          report to fraud team) once the backend provides results.
        </p>
      </ReportSection>

      {/* 7. Transcript */}
      <ReportSection
        icon={<FileTextIcon size={16} strokeWidth={1.75} />}
        title="Transcript"
        id="report-transcript"
      >
        <PendingBlock label="Transcript not available — backend not connected." />
        <p className="report-caption">
          Transcripts are generated server-side. A transcript will only be shown here when
          a genuine one is returned by the backend — this section will never display guessed
          or fabricated text.
        </p>
      </ReportSection>
    </div>
  )
}
