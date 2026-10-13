import { useState } from 'react'
import { AlertCircleIcon, FileAudioIcon, MicVocalIcon, CheckCircleIcon, LoaderIcon } from 'lucide-react'
import { AudioUpload, type AudioFileState } from '../components/shared/AudioUpload'
import { apiClient, type UploadResponse, type CallStatusResponse } from '../services/api'

interface AnalyseACallProps {
  /** Called when the user wants to view the analysis report. */
  onViewReport?: () => void
}

type AnalysisState = 
  | { type: 'idle' }
  | { type: 'uploading' }
  | { type: 'polling'; callId: string }
  | { type: 'completed'; callId: string }
  | { type: 'error'; message: string }

/**
 * Analyse a Call page.
 *
 * Lets the user upload an audio file and tracks the analysis progress
 * by polling the backend API.
 */
export function AnalyseACall({ onViewReport }: AnalyseACallProps) {
  const [fileState, setFileState] = useState<AudioFileState | null>(null)
  const [analysisState, setAnalysisState] = useState<AnalysisState>({ type: 'idle' })
  const [currentStatus, setCurrentStatus] = useState<string>('')

  const hasValidFile = fileState !== null && fileState.error === null

  async function handleStartAnalysis() {
    if (!hasValidFile || !fileState?.file) return

    setAnalysisState({ type: 'uploading' })

    try {
      // Upload the file
      const uploadResponse = await apiClient.uploadRecording(fileState.file)

      if (!uploadResponse) {
        setAnalysisState({ 
          type: 'error', 
          message: 'Upload failed. Please check backend connection and try again.' 
        })
        return
      }

      // Start polling for status
      setAnalysisState({ type: 'polling', callId: uploadResponse.call_id })
      setCurrentStatus(uploadResponse.status)
      pollAnalysisStatus(uploadResponse.call_id)

    } catch (error) {
      console.error('Analysis error:', error)
      setAnalysisState({ 
        type: 'error', 
        message: error instanceof Error ? error.message : 'Unknown error occurred' 
      })
    }
  }

  async function pollAnalysisStatus(callId: string) {
    const maxAttempts = 60 // Poll for up to 60 seconds
    let attempts = 0

    const pollInterval = setInterval(async () => {
      attempts++

      if (attempts > maxAttempts) {
        clearInterval(pollInterval)
        setAnalysisState({ 
          type: 'error', 
          message: 'Analysis timeout. Please check the History page for results.' 
        })
        return
      }

      const status = await apiClient.getCallStatus(callId)

      if (!status) {
        // Continue polling even if one request fails
        return
      }

      setCurrentStatus(status.status)

      if (status.status === 'completed') {
        clearInterval(pollInterval)
        setAnalysisState({ type: 'completed', callId })
      } else if (status.status === 'failed') {
        clearInterval(pollInterval)
        setAnalysisState({ 
          type: 'error', 
          message: status.error_message || 'Analysis failed' 
        })
      }
    }, 1000) // Poll every second
  }

  function handleFileChange(state: AudioFileState | null) {
    setFileState(state)
    // Reset analysis state when user picks a new file
    if (analysisState.type !== 'idle') {
      setAnalysisState({ type: 'idle' })
    }
  }

  function renderStatusMessage() {
    switch (analysisState.type) {
      case 'uploading':
        return (
          <div className="analysis-status analysis-status--uploading" role="status" aria-live="polite">
            <LoaderIcon size={16} className="analysis-status__spinner" aria-hidden="true" />
            <div className="analysis-status__text">
              <strong>Uploading recording...</strong>
            </div>
          </div>
        )

      case 'polling':
        return (
          <div className="analysis-status analysis-status--processing" role="status" aria-live="polite">
            <LoaderIcon size={16} className="analysis-status__spinner" aria-hidden="true" />
            <div className="analysis-status__text">
              <strong>Analysis in progress...</strong>
              <span> Status: {currentStatus}</span>
            </div>
          </div>
        )

      case 'completed':
        return (
          <div className="analysis-status analysis-status--completed" role="status" aria-live="polite">
            <CheckCircleIcon size={16} className="analysis-status__icon" aria-hidden="true" />
            <div className="analysis-status__text">
              <strong>Analysis complete!</strong>
              <span> View the report to see results.</span>
            </div>
          </div>
        )

      case 'error':
        return (
          <div className="analysis-status analysis-status--error" role="alert" aria-live="assertive">
            <AlertCircleIcon size={16} className="analysis-status__icon" aria-hidden="true" />
            <div className="analysis-status__text">
              <strong>Analysis failed:</strong>
              <span> {analysisState.message}</span>
            </div>
          </div>
        )

      default:
        return null
    }
  }

  const isAnalyzing = analysisState.type === 'uploading' || analysisState.type === 'polling'
  const canViewReport = analysisState.type === 'completed'

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
          disabled={isAnalyzing}
        />

        {/* Status message */}
        {renderStatusMessage()}

        {/* Primary action */}
        <div className="analyse-actions">
          <button
            className="btn-primary"
            disabled={!hasValidFile || isAnalyzing}
            onClick={handleStartAnalysis}
            aria-disabled={!hasValidFile || isAnalyzing}
          >
            {isAnalyzing ? 'Analysing...' : 'Start Analysis'}
          </button>
          
          {canViewReport && onViewReport && (
            <button
              className="btn-primary"
              onClick={onViewReport}
              aria-label="View analysis report"
            >
              View Report
            </button>
          )}

          {onViewReport && !canViewReport && (
            <button
              className="btn-ghost btn-ghost--sm"
              onClick={onViewReport}
              aria-label="View analysis report layout"
            >
              View Report Layout
            </button>
          )}
          
          {!hasValidFile && !isAnalyzing && (
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
          <strong>Backend Integration:</strong> This interface uploads recordings to the VISHWAS backend
          for real-time voice authenticity analysis. Results are based on the configured analysis mode
          (mock or real).
        </p>
      </aside>
    </div>
  )
}

