import { useState, useRef, useEffect } from 'react'
import {
  MicVocalIcon,
  MicIcon,
  MicOffIcon,
  AlertCircleIcon,
  CheckCircle2Icon,
  RefreshCwIcon,
  ActivityIcon,
} from 'lucide-react'
import { apiClient } from '../services/api'

type Status = 'idle' | 'requesting-mic' | 'listening' | 'analyzing' | 'error'

const CHUNK_SIZE_BYTES = 48000 // Backend expects 48000 bytes (~1.5s at 16kHz mono int16)
const SAMPLE_RATE = 16000
const CHANNELS = 1

export function VoiceDetectionPage() {
  const [recording, setRecording] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [spoofProb, setSpoofProb] = useState<number | null>(null)
  const [confidence, setConfidence] = useState<string>('')
  const [chunksProcessed, setChunksProcessed] = useState(0)
  const [errorMsg, setErrorMsg] = useState('')
  const [waveformData, setWaveformData] = useState<Float32Array>(new Float32Array(SAMPLE_RATE))

  const audioContextRef = useRef<AudioContext | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const bufferRef = useRef<Uint8Array>(new Uint8Array(CHUNK_SIZE_BYTES * 2)) // Double size for buffering
  const bufferPositionRef = useRef(0)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationFrameRef = useRef<number | null>(null)

  // Convert Float32 PCM to Int16
  function float32ToInt16(float32Array: Float32Array): Int16Array {
    const int16Array = new Int16Array(float32Array.length)
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]))
      int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7fff
    }
    return int16Array
  }

  // Draw waveform on canvas
  function drawWaveform() {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const width = canvas.width
    const height = canvas.height
    const data = waveformData

    // Clear canvas
    ctx.fillStyle = 'rgb(15, 23, 42)' // slate-900 background
    ctx.fillRect(0, 0, width, height)

    // Draw waveform
    ctx.strokeStyle = recording ? 'rgb(59, 130, 246)' : 'rgb(71, 85, 105)' // blue-500 or slate-600
    ctx.lineWidth = 1.5
    ctx.beginPath()

    const sliceWidth = width / data.length
    let x = 0

    for (let i = 0; i < data.length; i++) {
      const v = data[i]
      const y = (v * height / 2) + (height / 2)

      if (i === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }

      x += sliceWidth
    }

    ctx.stroke()
  }

  // Animation loop for waveform
  useEffect(() => {
    function animate() {
      drawWaveform()
      animationFrameRef.current = requestAnimationFrame(animate)
    }

    animate()

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [waveformData, recording])

  // Audio processing callback
  async function processAudio(audioData: Float32Array) {
    // Update waveform data for visualization
    setWaveformData(new Float32Array(audioData))

    // Convert to Int16 and buffer
    const int16Data = float32ToInt16(audioData)
    const bytes = new Uint8Array(int16Data.buffer)

    // Add to buffer
    const buffer = bufferRef.current
    let position = bufferPositionRef.current

    for (let i = 0; i < bytes.length; i++) {
      buffer[position++] = bytes[i]

      // When buffer reaches chunk size, send it
      if (position >= CHUNK_SIZE_BYTES) {
        const chunk = buffer.slice(0, CHUNK_SIZE_BYTES)
        bufferPositionRef.current = 0
        position = 0

        // Send chunk to backend
        if (sessionId) {
          try {
            const blob = new Blob([chunk], { type: 'application/octet-stream' })
            const response = await apiClient.sendVoiceChunk(sessionId, blob)

            if (response) {
              setSpoofProb(response.spoof_prob)
              setConfidence(response.confidence)
              setChunksProcessed(response.chunks_processed)

              if (response.label !== 'insufficient_data') {
                setStatus('analyzing')
              }
            } else {
              setStatus('error')
              setErrorMsg('Network error - check backend connection')
              stopRecording()
            }
          } catch (error) {
            console.error('Error sending chunk:', error)
            setStatus('error')
            setErrorMsg('Failed to send audio chunk')
            stopRecording()
          }
        }
      }
    }

    bufferPositionRef.current = position
  }

  // Start recording
  async function startRecording() {
    try {
      setStatus('requesting-mic')
      setErrorMsg('')
      setSpoofProb(null)
      setConfidence('')
      setChunksProcessed(0)
      bufferPositionRef.current = 0

      // Start streaming session
      const session = await apiClient.startVoiceStream()
      if (!session) {
        setStatus('error')
        setErrorMsg('Failed to start session - backend unavailable')
        return
      }

      setSessionId(session.session_id)

      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: CHANNELS,
          echoCancellation: true,
          noiseSuppression: false,
        },
      })

      mediaStreamRef.current = stream

      // Create audio context
      const audioContext = new AudioContext({ sampleRate: SAMPLE_RATE })
      audioContextRef.current = audioContext

      const source = audioContext.createMediaStreamSource(stream)

      // Create processor node (4096 buffer size)
      const processor = audioContext.createScriptProcessor(4096, CHANNELS, CHANNELS)
      processorRef.current = processor

      processor.onaudioprocess = (e: AudioProcessingEvent) => {
        const inputData = e.inputBuffer.getChannelData(0)
        processAudio(inputData)
      }

      source.connect(processor)
      processor.connect(audioContext.destination)

      setRecording(true)
      setStatus('listening')
    } catch (error) {
      console.error('Error starting recording:', error)
      setStatus('error')
      
      if (error instanceof Error && error.name === 'NotAllowedError') {
        setErrorMsg('Microphone permission denied')
      } else if (error instanceof Error && error.name === 'NotFoundError') {
        setErrorMsg('No microphone found')
      } else {
        setErrorMsg('Failed to access microphone')
      }
    }
  }

  // Stop recording
  async function stopRecording() {
    setRecording(false)
    setStatus('idle')

    // Stop processor
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }

    // Close audio context
    if (audioContextRef.current) {
      await audioContextRef.current.close()
      audioContextRef.current = null
    }

    // Stop media stream
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop())
      mediaStreamRef.current = null
    }

    // Cleanup session
    if (sessionId) {
      try {
        await apiClient.deleteVoiceStream(sessionId)
      } catch (error) {
        console.error('Error deleting session:', error)
      }
      setSessionId(null)
    }

    // Reset waveform
    setWaveformData(new Float32Array(SAMPLE_RATE))
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recording) {
        stopRecording()
      }
    }
  }, [])

  // Get status badge
  function getStatusBadge() {
    if (status === 'error') {
      return (
        <div className="risk-badge badge--high" role="status">
          <AlertCircleIcon size={12} />
          <span>Error</span>
        </div>
      )
    }

    if (status === 'listening') {
      return (
        <div className="risk-badge badge--medium" role="status">
          <ActivityIcon size={12} className="analysis-status__spinner" />
          <span>Listening...</span>
        </div>
      )
    }

    if (status === 'analyzing') {
      return (
        <div className="risk-badge badge--low" role="status">
          <CheckCircle2Icon size={12} />
          <span>Analyzing</span>
        </div>
      )
    }

    return null
  }

  // Get result badge
  function getResultBadge() {
    if (spoofProb === null || confidence === 'insufficient_data') return null

    const isHuman = spoofProb < 0.5
    const highConfidence = confidence === 'high' || confidence === 'medium'

    if (highConfidence) {
      return (
        <div
          className={`analysis-status ${isHuman ? 'analysis-status--success' : 'analysis-status--error'}`}
          role="status"
        >
          {isHuman ? (
            <CheckCircle2Icon size={16} className="analysis-status__icon" />
          ) : (
            <AlertCircleIcon size={16} className="analysis-status__icon" />
          )}
          <div className="analysis-status__text">
            <strong>{isHuman ? 'Human Voice Detected' : 'AI-Generated Voice Detected'}</strong>
          </div>
        </div>
      )
    }

    return null
  }

  // Get spoof probability color
  function getSpoofColor(prob: number): string {
    if (prob < 0.3) return '#10b981' // green
    if (prob < 0.7) return '#f59e0b' // yellow
    return '#ef4444' // red
  }

  return (
    <div className="page-content">
      {/* Header */}
      <div className="page-heading">
        <div className="page-heading__icon-wrap" aria-hidden="true">
          <MicVocalIcon size={20} strokeWidth={1.75} />
        </div>
        <div>
          <h1 className="page-heading__title">Real-Time Voice Detection</h1>
          <p className="page-heading__subtitle">
            Stream live audio from your microphone to detect AI-generated voice spoofing in real-time.
          </p>
        </div>
      </div>

      {/* Main grid layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '1.5rem', maxWidth: '900px' }}>
        
        {/* Control Card */}
        <div className="analyse-pipeline-card" style={{ padding: '2rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            
            {/* Status badge */}
            {getStatusBadge()}

            {/* Waveform visualization */}
            <div>
              <label className="text-sm font-medium text-slate-300 mb-2 block">
                Audio Waveform
              </label>
              <canvas
                ref={canvasRef}
                width={800}
                height={120}
                style={{
                  width: '100%',
                  height: '120px',
                  borderRadius: '8px',
                  border: '1px solid rgb(51, 65, 85)',
                  backgroundColor: 'rgb(15, 23, 42)',
                }}
                aria-label="Audio waveform visualization"
              />
            </div>

            {/* Start/Stop button */}
            <button
              className="btn-primary"
              style={{ justifyContent: 'center', display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}
              disabled={status === 'requesting-mic'}
              onClick={recording ? stopRecording : startRecording}
            >
              {status === 'requesting-mic' ? (
                <>
                  <RefreshCwIcon size={16} className="analysis-status__spinner" />
                  Requesting Microphone...
                </>
              ) : recording ? (
                <>
                  <MicOffIcon size={16} />
                  Stop Listening
                </>
              ) : (
                <>
                  <MicIcon size={16} />
                  Start Listening
                </>
              )}
            </button>

            {/* Error banner */}
            {status === 'error' && errorMsg && (
              <div className="analysis-status analysis-status--error" role="alert">
                <AlertCircleIcon size={16} className="analysis-status__icon" />
                <div className="analysis-status__text">
                  <strong>Error:</strong>
                  <span> {errorMsg}</span>
                </div>
              </div>
            )}

            {/* Empty state */}
            {!recording && status === 'idle' && !errorMsg && (
              <div className="info-card" style={{ marginTop: 0 }}>
                <p className="info-card__text" style={{ textAlign: 'center' }}>
                  Click <strong>Start Listening</strong> to begin live voice analysis.
                  Your audio is processed in real-time and sent to the backend for spoof detection.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Results Card */}
        {(recording || spoofProb !== null) && (
          <div className="analyse-pipeline-card" style={{ padding: '2rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              
              {/* Result badge */}
              {getResultBadge()}

              {/* Spoof Probability Gauge */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <label className="text-sm font-medium text-slate-300">
                    Spoof Probability
                  </label>
                  <span className="text-2xl font-bold" style={{ color: spoofProb !== null ? getSpoofColor(spoofProb) : '#94a3b8' }}>
                    {spoofProb !== null ? `${(spoofProb * 100).toFixed(1)}%` : '—'}
                  </span>
                </div>
                
                {/* Progress bar */}
                <div style={{
                  width: '100%',
                  height: '12px',
                  backgroundColor: 'rgb(30, 41, 59)',
                  borderRadius: '6px',
                  overflow: 'hidden',
                  border: '1px solid rgb(51, 65, 85)',
                }}>
                  <div
                    style={{
                      width: spoofProb !== null ? `${spoofProb * 100}%` : '0%',
                      height: '100%',
                      backgroundColor: spoofProb !== null ? getSpoofColor(spoofProb) : '#94a3b8',
                      transition: 'width 0.3s ease, background-color 0.3s ease',
                    }}
                  />
                </div>
              </div>

              {/* Info grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Confidence Level</label>
                  <p className="text-sm font-medium text-slate-200 capitalize">
                    {confidence || 'Insufficient data'}
                  </p>
                </div>
                <div>
                  <label className="text-xs text-slate-400 block mb-1">Chunks Processed</label>
                  <p className="text-sm font-medium text-slate-200">
                    {chunksProcessed} <span className="text-slate-500">({(chunksProcessed * 1.5).toFixed(1)}s)</span>
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Privacy notice */}
        <aside className="info-card" aria-label="Privacy note">
          <p className="info-card__text">
            <strong>Privacy-first:</strong> Audio is streamed in 1.5-second chunks and processed immediately.
            No recordings are permanently stored. The backend analyzes each chunk and discards it after processing.
          </p>
        </aside>
      </div>
    </div>
  )
}
