import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Activity, AlertTriangle, CheckCircle2, Mic, PhoneCall,
  PhoneOff, Shield, Sparkles,
  Radio, Send, Lock, Volume2, Info
} from 'lucide-react'
import { apiClient, type LiveTranscriptSegment } from '../services/api'

interface LiveAnalysisPageProps {
  onViewReport?: (callId: string) => void
}

type SessionMode = 'webrtc' | 'cellular' | 'non_audio'

interface WSMessage {
  type: string
  session_id?: string
  data?: any
  message?: string
  segment?: LiveTranscriptSegment
}

export function LiveAnalysisPage({ onViewReport }: LiveAnalysisPageProps) {

  // Form / Setup State
  const [mode, setMode] = useState<SessionMode>('non_audio')
  const [audioAuthorized, setAudioAuthorized] = useState(false)
  const [callerNumber, setCallerNumber] = useState('')
  const [claimedIdentity, setClaimedIdentity] = useState('')
  const [claimedRelationship, setClaimedRelationship] = useState('unknown')

  // Live Session State
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isActive, setIsActive] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'connecting' | 'connected' | 'disconnected'>('idle')
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  // Real-Time Analytics State
  const [currentScore, setCurrentScore] = useState(0)
  const [currentLevel, setCurrentLevel] = useState('LOW')
  const [categoryScores, setCategoryScores] = useState<Record<string, number>>({})
  const [firedRules, setFiredRules] = useState<string[]>([])
  const [reasons, setReasons] = useState<string[]>([])
  const [recommendedActions, setRecommendedActions] = useState<string[]>([])
  const [warnings, setWarnings] = useState<string[]>([])
  const [voiceStatus, setVoiceStatus] = useState('unavailable')
  const [voiceSpoofProb, setVoiceSpoofProb] = useState<number | null>(null)
  const [windowsAnalyzed, setWindowsAnalyzed] = useState(0)

  // Phase 5A: Transcript quality / assessment status
  const [assessmentStatus, setAssessmentStatus] = useState<string | null>(null)
  const [transcriptQuality, setTranscriptQuality] = useState<Record<string, any> | null>(null)

  // Transcript state
  const [segments, setSegments] = useState<LiveTranscriptSegment[]>([])
  const [provisionalText, setProvisionalText] = useState<string | null>(null)

  // Non-audio manual message input
  const [manualText, setManualText] = useState('')
  const [isSubmittingMessage, setIsSubmittingMessage] = useState(false)

  // WebSocket & Audio references
  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null)
  const audioChunkSeqRef = useRef<number>(0)
  const transcriptEndRef = useRef<HTMLDivElement | null>(null)

  // Auto scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [segments, provisionalText])

  // Timer
  useEffect(() => {
    if (isActive) {
      timerRef.current = setInterval(() => setElapsedSeconds(s => s + 1), 1000)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [isActive])

  // Quick preset suspicious statements
  const QUICK_REPORTS = [
    { label: 'Demand OTP/PIN', text: 'Please read me the 6-digit one-time password sent to your mobile.' },
    { label: 'Digital Arrest Threat', text: 'This is the cyber crime department. You are under digital arrest. Stay on this call.' },
    { label: 'Install Remote App', text: 'Kindly download QuickSupport or AnyDesk from the Play Store to verify your account.' },
    { label: 'Immediate Account Block', text: 'Your bank account and debit card are suspended due to unverified KYC.' },
    { label: 'Secret Wire Transfer', text: 'Transfer funds immediately to our RBI safety escrow account for verification.' },
  ]

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopAudioCapture()
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  // Start Session
  async function handleStartSession() {
    setConnectionStatus('connecting')
    try {
      const res = await apiClient.startLiveSession({
        mode,
        audio_authorized: audioAuthorized,
        caller_number: callerNumber.trim() || undefined,
        claimed_identity: claimedIdentity.trim() || undefined,
        claimed_relationship: claimedRelationship,
      })

      if (!res) {
        alert('Failed to initialize live session. Check backend connection.')
        setConnectionStatus('idle')
        return
      }

      setSessionId(res.session_id)
      setIsActive(true)
      setElapsedSeconds(0)
      setSegments([])
      setProvisionalText(null)
      setCurrentScore(0)
      setCurrentLevel('LOW')
      setFiredRules([])
      setReasons([])
      setWarnings([])
      setVoiceStatus(res.audio_authorized ? 'pending' : 'not_authorized')

      // Connect WebSocket
      connectWebSocket(res.session_id)

      // Start WebRTC audio capture if mode requires audio and authorized
      if (mode === 'webrtc' && audioAuthorized) {
        await startAudioCapture(res.session_id)
      }
    } catch (err) {
      console.error('Error starting live session:', err)
      setConnectionStatus('idle')
    }
  }

  // Connect WebSocket
  const connectWebSocket = useCallback((sid: string) => {
    const wsUrl = apiClient.getLiveWebSocketUrl(sid)
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionStatus('connected')
    }

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)

        if (msg.type === 'auth_ok') {
          // Session confirmed
        } else if (msg.type === 'transcript_partial') {
          if (msg.segment) {
            setProvisionalText(msg.segment.text)
          } else if (msg.data?.segment) {
            setProvisionalText(msg.data.segment.text)
          }
        } else if (msg.type === 'transcript_final') {
          setProvisionalText(null)
          const seg: LiveTranscriptSegment = msg.segment || msg.data?.segment
          if (seg) {
            setSegments(prev => [...prev, seg])
          }
        } else if (msg.type === 'risk_update') {
          const d = msg.data || {}
          setCurrentScore(d.score ?? 0)
          setCurrentLevel(d.level ?? 'LOW')
          if (d.category_scores) setCategoryScores(d.category_scores)
          if (d.fired_rules) setFiredRules(d.fired_rules)
          if (d.reasons) setReasons(d.reasons)
          if (d.recommended_actions) setRecommendedActions(d.recommended_actions)
          if (d.voice_status) setVoiceStatus(d.voice_status)
          if (d.voice_spoof_prob !== undefined) setVoiceSpoofProb(d.voice_spoof_prob)
          // Phase 5A: assessment quality signals
          if (d.assessment_status) setAssessmentStatus(d.assessment_status)
          if (d.transcript_quality) setTranscriptQuality(d.transcript_quality)
        } else if (msg.type === 'voice_update') {
          const d = msg.data || {}
          setVoiceStatus(d.status || 'analyzed')
          if (d.spoof_prob !== undefined) setVoiceSpoofProb(d.spoof_prob)
          if (d.windows_analyzed) setWindowsAnalyzed(d.windows_analyzed)
        } else if (msg.type === 'warning') {
          const text = msg.message || msg.data?.message || 'Warning received'
          setWarnings(prev => Array.from(new Set([...prev, text])))
        }
      } catch (e) {
        console.error('WS parse error:', e)
      }
    }

    ws.onerror = (e) => {
      console.error('WS Error:', e)
    }

    ws.onclose = () => {
      setConnectionStatus('disconnected')
    }
  }, [])

  // WebRTC Audio Streaming (PCM 16-bit 16kHz Mono)
  async function startAudioCapture(_sid: string) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } })
      mediaStreamRef.current = stream

      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 })
      audioContextRef.current = audioCtx

      const source = audioCtx.createMediaStreamSource(stream)
      // Buffer size 4096 = ~256ms chunk at 16kHz
      const processor = audioCtx.createScriptProcessor(4096, 1, 1)
      scriptProcessorRef.current = processor

      processor.onaudioprocess = (e) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return

        const inputData = e.inputBuffer.getChannelData(0)
        // Convert Float32 to 16-bit PCM
        const pcm16 = new Int16Array(inputData.length)
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]))
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
        }

        // Pack 16-byte binary header:
        // uint32 sequence_number (4)
        // uint64 timestamp_ms (8)
        // uint16 sample_rate (2)
        // uint8  channel_count (1)
        // uint8  encoding (1)
        audioChunkSeqRef.current++
        const seq = audioChunkSeqRef.current
        const nowMs = BigInt(Date.now())

        const headerBuffer = new ArrayBuffer(16)
        const view = new DataView(headerBuffer)
        view.setUint32(0, seq, true)
        view.setBigUint64(4, nowMs, true)
        view.setUint16(12, 16000, true)
        view.setUint8(14, 1)
        view.setUint8(15, 0) // PCM_16BIT

        // Combine header + audio
        const combined = new Uint8Array(16 + pcm16.byteLength)
        combined.set(new Uint8Array(headerBuffer), 0)
        combined.set(new Uint8Array(pcm16.buffer), 16)

        wsRef.current.send(combined.buffer)
      }

      source.connect(processor)
      processor.connect(audioCtx.destination)
    } catch (err) {
      console.error('Microphone capture error:', err)
      alert('Could not access microphone for live audio streaming. Running in non-audio companion mode.')
    }
  }

  function stopAudioCapture() {
    if (scriptProcessorRef.current) {
      scriptProcessorRef.current.disconnect()
      scriptProcessorRef.current = null
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {})
      audioContextRef.current = null
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(t => t.stop())
      mediaStreamRef.current = null
    }
  }

  // Submit manual / non-audio message
  async function handleSubmitMessage(textToSend?: string) {
    const text = textToSend || manualText
    if (!text.trim() || !sessionId) return

    setIsSubmittingMessage(true)
    try {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'submit_message',
          text: text.trim(),
          speaker: 'caller',
          timestamp_s: elapsedSeconds,
        }))
      } else {
        await apiClient.submitLiveMessage(sessionId, {
          text: text.trim(),
          speaker: 'caller',
          timestamp_s: elapsedSeconds,
        })
      }
      setManualText('')
    } catch (e) {
      console.error('Error submitting message:', e)
    } finally {
      setIsSubmittingMessage(false)
    }
  }

  // Stop Session (persists to DB)
  async function handleStopSession() {
    if (!sessionId) return
    stopAudioCapture()
    if (wsRef.current) {
      try {
        wsRef.current.send(JSON.stringify({ type: 'stop' }))
      } catch {}
      wsRef.current.close()
    }

    try {
      const res = await apiClient.stopLiveSession(sessionId)
      setIsActive(false)
      if (res && onViewReport) {
        onViewReport(res.call_id)
      } else {
        alert('Live session concluded and saved to database.')
      }
    } catch (e) {
      console.error('Error stopping session:', e)
      setIsActive(false)
    }
  }

  // Cancel Session (discards)
  async function handleCancelSession() {
    if (!sessionId) return
    stopAudioCapture()
    if (wsRef.current) {
      try {
        wsRef.current.send(JSON.stringify({ type: 'cancel' }))
      } catch {}
      wsRef.current.close()
    }
    await apiClient.cancelLiveSession(sessionId)
    setIsActive(false)
    setSessionId(null)
  }

  // Score color helper
  function getScoreColor(score: number): string {
    if (score >= 75) return 'text-red-500'
    if (score >= 50) return 'text-orange-500'
    if (score >= 25) return 'text-amber-500'
    return 'text-emerald-500'
  }

  function formatTime(sec: number): string {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-6 border-b border-slate-700/60">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Activity className="w-3.5 h-3.5 mr-1 animate-pulse" />
              Live Telephony & Internet Call Detection
            </span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-100 tracking-tight mt-1">
            Real-Time Fraud Monitor
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Dual-source scam detection with deterministic Trust Judge scoring, live ASR, and anti-spoof evaluation.
          </p>
        </div>

        {isActive && (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping" />
              <span className="font-mono text-sm font-semibold text-slate-200">{formatTime(elapsedSeconds)}</span>
            </div>
            <button
              onClick={handleStopSession}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-red-600 hover:bg-red-700 text-white transition-colors shadow-sm"
            >
              <PhoneOff className="w-4 h-4" />
              Conclude Call & View Report
            </button>
            <button
              onClick={handleCancelSession}
              className="px-3 py-2 rounded-lg text-sm font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
            >
              Cancel
            </button>
          </div>
        )}
      </div>

      {/* Main Content */}
      {!isActive ? (
        /* Configuration Setup Panel */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-slate-800/80 rounded-2xl border border-slate-700/60 p-6 backdrop-blur-sm shadow-xl space-y-6">
              <h2 className="text-xl font-semibold text-slate-100 flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-blue-400" />
                Start a New Live Session
              </h2>

              {/* Mode Selection */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Session Mode
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <button
                    type="button"
                    onClick={() => setMode('non_audio')}
                    className={`p-4 rounded-xl border text-left transition-all ${
                      mode === 'non_audio'
                        ? 'bg-blue-600/10 border-blue-500 text-slate-100 shadow-md ring-1 ring-blue-500/50'
                        : 'bg-slate-900/50 border-slate-700 hover:border-slate-600 text-slate-400'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-slate-200">Non-Audio Companion</span>
                      <Shield className="w-4 h-4 text-blue-400" />
                    </div>
                    <p className="text-xs text-slate-400">
                      Standard cellular call mode. Report claims or suspicious demands in real time with instant Trust Judge scoring.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setMode('webrtc')
                      setAudioAuthorized(true)
                    }}
                    className={`p-4 rounded-xl border text-left transition-all ${
                      mode === 'webrtc'
                        ? 'bg-blue-600/10 border-blue-500 text-slate-100 shadow-md ring-1 ring-blue-500/50'
                        : 'bg-slate-900/50 border-slate-700 hover:border-slate-600 text-slate-400'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-slate-200">WebRTC Internet Call</span>
                      <Mic className="w-4 h-4 text-emerald-400" />
                    </div>
                    <p className="text-xs text-slate-400">
                      Live microphone audio streaming prototype with incremental ASR and AASIST voice clone anti-spoof analysis.
                    </p>
                  </button>
                </div>
              </div>

              {/* Consent Toggle */}
              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-700/80 space-y-3">
                <div className="flex items-start justify-between">
                  <div className="space-y-0.5">
                    <span className="text-sm font-medium text-slate-200 flex items-center gap-1.5">
                      <Lock className="w-4 h-4 text-blue-400" />
                      Caller Audio Consent Authorization
                    </span>
                    <p className="text-xs text-slate-400">
                      Explicit authorization for synthetic speech and voice clone detection in accordance with privacy laws.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={audioAuthorized}
                    onChange={(e) => setAudioAuthorized(e.target.checked)}
                    className="w-5 h-5 rounded text-blue-600 bg-slate-800 border-slate-600 focus:ring-blue-500 focus:ring-offset-slate-900 cursor-pointer"
                  />
                </div>
                {!audioAuthorized && mode === 'webrtc' && (
                  <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 px-3 py-2 rounded-lg">
                    <Info className="w-4 h-4 shrink-0" />
                    Caller audio consent not authorized. Voice-clone analysis will be disabled and non-audio detection will run.
                  </div>
                )}
              </div>

              {/* Call Metadata */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Caller Phone Number
                  </label>
                  <input
                    type="text"
                    value={callerNumber}
                    onChange={(e) => setCallerNumber(e.target.value)}
                    placeholder="+91 98765 43210"
                    className="w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Claimed Identity / Organization
                  </label>
                  <input
                    type="text"
                    value={claimedIdentity}
                    onChange={(e) => setClaimedIdentity(e.target.value)}
                    placeholder="e.g. State Bank Officer, Police"
                    className="w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Claimed Relationship
                  </label>
                  <select
                    value={claimedRelationship}
                    onChange={(e) => setClaimedRelationship(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700 text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="unknown">Unknown Caller</option>
                    <option value="bank">Bank / Financial Institution</option>
                    <option value="government">Government / Police / Customs</option>
                    <option value="telecom">Telecom / Courier Service</option>
                    <option value="relative">Relative / Family Member</option>
                  </select>
                </div>
              </div>

              {/* Action */}
              <button
                onClick={handleStartSession}
                disabled={connectionStatus === 'connecting'}
                className="w-full py-3.5 rounded-xl font-semibold text-white bg-blue-600 hover:bg-blue-700 shadow-lg shadow-blue-600/20 transition-all flex items-center justify-center gap-2"
              >
                <PhoneCall className="w-5 h-5" />
                {connectionStatus === 'connecting' ? 'Initializing Live Channel...' : 'Start Live Detection Session'}
              </button>
            </div>
          </div>

          {/* Right Info Box */}
          <div className="space-y-6">
            <div className="bg-slate-800/80 rounded-2xl border border-slate-700/60 p-6 backdrop-blur-sm shadow-xl space-y-4">
              <h3 className="text-base font-semibold text-slate-200 flex items-center gap-2">
                <Shield className="w-4 h-4 text-emerald-400" />
                VISHWAS Protection Pipeline
              </h3>
              <ul className="text-xs text-slate-400 space-y-3">
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                  <span><strong>Agents propose. Rules decide.</strong> LLMs extract parameters; authoritative scoring stays strictly deterministic.</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                  <span><strong>Hard Floor Safeguards:</strong> Demanding OTP/PIN immediately elevates score to at least 75 (CRITICAL).</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                  <span><strong>Cellular Feasibility:</strong> Respects Android audio capture constraints and falls back safely to companion reporting without false claims.</span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                  <span><strong>Privacy Preservation:</strong> PII is masked before any LLM evaluation; raw audio is never permanently stored.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      ) : (
        /* Active Live Monitoring Dashboard */
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column: Live Gauges & Voice Status */}
          <div className="space-y-6">
            {/* Risk Gauge Card */}
            <div className="bg-slate-800/80 rounded-2xl border border-slate-700/60 p-6 backdrop-blur-sm shadow-xl space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Trust Judge Assessment
                </span>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                  currentLevel === 'CRITICAL' ? 'bg-red-500/10 text-red-400 border-red-500/30' :
                  currentLevel === 'HIGH' ? 'bg-orange-500/10 text-orange-400 border-orange-500/30' :
                  currentLevel === 'MEDIUM' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' :
                  'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                }`}>
                  {currentLevel} RISK
                </span>
              </div>

              {/* Big Score Display */}
              <div className="flex items-baseline justify-center py-4">
                <span className={`text-6xl font-black tracking-tight ${getScoreColor(currentScore)}`}>
                  {currentScore}
                </span>
                <span className="text-slate-500 text-xl font-medium ml-1">/100</span>
              </div>

              {/* Category Breakdown Bars */}
              <div className="space-y-2 pt-2 border-t border-slate-700/60 text-xs">
                {['identity', 'sensitive_request', 'behavior', 'channel', 'voice'].map((cat) => {
                  const val = categoryScores[cat] || 0
                  const maxCap = cat === 'sensitive_request' ? 30 : cat === 'identity' ? 25 : cat === 'behavior' ? 20 : cat === 'channel' ? 15 : 10
                  const pct = Math.min(100, Math.round((val / maxCap) * 100))
                  return (
                    <div key={cat} className="space-y-1">
                      <div className="flex justify-between text-slate-300">
                        <span className="capitalize">{cat.replace('_', ' ')}</span>
                        <span>{val} / {maxCap}</span>
                      </div>
                      <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Phase 5A: Transcript Quality Banner */}
            {assessmentStatus && assessmentStatus !== 'complete' && (
              <div className={`rounded-xl border px-4 py-3 text-xs flex items-start gap-3 ${
                assessmentStatus === 'unavailable' ? 'bg-slate-900/60 border-slate-600/50 text-slate-400' :
                assessmentStatus === 'degraded' ? 'bg-amber-950/40 border-amber-600/40 text-amber-300' :
                'bg-blue-950/30 border-blue-700/30 text-blue-300'
              }`}>
                <Info className={`w-4 h-4 mt-0.5 shrink-0 ${
                  assessmentStatus === 'degraded' ? 'text-amber-400' :
                  assessmentStatus === 'unavailable' ? 'text-slate-500' : 'text-blue-400'
                }`} />
                <div className="space-y-1">
                  <div className="font-semibold capitalize">
                    Assessment: {assessmentStatus}
                  </div>
                  {transcriptQuality?.reason && (
                    <div className="opacity-80">{transcriptQuality.reason}</div>
                  )}
                  {transcriptQuality?.revision_count != null && transcriptQuality.revision_count > 0 && (
                    <div className="opacity-60">Revisions: {transcriptQuality.revision_count}</div>
                  )}
                  <div className="opacity-60 mt-0.5">
                    {assessmentStatus === 'degraded'
                      ? 'Evidence reliability limited — verify independently before acting.'
                      : assessmentStatus === 'provisional'
                      ? 'Transcript still stabilising — findings are preliminary.'
                      : 'Transcript unavailable — no evidence can be extracted.'}
                  </div>
                </div>
              </div>
            )}

            {/* Voice Anti-Spoof Status */}
            <div className="bg-slate-800/80 rounded-2xl border border-slate-700/60 p-6 backdrop-blur-sm shadow-xl space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Volume2 className="w-4 h-4 text-blue-400" />
                  Voice-Clone Analysis
                </span>
                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                  voiceStatus === 'analyzed' ? 'bg-emerald-500/10 text-emerald-400' :
                  voiceStatus === 'pending' ? 'bg-blue-500/10 text-blue-400 animate-pulse' :
                  'bg-slate-700/50 text-slate-400'
                }`}>
                  {voiceStatus}
                </span>
              </div>

              {voiceStatus === 'not_authorized' ? (
                <p className="text-xs text-slate-400">
                  Caller audio consent is not authorized for this session. Anti-spoofing is disabled per privacy rules.
                </p>
              ) : voiceStatus === 'unavailable' ? (
                <p className="text-xs text-slate-400">
                  Voice anti-spoof model is unavailable or in non-audio companion mode.
                </p>
              ) : (
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-xs text-slate-300 mb-1">
                      <span>Calibrated Spoof Probability</span>
                      <span className="font-mono font-semibold">
                        {voiceSpoofProb !== null ? `${(voiceSpoofProb * 100).toFixed(1)}%` : 'Measuring...'}
                      </span>
                    </div>
                    <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden">
                      <div
                        className={`h-2 rounded-full transition-all duration-500 ${
                          (voiceSpoofProb ?? 0) >= 0.80 ? 'bg-red-500' :
                          (voiceSpoofProb ?? 0) >= 0.60 ? 'bg-amber-500' : 'bg-emerald-500'
                        }`}
                        style={{ width: `${Math.min(100, Math.round((voiceSpoofProb ?? 0) * 100))}%` }}
                      />
                    </div>
                  </div>
                  <div className="flex justify-between text-[11px] text-slate-400">
                    <span>Windows Evaluated: {windowsAnalyzed}</span>
                    <span>Model: AASIST-L Calibrated</span>
                  </div>
                </div>
              )}
            </div>

            {/* Warnings & Recommendations */}
            {(warnings.length > 0 || recommendedActions.length > 0) && (
              <div className="bg-slate-800/80 rounded-2xl border border-red-500/30 p-5 space-y-3 bg-red-950/20">
                <div className="flex items-center gap-2 text-red-400 font-semibold text-xs uppercase tracking-wider">
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                  Urgent Warnings & Guidance
                </div>
                {warnings.map((w, idx) => (
                  <div key={idx} className="text-xs text-red-300 font-medium bg-red-900/30 p-2.5 rounded-lg border border-red-800/50">
                    {w}
                  </div>
                ))}
                {recommendedActions.map((act, idx) => (
                  <div key={idx} className="text-xs text-slate-300 flex items-start gap-1.5">
                    <span className="text-amber-400 font-bold">•</span>
                    <span>{act}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right Column: Live Transcript & Non-Audio Fast Reporter */}
          <div className="lg:col-span-2 space-y-6">
            {/* Live Streaming Transcript Card */}
            <div className="bg-slate-800/80 rounded-2xl border border-slate-700/60 p-6 backdrop-blur-sm shadow-xl flex flex-col h-[420px]">
              <div className="flex items-center justify-between pb-3 border-b border-slate-700/60 mb-3">
                <div className="flex items-center gap-2">
                  <Radio className="w-4 h-4 text-emerald-400 animate-pulse" />
                  <span className="text-sm font-semibold text-slate-200">
                    Live Call Stream & Transcript
                  </span>
                </div>
                <span className="text-xs text-slate-400 font-mono">
                  {segments.length} segment(s)
                </span>
              </div>

              {/* Scrollable transcript area */}
              <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-thin scrollbar-thumb-slate-700">
                {segments.length === 0 && !provisionalText && (
                  <div className="h-full flex flex-col items-center justify-center text-slate-500 text-sm italic">
                    <Activity className="w-8 h-8 mb-2 opacity-40 animate-pulse" />
                    Listening for incoming call statements...
                  </div>
                )}

                {segments.map((seg, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-slate-900/60 border border-slate-700/60 text-slate-200 text-sm space-y-1"
                  >
                    <div className="flex items-center justify-between text-xs text-slate-400">
                      <span className="font-semibold text-blue-400 capitalize">
                        {seg.speaker}
                      </span>
                      <span>{seg.start.toFixed(1)}s - {seg.end.toFixed(1)}s</span>
                    </div>
                    <p className="leading-relaxed">{seg.text}</p>
                  </div>
                ))}

                {/* Provisional Interim Segment */}
                {provisionalText && (
                  <div className="p-3 rounded-xl bg-blue-950/30 border border-blue-500/40 text-blue-200 text-sm space-y-1 animate-pulse">
                    <div className="flex items-center justify-between text-xs text-blue-400">
                      <span className="font-semibold flex items-center gap-1">
                        <Activity className="w-3 h-3 animate-spin" />
                        Transcribing (Provisional)...
                      </span>
                    </div>
                    <p className="italic leading-relaxed">{provisionalText}</p>
                  </div>
                )}
                <div ref={transcriptEndRef} />
              </div>
            </div>

            {/* Non-Audio Fast Reporter / Companion Input */}
            <div className="bg-slate-800/80 rounded-2xl border border-slate-700/60 p-6 backdrop-blur-sm shadow-xl space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                  <Send className="w-4 h-4 text-blue-400" />
                  Companion Report: Submit Caller Statement
                </span>
                <span className="text-xs text-slate-400">Updates Trust Judge immediately</span>
              </div>

              {/* Quick Preset Buttons */}
              <div className="flex flex-wrap gap-2">
                {QUICK_REPORTS.map((qr, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSubmitMessage(qr.text)}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-900 hover:bg-slate-700 text-slate-300 border border-slate-700/80 hover:border-blue-500/50 transition-colors"
                  >
                    {qr.label}
                  </button>
                ))}
              </div>

              {/* Custom input */}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={manualText}
                  onChange={(e) => setManualText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      handleSubmitMessage()
                    }
                  }}
                  placeholder="Type or paste what the caller is saying right now..."
                  className="flex-1 px-4 py-2.5 rounded-xl bg-slate-900/70 border border-slate-700 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  type="button"
                  onClick={() => handleSubmitMessage()}
                  disabled={isSubmittingMessage || !manualText.trim()}
                  className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium text-sm transition-colors flex items-center gap-1.5 shadow-sm"
                >
                  <Send className="w-4 h-4" />
                  Report
                </button>
              </div>
            </div>

            {/* Fired Rules & Reasons summary */}
            {firedRules.length > 0 && (
              <div className="bg-slate-800/80 rounded-2xl border border-slate-700/60 p-5 space-y-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Fired Deterministic Rules ({firedRules.length})
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {firedRules.map((r, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 rounded text-xs font-mono font-medium bg-slate-900 border border-slate-700 text-amber-300"
                    >
                      {r}
                    </span>
                  ))}
                </div>
                {reasons.length > 0 && (
                  <div className="pt-2 border-t border-slate-700/60 space-y-1">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase">Detection Rationale:</span>
                    {reasons.map((rsn, idx) => (
                      <p key={idx} className="text-xs text-slate-300">• {rsn}</p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
