import { useState, useCallback, useRef, useEffect } from 'react'
import {
  MicVocalIcon, UploadCloudIcon, FileAudioIcon, CheckCircle2Icon,
  AlertCircleIcon, XIcon, ShieldIcon, ZapIcon, BrainCircuitIcon,
  WavesIcon, ArrowRightIcon, RefreshCwIcon, ClockIcon,
} from 'lucide-react'
import { apiClient } from '../services/api'

interface AnalyseACallProps {
  onViewReport?: (callId: string) => void
}

type Stage = 'idle' | 'uploading' | 'queued' | 'processing' | 'completed' | 'failed'

const PIPELINE_STEPS = [
  { id: 'upload',      icon: UploadCloudIcon,   label: 'Uploading',          desc: 'Securely transferring file' },
  { id: 'queued',      icon: ClockIcon,          label: 'In Queue',           desc: 'Awaiting processing slot' },
  { id: 'asr',         icon: WavesIcon,          label: 'Transcribing',       desc: 'Running faster-whisper ASR' },
  { id: 'intelligence',icon: BrainCircuitIcon,   label: 'Intelligence',       desc: 'Trust Engine assessment' },
  { id: 'done',        icon: CheckCircle2Icon,   label: 'Complete',           desc: 'Report ready' },
]

function getActiveStep(stage: Stage): number {
  switch (stage) {
    case 'uploading':  return 0
    case 'queued':     return 1
    case 'processing': return 2
    default:           return stage === 'completed' ? 4 : -1
  }
}

const ACCEPTED_TYPES = ['.wav', '.mp3', '.m4a', '.ogg', '.flac']
const MAX_SIZE_MB = 50

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function AnalyseACall({ onViewReport }: AnalyseACallProps) {
  const [dragOver, setDragOver] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [stage, setStage] = useState<Stage>('idle')
  const [callId, setCallId] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [analysisMode, setAnalysisMode] = useState<string>('')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Elapsed timer during analysis
  useEffect(() => {
    if (stage === 'uploading' || stage === 'queued' || stage === 'processing') {
      timerRef.current = setInterval(() => setElapsedSeconds(s => s + 1), 1000)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [stage])

  function validateFile(f: File): string | null {
    const ext = '.' + f.name.split('.').pop()?.toLowerCase()
    if (!ACCEPTED_TYPES.includes(ext)) return `Unsupported format. Use: ${ACCEPTED_TYPES.join(', ')}`
    if (f.size > MAX_SIZE_MB * 1024 * 1024) return `File too large. Max ${MAX_SIZE_MB}MB.`
    return null
  }

  function handleFileSelect(f: File) {
    const err = validateFile(f)
    setFile(f)
    setFileError(err)
    setStage('idle')
    setCallId(null)
    setElapsedSeconds(0)
    setUploadProgress(0)
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) handleFileSelect(dropped)
  }, [])

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) handleFileSelect(f)
  }

  async function startAnalysis() {
    if (!file || fileError) return
    setStage('uploading')
    setErrorMsg('')
    setElapsedSeconds(0)

    // Fake upload progress animation
    let prog = 0
    const progInterval = setInterval(() => {
      prog = Math.min(prog + Math.random() * 15, 90)
      setUploadProgress(prog)
    }, 200)

    try {
      const upload = await apiClient.uploadRecording(file)
      clearInterval(progInterval)
      setUploadProgress(100)

      if (!upload) {
        setStage('failed')
        setErrorMsg('Upload failed. Check backend connection.')
        return
      }

      setCallId(upload.call_id)
      setAnalysisMode(upload.analysis_mode)
      setStage('queued')

      // Poll for completion
      const maxAttempts = 120
      let attempts = 0
      const poll = setInterval(async () => {
        attempts++
        if (attempts > maxAttempts) {
          clearInterval(poll)
          setStage('failed')
          setErrorMsg('Analysis timed out. Check History for results.')
          return
        }
        const status = await apiClient.getCallStatus(upload.call_id)
        if (!status) return
        if (status.status === 'processing') setStage('processing')
        if (status.status === 'completed') { clearInterval(poll); setStage('completed') }
        if (status.status === 'failed') {
          clearInterval(poll)
          setStage('failed')
          setErrorMsg(status.error || 'Analysis failed')
        }
      }, 1500)

    } catch (e) {
      clearInterval(progInterval)
      setStage('failed')
      setErrorMsg(e instanceof Error ? e.message : 'Unknown error')
    }
  }

  function resetAll() {
    setFile(null)
    setFileError(null)
    setStage('idle')
    setCallId(null)
    setErrorMsg('')
    setElapsedSeconds(0)
    setUploadProgress(0)
    if (inputRef.current) inputRef.current.value = ''
  }

  const activeStep = getActiveStep(stage)
  const isAnalyzing = ['uploading', 'queued', 'processing'].includes(stage)
  const isCompleted = stage === 'completed'
  const isFailed = stage === 'failed'

  return (
    <div className="page-content">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="page-heading">
        <div className="page-heading__icon-wrap" aria-hidden="true">
          <MicVocalIcon size={20} strokeWidth={1.75} />
        </div>
        <div>
          <h1 className="page-heading__title">Analyse a Call</h1>
          <p className="page-heading__subtitle">
            Upload a recording to detect social engineering, voice spoofing, and fraud patterns.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '1.5rem', alignItems: 'start' }}>

        {/* ── Main Panel ─────────────────────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

          {/* Drop Zone */}
          <div
            className={`analyse-dropzone${dragOver ? ' analyse-dropzone--active' : ''}${file && !fileError ? ' analyse-dropzone--has-file' : ''}${fileError ? ' analyse-dropzone--error' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => !isAnalyzing && inputRef.current?.click()}
            role="button"
            tabIndex={0}
            aria-label="Upload audio file"
            onKeyDown={e => e.key === 'Enter' && !isAnalyzing && inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".wav,.mp3,.m4a,.ogg,.flac,audio/*"
              style={{ display: 'none' }}
              onChange={onInputChange}
              id="audio-file-input"
            />

            {!file ? (
              <div className="analyse-dropzone__empty">
                <div className="analyse-dropzone__icon-ring">
                  <UploadCloudIcon size={32} strokeWidth={1.5} />
                </div>
                <p className="analyse-dropzone__title">Drop audio file here</p>
                <p className="analyse-dropzone__hint">or click to browse</p>
                <div className="analyse-dropzone__formats">
                  {ACCEPTED_TYPES.map(t => (
                    <span key={t} className="analyse-format-badge">{t.toUpperCase().slice(1)}</span>
                  ))}
                </div>
                <p className="analyse-dropzone__limit">Max {MAX_SIZE_MB}MB</p>
              </div>
            ) : (
              <div className="analyse-dropzone__file">
                <div className={`analyse-file-icon ${fileError ? 'analyse-file-icon--error' : ''}`}>
                  <FileAudioIcon size={28} strokeWidth={1.5} />
                </div>
                <div className="analyse-file-info">
                  <p className="analyse-file-name">{file.name}</p>
                  <p className="analyse-file-meta">
                    {formatBytes(file.size)} · {file.name.split('.').pop()?.toUpperCase()}
                  </p>
                  {fileError && (
                    <p className="analyse-file-error">
                      <AlertCircleIcon size={13} style={{ display: 'inline', marginRight: 4 }} />
                      {fileError}
                    </p>
                  )}
                </div>
                {!isAnalyzing && (
                  <button
                    className="analyse-file-remove"
                    onClick={e => { e.stopPropagation(); resetAll() }}
                    aria-label="Remove file"
                  >
                    <XIcon size={14} />
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Upload progress bar */}
          {stage === 'uploading' && (
            <div className="analyse-progress-wrap">
              <div className="analyse-progress-bar" style={{ width: `${uploadProgress}%` }} />
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            {!isCompleted && !isFailed && (
              <button
                className="btn-primary"
                style={{ flex: 1, justifyContent: 'center', display: 'flex', alignItems: 'center', gap: 8 }}
                disabled={!file || !!fileError || isAnalyzing}
                onClick={startAnalysis}
              >
                {isAnalyzing ? (
                  <>
                    <RefreshCwIcon size={16} className="analysis-status__spinner" />
                    Analysing... ({elapsedSeconds}s)
                  </>
                ) : (
                  <>
                    <ZapIcon size={16} />
                    Start Analysis
                  </>
                )}
              </button>
            )}

            {isCompleted && (
              <>
                <button
                  className="btn-primary"
                  style={{ flex: 1, justifyContent: 'center', display: 'flex', alignItems: 'center', gap: 8 }}
                  onClick={() => callId && onViewReport?.(callId)}
                >
                  <ArrowRightIcon size={16} />
                  View Report
                </button>
                <button className="btn-ghost btn-ghost--sm" onClick={resetAll}>
                  Analyse Another
                </button>
              </>
            )}

            {isFailed && (
              <button
                className="btn-ghost btn-ghost--sm"
                style={{ flex: 1, justifyContent: 'center', display: 'flex', alignItems: 'center', gap: 8 }}
                onClick={resetAll}
              >
                <RefreshCwIcon size={14} />
                Try Again
              </button>
            )}
          </div>

          {/* Error banner */}
          {isFailed && (
            <div className="analysis-status analysis-status--error" role="alert">
              <AlertCircleIcon size={16} className="analysis-status__icon" />
              <div className="analysis-status__text">
                <strong>Analysis failed:</strong>
                <span> {errorMsg}</span>
              </div>
            </div>
          )}
        </div>

        {/* ── Right Panel: Pipeline ──────────────────────────────── */}
        <div className="analyse-pipeline-card">
          <div className="analyse-pipeline-header">
            <ShieldIcon size={15} />
            <span>Analysis Pipeline</span>
            {analysisMode && (
              <span className={`analyse-mode-badge analyse-mode-badge--${analysisMode}`}>
                {analysisMode.toUpperCase()}
              </span>
            )}
          </div>

          <div className="analyse-pipeline-steps">
            {PIPELINE_STEPS.map((step, idx) => {
              const isDone = isCompleted ? true : idx < activeStep
              const isActive = idx === activeStep && isAnalyzing
              const isFuture = idx > activeStep || (!isAnalyzing && !isCompleted)
              const Icon = step.icon

              return (
                <div
                  key={step.id}
                  className={`analyse-step ${isActive ? 'analyse-step--active' : ''} ${isDone && !isActive ? 'analyse-step--done' : ''} ${isFuture && !isCompleted ? 'analyse-step--future' : ''}`}
                >
                  <div className="analyse-step__connector" />
                  <div className="analyse-step__dot">
                    {isDone && !isActive
                      ? <CheckCircle2Icon size={14} />
                      : <Icon size={14} className={isActive ? 'analysis-status__spinner' : ''} />
                    }
                  </div>
                  <div className="analyse-step__text">
                    <span className="analyse-step__label">{step.label}</span>
                    <span className="analyse-step__desc">{step.desc}</span>
                  </div>
                </div>
              )
            })}
          </div>

          {isCompleted && (
            <div className="analyse-pipeline-success">
              <CheckCircle2Icon size={14} />
              <span>Report ready in {elapsedSeconds}s</span>
            </div>
          )}
        </div>
      </div>

      {/* ── Info footer ──────────────────────────────────────────── */}
      <aside className="info-card" aria-label="Privacy note">
        <p className="info-card__text">
          <strong>Privacy-first:</strong> Your recording is processed locally and never stored in the cloud.
          Only the voice embedding is retained for enrolled contacts — raw audio is immediately deleted.
        </p>
      </aside>
    </div>
  )
}
