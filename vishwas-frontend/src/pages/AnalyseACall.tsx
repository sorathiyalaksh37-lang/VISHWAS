import { useState } from 'react'
import { AlertCircleIcon, FileAudioIcon, MicVocalIcon } from 'lucide-react'
import { AudioUpload, type AudioFileState } from '../components/shared/AudioUpload'

interface AnalyseACallProps {
  /** Called when the user wants to view the analysis report. */
  onViewReport?: () => void
}

/**
 * Analyse a Call page.
 *
 * Lets the user select an audio file and shows a clear, non-deceptive message
 * when Start Analysis is clicked — because the backend is not connected.
 *
 * IMPORTANT:
 *  - No file is uploaded anywhere.
 *  - No progress is simulated.
 *  - No trust score or detection results are fabricated.
 */
export function AnalyseACall({ onViewReport }: AnalyseACallProps) {
  const [fileState, setFileState] = useState<AudioFileState | null>(null)
  const [analysisAttempted, setAnalysisAttempted] = useState(false)

  const hasValidFile = fileState !== null && fileState.error === null

  function handleStartAnalysis() {
    if (!hasValidFile) return
    setAnalysisAttempted(true)
  }

  function handleFileChange(state: AudioFileState | null) {
    setFileState(state)
    // Clear the "attempted" banner when the user picks a new file or clears
    if (analysisAttempted) setAnalysisAttempted(false)
  }

  return (
    <div className="page-content">
      {/* Page heading */}
      <div className="page-heading">
        <div className="page-heading__icon-wrap" aria-hidden="true">
          <MicVocalIcon size={20} strokeWidth={1.75} />
        </div>
        <div>
          <h1 className="page-heading__title">Analyse a Call</h1>
          <p className="page-heading__subtitle">
            Verify voice authenticity and assess potential social-engineering risk.
          </p>
        </div>
      </div>

      {/* Upload card */}
      <section className="upload-panel" aria-labelledby="analyse-upload-heading">
        <div className="upload-panel__header">
          <div className="upload-panel__icon" aria-hidden="true">
            <FileAudioIcon size={20} strokeWidth={1.75} />
          </div>
          <div>
            <h2 id="analyse-upload-heading" className="upload-panel__title">
              Select a Recording
            </h2>
            <p className="upload-panel__subtitle">
              Drop an audio file below or use the button to browse. Accepted formats: WAV, MP3, M4A.
            </p>
          </div>
        </div>

        <AudioUpload
          inputId="analyse-audio-file-input"
          fileState={fileState}
          onFileChange={handleFileChange}
        />

        {/* Backend unavailable notice shown after user clicks Start Analysis */}
        {analysisAttempted && (
          <div className="analysis-unavailable-notice" role="alert" aria-live="assertive">
            <AlertCircleIcon size={16} aria-hidden="true" className="analysis-unavailable-notice__icon" />
            <div className="analysis-unavailable-notice__text">
              <strong>Analysis is unavailable until the backend is connected.</strong>
              <span> No analysis has been performed.</span>
            </div>
          </div>
        )}

        {/* Primary action */}
        <div className="analyse-actions">
          <button
            className="btn-primary"
            disabled={!hasValidFile}
            onClick={handleStartAnalysis}
            aria-disabled={!hasValidFile}
          >
            Start Analysis
          </button>
          {onViewReport && (
            <button
              className="btn-ghost btn-ghost--sm"
              onClick={onViewReport}
              aria-label="View analysis report layout"
            >
              View Report Layout
            </button>
          )}
          {!hasValidFile && (
            <p className="analyse-actions__hint">
              {fileState?.error
                ? 'Fix the file error above to continue.'
                : 'Select a valid audio file to enable analysis.'}
            </p>
          )}
        </div>
      </section>

      {/* Informational note */}
      <aside className="info-card" aria-label="Important note">
        <p className="info-card__text">
          <strong>Frontend-only mode:</strong> This interface does not upload recordings, simulate
          analysis progress, or generate detection results. Voice-authenticity analysis requires a
          connected backend service.
        </p>
      </aside>
    </div>
  )
}
