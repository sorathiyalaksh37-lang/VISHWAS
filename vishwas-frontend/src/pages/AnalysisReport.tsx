import { useEffect, useRef, useState } from 'react'
import {
  AlertTriangleIcon, ArrowLeftIcon, CheckCircle2Icon,
  ClockIcon, FileAudioIcon, FileTextIcon,
  MicVocalIcon, PhoneOffIcon, ShieldIcon, ShieldOffIcon,
  WavesIcon, ZapIcon, InfoIcon, XCircleIcon,
  BrainCircuitIcon, GitMergeIcon, MessageSquareIcon,
  ActivityIcon, PhoneIcon, ExternalLinkIcon, ChevronDownIcon,
  ChevronUpIcon, BarChart2Icon, AlertOctagonIcon,
} from 'lucide-react'
import { apiClient, type AnalysisReportResponse } from '../services/api'

// ── Helper: animated circular score gauge ─────────────────────────────────────

function ScoreGauge({ score, level }: { score: number; level: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [animated, setAnimated] = useState(0)

  const lvlColor: Record<string, string> = {
    CRITICAL: '#ef4444',
    HIGH: '#f97316',
    MEDIUM: '#f59e0b',
    LOW: '#10b981',
  }
  const color = lvlColor[level.toUpperCase()] ?? '#10b981'

  useEffect(() => {
    let start: number | null = null
    const duration = 1200
    const target = score
    const frame = (ts: number) => {
      if (!start) start = ts
      const progress = Math.min((ts - start) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setAnimated(Math.round(eased * target))
      if (progress < 1) requestAnimationFrame(frame)
    }
    requestAnimationFrame(frame)
  }, [score])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    const W = canvas.width
    const H = canvas.height
    const cx = W / 2
    const cy = H / 2
    const r = Math.min(W, H) / 2 - 10
    const startAngle = -Math.PI * 0.75
    const endAngle = Math.PI * 0.75
    const filledEnd = startAngle + (endAngle - startAngle) * (animated / 100)

    ctx.clearRect(0, 0, W, H)

    // Track
    ctx.beginPath()
    ctx.arc(cx, cy, r, startAngle, endAngle)
    ctx.strokeStyle = 'rgba(255,255,255,0.07)'
    ctx.lineWidth = 12
    ctx.lineCap = 'round'
    ctx.stroke()

    // Fill
    if (animated > 0) {
      const grad = ctx.createLinearGradient(0, H, W, 0)
      grad.addColorStop(0, color + '99')
      grad.addColorStop(1, color)
      ctx.beginPath()
      ctx.arc(cx, cy, r, startAngle, filledEnd)
      ctx.strokeStyle = grad
      ctx.lineWidth = 12
      ctx.lineCap = 'round'
      ctx.stroke()
    }

    // Glow ring at tip
    if (animated > 0) {
      const tipX = cx + r * Math.cos(filledEnd)
      const tipY = cy + r * Math.sin(filledEnd)
      const glow = ctx.createRadialGradient(tipX, tipY, 0, tipX, tipY, 14)
      glow.addColorStop(0, color + 'aa')
      glow.addColorStop(1, 'transparent')
      ctx.beginPath()
      ctx.arc(tipX, tipY, 14, 0, Math.PI * 2)
      ctx.fillStyle = glow
      ctx.fill()
    }
  }, [animated, color])

  return (
    <div style={{ position: 'relative', width: 160, height: 160, flexShrink: 0 }}>
      <canvas ref={canvasRef} width={160} height={160} style={{ position: 'absolute', inset: 0 }} />
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: '2.25rem', fontWeight: 800, color, lineHeight: 1, letterSpacing: '-0.04em' }}>
          {animated}
        </span>
        <span style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.4)', marginTop: 2, letterSpacing: '0.12em' }}>
          / 100
        </span>
      </div>
    </div>
  )
}

// ── Helper: category horizontal bar ──────────────────────────────────────────

function CategoryBar({ label, value, max }: { label: string; value: number | null | undefined; max: number }) {
  const v = value ?? 0
  const pct = Math.min(100, (v / max) * 100)
  const color = v >= max * 0.85 ? '#ef4444' : v >= max * 0.6 ? '#f59e0b' : v >= max * 0.35 ? '#3b82f6' : '#10b981'
  const riskLabel = v >= max * 0.85 ? 'CRITICAL' : v >= max * 0.6 ? 'HIGH' : v >= max * 0.35 ? 'MEDIUM' : 'LOW'
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text)' }}>{label}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: '0.65rem', fontWeight: 700, color, letterSpacing: '0.08em' }}>{riskLabel}</span>
          <span style={{ fontSize: '0.8125rem', fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>{v}/{max}</span>
        </div>
      </div>
      <div style={{ height: 8, borderRadius: 99, background: 'rgba(255,255,255,0.07)', overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${pct}%`, borderRadius: 99,
          background: `linear-gradient(90deg, ${color}88, ${color})`,
          transition: 'width 800ms cubic-bezier(0.34, 1.56, 0.64, 1)',
          boxShadow: `0 0 8px ${color}66`,
        }} />
      </div>
    </div>
  )
}

// ── Helper: severity badge ────────────────────────────────────────────────────

function SeverityBadge({ severity }: { severity: string }) {
  const cfg: Record<string, { bg: string; color: string; label: string }> = {
    critical: { bg: 'rgba(239,68,68,0.15)', color: '#ef4444', label: 'CRITICAL' },
    high:     { bg: 'rgba(249,115,22,0.15)', color: '#f97316', label: 'HIGH' },
    medium:   { bg: 'rgba(245,158,11,0.15)', color: '#f59e0b', label: 'MEDIUM' },
    low:      { bg: 'rgba(16,185,129,0.15)', color: '#10b981', label: 'LOW' },
  }
  const s = cfg[severity.toLowerCase()] ?? cfg.medium
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '2px 8px', borderRadius: 99,
      fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.08em',
      background: s.bg, color: s.color, border: `1px solid ${s.color}44`,
    }}>
      {s.label}
    </span>
  )
}

// ── Helper: collapsible finding card ─────────────────────────────────────────

function FindingCard({ finding, index }: { finding: AnalysisReportResponse['agent_findings'][0]; index: number }) {
  const [open, setOpen] = useState(index === 0)
  const agentLabel = (finding.agent || '').replace(/_agent$/, '').replace(/_/g, ' ')
  const signalLabel = (finding.signal || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  const colors: Record<string, string> = {
    critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#10b981',
  }
  const col = colors[finding.severity?.toLowerCase()] ?? '#f59e0b'

  return (
    <div style={{
      borderRadius: 10, border: `1px solid ${col}33`,
      background: `${col}08`, overflow: 'hidden',
      transition: 'box-shadow 200ms ease',
    }}>
      <button
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 12,
          padding: '0.875rem 1rem', background: 'transparent', border: 'none',
          cursor: 'pointer', textAlign: 'left',
        }}
        onClick={() => setOpen(o => !o)}
      >
        <div style={{
          width: 32, height: 32, borderRadius: 8, flexShrink: 0,
          background: `${col}18`, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: col,
        }}>
          <AlertOctagonIcon size={15} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--color-text)' }}>{signalLabel}</span>
            <SeverityBadge severity={finding.severity} />
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', margin: '2px 0 0', textTransform: 'capitalize' }}>
            {agentLabel} · {finding.source}
            {finding.confidence != null && ` · ${(finding.confidence * 100).toFixed(0)}% confidence`}
            {finding.start_time != null && ` · ${finding.start_time.toFixed(1)}s–${finding.end_time?.toFixed(1)}s`}
          </p>
        </div>
        <div style={{ color: 'var(--color-text-muted)', flexShrink: 0 }}>
          {open ? <ChevronUpIcon size={16} /> : <ChevronDownIcon size={16} />}
        </div>
      </button>
      {open && (
        <div style={{
          padding: '0 1rem 0.875rem',
          borderTop: `1px solid ${col}22`,
        }}>
          <p style={{
            fontSize: '0.875rem', color: 'var(--color-text-muted)',
            fontStyle: 'italic', lineHeight: 1.6,
            borderLeft: `3px solid ${col}55`, paddingLeft: 12, marginTop: 8,
          }}>
            "{finding.evidence_text}"
          </p>
        </div>
      )}
    </div>
  )
}

// ── Helper: transcript segment ────────────────────────────────────────────────

function TranscriptSegment({ seg, index }: {
  seg: { speaker?: string | null; text: string; start: number; end: number; language?: string | null }
  index: number
}) {
  const isVictim = (seg.speaker ?? '').includes('VICTIM') || (seg.speaker ?? '').includes('USER')
  return (
    <div style={{
      display: 'flex', gap: 10, alignItems: 'flex-start',
      padding: '0.625rem 0',
      borderBottom: '1px solid rgba(255,255,255,0.05)',
    }}>
      <div style={{
        width: 56, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 2,
        alignItems: 'center', paddingTop: 2,
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
          background: isVictim ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.12)',
          border: `1.5px solid ${isVictim ? 'rgba(16,185,129,0.35)' : 'rgba(239,68,68,0.3)'}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '0.625rem', fontWeight: 700,
          color: isVictim ? '#10b981' : '#ef4444',
        }}>
          {isVictim ? 'YOU' : 'C'}
        </div>
        <span style={{ fontSize: '0.6rem', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>
          {seg.start.toFixed(1)}s
        </span>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{
          fontSize: '0.85rem', lineHeight: 1.6,
          color: isVictim ? 'var(--color-text)' : 'rgba(255,255,255,0.85)',
          margin: 0,
        }}>
          {isVictim
            ? <span style={{ color: '#ef4444', fontWeight: 600, fontSize: '0.7rem', marginRight: 6 }}>⚠ VICTIM RESPONSE</span>
            : <span style={{ color: '#f97316', fontWeight: 600, fontSize: '0.7rem', marginRight: 6 }}>CALLER</span>
          }
          {seg.text}
        </p>
      </div>
    </div>
  )
}

// ── Helper: Section wrapper ───────────────────────────────────────────────────

function Section({
  icon, title, badge, children, accentColor,
}: {
  icon: React.ReactNode; title: string; badge?: React.ReactNode;
  children: React.ReactNode; accentColor?: string
}) {
  return (
    <div style={{
      background: 'var(--color-panel)',
      border: '1px solid var(--color-border)',
      borderRadius: 12,
      overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '0.875rem 1.25rem',
        borderBottom: '1px solid var(--color-border)',
        background: 'rgba(255,255,255,0.02)',
        borderLeft: accentColor ? `3px solid ${accentColor}` : undefined,
      }}>
        <div style={{ color: accentColor ?? 'var(--color-accent)', flexShrink: 0 }}>{icon}</div>
        <h2 style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'var(--color-text)', flex: 1 }}>{title}</h2>
        {badge}
      </div>
      <div style={{ padding: '1.25rem' }}>{children}</div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

interface AnalysisReportProps {
  callId?: string
  recordingName?: string
  submittedAt?: string
  onBack?: () => void
}

export function AnalysisReport({ callId, recordingName, onBack }: AnalysisReportProps) {
  const [report, setReport] = useState<AnalysisReportResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'transcript'>('overview')

  useEffect(() => {
    if (!callId) return
    setLoading(true)
    setError(null)
    apiClient.getReport(callId).then(data => {
      if (data) setReport(data)
      else setError('Failed to load report. The backend may be unavailable.')
      setLoading(false)
    })
  }, [callId])

  const level = report?.level?.toUpperCase() ?? 'UNKNOWN'
  const levelColors: Record<string, { primary: string; glow: string; bg: string }> = {
    CRITICAL: { primary: '#ef4444', glow: 'rgba(239,68,68,0.15)', bg: 'rgba(239,68,68,0.06)' },
    HIGH:     { primary: '#f97316', glow: 'rgba(249,115,22,0.15)', bg: 'rgba(249,115,22,0.06)' },
    MEDIUM:   { primary: '#f59e0b', glow: 'rgba(245,158,11,0.15)', bg: 'rgba(245,158,11,0.06)' },
    LOW:      { primary: '#10b981', glow: 'rgba(16,185,129,0.15)', bg: 'rgba(16,185,129,0.06)' },
  }
  const lc = levelColors[level] ?? levelColors.MEDIUM

  if (loading) {
    return (
      <div className="page-content" style={{ alignItems: 'center', justifyContent: 'center', minHeight: 400 }}>
        <div style={{ textAlign: 'center', color: 'var(--color-text-muted)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <BrainCircuitIcon size={32} className="analysis-status__spinner" style={{ color: 'var(--color-accent)' }} />
          <p>Loading analysis report…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-content">
        {onBack && <button className="btn-ghost btn-ghost--sm" onClick={onBack} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}><ArrowLeftIcon size={14} /> Back</button>}
        <div style={{
          padding: '2rem', textAlign: 'center', background: 'var(--color-panel)',
          border: '1px solid rgba(239,68,68,0.2)', borderRadius: 12, color: 'var(--color-critical)',
        }}>
          <XCircleIcon size={32} style={{ marginBottom: 12 }} />
          <p style={{ fontWeight: 600 }}>Error loading report</p>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginTop: 4 }}>{error}</p>
        </div>
      </div>
    )
  }

  if (!callId || !report) {
    return (
      <div className="page-content">
        <div className="page-heading">
          <div className="page-heading__icon-wrap"><FileTextIcon size={20} strokeWidth={1.75} /></div>
          <div>
            <h1 className="page-heading__title">Analysis Report</h1>
            <p className="page-heading__subtitle">No report selected. Upload and analyse a call recording first.</p>
          </div>
        </div>
        <div className="info-card info-card--warn">
          <InfoIcon size={14} className="info-card__icon" />
          <p className="info-card__text">
            <strong>No analysis yet.</strong> Navigate to "Analyse a Call" and upload a recording to generate a report.
          </p>
        </div>
      </div>
    )
  }

  const voiceSpoof = report.voice?.spoof_prob ?? 0
  const voicePct = Math.round(voiceSpoof * 100)

  return (
    <div className="page-content">
      {/* Back */}
      {onBack && (
        <button
          className="btn-ghost btn-ghost--sm"
          onClick={onBack}
          style={{ display: 'flex', alignItems: 'center', gap: 6, alignSelf: 'flex-start' }}
        >
          <ArrowLeftIcon size={14} /> Back
        </button>
      )}

      {/* ── WARNING BANNER ───────────────────────────────────────── */}
      {report.warnings.length > 0 && (
        <div style={{
          background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)',
          borderRadius: 10, padding: '0.75rem 1rem',
          display: 'flex', gap: 10, alignItems: 'flex-start',
        }}>
          <AlertTriangleIcon size={16} style={{ color: '#f59e0b', flexShrink: 0, marginTop: 1 }} />
          <div style={{ flex: 1 }}>
            {report.warnings.map((w, i) => (
              <p key={i} style={{ fontSize: '0.8125rem', color: '#f59e0b', margin: 0 }}>{w}</p>
            ))}
          </div>
          <span style={{
            fontSize: '0.65rem', fontWeight: 700, padding: '2px 8px',
            borderRadius: 99, background: 'rgba(245,158,11,0.2)',
            color: '#f59e0b', border: '1px solid rgba(245,158,11,0.35)',
            letterSpacing: '0.08em', flexShrink: 0,
          }}>
            ANALYSIS MODE: {report.analysis_mode.toUpperCase()}
          </span>
        </div>
      )}

      {/* ── HERO HEADER CARD ─────────────────────────────────────── */}
      <div style={{
        background: `linear-gradient(135deg, ${lc.bg} 0%, rgba(17,24,39,0.5) 100%)`,
        border: `1px solid ${lc.primary}33`,
        borderRadius: 14, padding: '1.5rem',
        boxShadow: `0 0 40px ${lc.glow}`,
        position: 'relative', overflow: 'hidden',
      }}>
        {/* Background label watermark */}
        <div style={{
          position: 'absolute', right: -20, top: -10,
          fontSize: '7rem', fontWeight: 900, letterSpacing: '-0.06em',
          color: `${lc.primary}08`, lineHeight: 1, userSelect: 'none', pointerEvents: 'none',
        }}>
          {level}
        </div>

        <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'flex-start', flexWrap: 'wrap' }}>
          {/* Score Gauge */}
          <ScoreGauge score={report.score} level={level} />

          {/* Main info */}
          <div style={{ flex: 1, minWidth: 260 }}>
            {/* Risk level badge + killchain */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '4px 14px', borderRadius: 99,
                background: lc.glow, border: `1px solid ${lc.primary}55`,
                color: lc.primary, fontSize: '0.75rem', fontWeight: 800,
                letterSpacing: '0.1em',
              }}>
                <ShieldIcon size={12} />
                {level} THREAT LEVEL
              </span>
              {report.killchain_stage && (
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  padding: '4px 12px', borderRadius: 99,
                  background: 'rgba(249,115,22,0.12)', border: '1px solid rgba(249,115,22,0.3)',
                  color: '#f97316', fontSize: '0.7rem', fontWeight: 700,
                  letterSpacing: '0.08em',
                }}>
                  <GitMergeIcon size={11} />
                  KILL-CHAIN: {report.killchain_stage.toUpperCase()}
                </span>
              )}
              <span style={{
                fontSize: '0.65rem', fontWeight: 600, color: 'var(--color-text-muted)',
                fontFamily: 'var(--font-mono)',
              }}>
                {report.call_id.slice(0, 8).toUpperCase()}
              </span>
            </div>

            {/* Main threat description */}
            <h1 style={{
              fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-text)',
              lineHeight: 1.3, marginBottom: 6,
            }}>
              {level === 'CRITICAL'
                ? 'Coercive Authority Impersonation with Real-Time Deepfake Voice Signature'
                : level === 'HIGH'
                ? 'High-Probability Social Engineering Attack Detected'
                : level === 'MEDIUM'
                ? 'Suspicious Patterns Detected — Verification Recommended'
                : 'Call Appears Legitimate — Low Risk Indicators'}
            </h1>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', lineHeight: 1.6, marginBottom: 12 }}>
              {report.reasons[0]}
            </p>

            {/* Meta row */}
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              {[
                { label: 'CREATED', value: new Date(report.created_at).toLocaleString() },
                { label: 'COMPLETED', value: report.completed_at ? new Date(report.completed_at).toLocaleString() : '—' },
                { label: 'LANGUAGE', value: report.language?.toUpperCase() ?? 'EN' },
                { label: 'MODE', value: report.analysis_mode.toUpperCase() },
              ].map(({ label, value }) => (
                <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <span style={{ fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--color-text-muted)' }}>
                    {label}
                  </span>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text)', fontFamily: 'var(--font-mono)' }}>
                    {value}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Score breakdown mini */}
          {report.category_scores && (
            <div style={{
              background: 'rgba(0,0,0,0.25)', borderRadius: 10,
              padding: '0.875rem 1rem', minWidth: 200, flexShrink: 0,
              border: '1px solid rgba(255,255,255,0.06)',
            }}>
              <p style={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.1em', color: 'var(--color-text-muted)', marginBottom: 10 }}>
                PRIMARY CAUSES
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  { l: 'Identity', v: report.category_scores.identity, m: 25 },
                  { l: 'Request', v: report.category_scores.request, m: 30 },
                  { l: 'Behavior', v: report.category_scores.behavior, m: 20 },
                  { l: 'Channel', v: report.category_scores.channel, m: 15 },
                  { l: 'Voice', v: report.category_scores.voice, m: 10 },
                ].map(({ l, v, m }) => (
                  <CategoryBar key={l} label={l} value={v} max={m} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── TABS ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--color-border)', paddingBottom: 0 }}>
        {(['overview', 'transcript'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '0.5rem 1rem', border: 'none', background: 'transparent', cursor: 'pointer',
              fontSize: '0.875rem', fontWeight: 600,
              color: activeTab === tab ? 'var(--color-accent)' : 'var(--color-text-muted)',
              borderBottom: activeTab === tab ? '2px solid var(--color-accent)' : '2px solid transparent',
              marginBottom: -1, textTransform: 'capitalize',
              transition: 'color 150ms ease',
            }}
          >
            {tab === 'overview' ? '📊 Overview' : '🎙 Transcript & Audio'}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>

          {/* ── LEFT COLUMN ───────────────────────────────────────── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

            {/* Fired Rules */}
            {report.fired_rules && report.fired_rules.length > 0 && (
              <Section
                icon={<ZapIcon size={15} />}
                title="Fired Threat Rules"
                accentColor="#f59e0b"
                badge={
                  <span style={{
                    fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                    background: 'rgba(245,158,11,0.12)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.25)',
                  }}>
                    {report.fired_rules.length} ACTIVE
                  </span>
                }
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {report.fired_rules.map((rule, i) => (
                    <span key={i} style={{
                      display: 'inline-flex', alignItems: 'center', gap: 5,
                      padding: '4px 10px', borderRadius: 6,
                      fontSize: '0.75rem', fontWeight: 600, fontFamily: 'var(--font-mono)',
                      background: 'rgba(239,68,68,0.08)', color: '#ef4444',
                      border: '1px solid rgba(239,68,68,0.2)',
                    }}>
                      <ZapIcon size={9} />
                      {rule}
                    </span>
                  ))}
                </div>
              </Section>
            )}

            {/* Agent Findings */}
            <Section
              icon={<BrainCircuitIcon size={15} />}
              title="Multi-Agent Intelligence Findings"
              accentColor="#06b6d4"
              badge={
                report.agent_findings.length > 0 ? (
                  <span style={{
                    fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                    background: 'rgba(6,182,212,0.12)', color: '#06b6d4', border: '1px solid rgba(6,182,212,0.25)',
                  }}>
                    {report.agent_findings.length} SIGNALS
                  </span>
                ) : undefined
              }
            >
              {report.agent_findings.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {report.agent_findings.map((f, i) => (
                    <FindingCard key={i} finding={f} index={i} />
                  ))}
                </div>
              ) : (
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>No findings from agents.</p>
              )}
            </Section>

            {/* Counterfactuals */}
            {report.counterfactuals && report.counterfactuals.length > 0 && (
              <Section
                icon={<BarChart2Icon size={15} />}
                title="Counterfactual Risk Explainer"
                accentColor="#8b5cf6"
                badge={
                  <span style={{
                    fontSize: '0.7rem', color: 'var(--color-text-muted)',
                    fontStyle: 'italic',
                  }}>
                    Hypothetical what-if scenarios
                  </span>
                }
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {report.counterfactuals.map((cf, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'center', gap: 12,
                      padding: '0.75rem', borderRadius: 8,
                      background: 'rgba(139,92,246,0.06)', border: '1px solid rgba(139,92,246,0.15)',
                    }}>
                      <div style={{ flex: 1 }}>
                        <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', margin: 0 }}>
                          If {cf.change}
                        </p>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Score drops to</span>
                        <span style={{
                          fontSize: '1rem', fontWeight: 800,
                          color: cf.new_score < 40 ? '#10b981' : cf.new_score < 70 ? '#f59e0b' : '#ef4444',
                          fontFamily: 'var(--font-mono)',
                        }}>
                          {cf.new_score}
                        </span>
                        <span style={{ fontSize: '0.65rem', color: '#10b981', fontWeight: 700 }}>
                          ↓{report.score - cf.new_score}pts
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </Section>
            )}
          </div>

          {/* ── RIGHT COLUMN ──────────────────────────────────────── */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

            {/* Voice Evidence */}
            <Section
              icon={<WavesIcon size={15} />}
              title="Voice Evidence & Deepfake Forensics"
              accentColor={voicePct > 60 ? '#ef4444' : '#10b981'}
              badge={
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                  background: voicePct > 60 ? 'rgba(239,68,68,0.12)' : 'rgba(16,185,129,0.12)',
                  color: voicePct > 60 ? '#ef4444' : '#10b981',
                  border: `1px solid ${voicePct > 60 ? 'rgba(239,68,68,0.3)' : 'rgba(16,185,129,0.3)'}`,
                  letterSpacing: '0.06em',
                }}>
                  {report.voice?.status === 'ok'
                    ? `${voicePct}% SYNTHETIC | CLONE DETECTED`
                    : (report.voice?.status ?? 'UNAVAILABLE').toUpperCase()}
                </span>
              }
            >
              {report.voice ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {/* Spoof prob bar */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>SPOOF PROBABILITY</span>
                      <span style={{ fontSize: '0.875rem', fontWeight: 800, color: voicePct > 60 ? '#ef4444' : '#10b981', fontFamily: 'var(--font-mono)' }}>
                        {voicePct}%
                      </span>
                    </div>
                    <div style={{ height: 10, borderRadius: 99, background: 'rgba(255,255,255,0.07)', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%', width: `${voicePct}%`, borderRadius: 99,
                        background: voicePct > 80 ? 'linear-gradient(90deg, #ef444488, #ef4444)' :
                          voicePct > 60 ? 'linear-gradient(90deg, #f9731688, #f97316)' :
                          'linear-gradient(90deg, #10b98188, #10b981)',
                        boxShadow: `0 0 8px ${voicePct > 60 ? '#ef444466' : '#10b98166'}`,
                      }} />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 3 }}>
                      <span style={{ fontSize: '0.6rem', color: 'rgba(255,255,255,0.2)' }}>Authentic</span>
                      <span style={{ fontSize: '0.6rem', color: 'rgba(255,255,255,0.2)' }}>Synthetic / Clone</span>
                    </div>
                  </div>

                  {/* Voice metrics grid */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    {[
                      { label: 'Windows Analyzed', value: report.voice.windows_analyzed ?? '—' },
                      { label: 'SNR (dB)', value: (report.voice.quality as Record<string, unknown>)?.snr_db ?? '—' },
                      { label: 'Duration (s)', value: (report.voice.quality as Record<string, unknown>)?.duration_s ?? '—' },
                      { label: 'Model', value: report.voice.model ? report.voice.model.split('/').pop()?.split(' ')[0] : '—' },
                    ].map(({ label, value }) => (
                      <div key={label} style={{
                        padding: '0.5rem 0.75rem', borderRadius: 8,
                        background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)',
                      }}>
                        <p style={{ fontSize: '0.6rem', color: 'var(--color-text-muted)', fontWeight: 700, letterSpacing: '0.08em', margin: 0 }}>
                          {label.toUpperCase()}
                        </p>
                        <p style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--color-text)', fontFamily: 'var(--font-mono)', margin: '2px 0 0' }}>
                          {String(value)}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* Speaker match */}
                  {report.voice.speaker_match && (
                    <div style={{
                      padding: '0.75rem', borderRadius: 8,
                      background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)',
                    }}>
                      <p style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 6 }}>SPEAKER MATCH</p>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                          {report.voice.speaker_match.claimed_contact ?? 'No contact claimed'}
                        </span>
                        <span style={{
                          fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)',
                          color: (report.voice.speaker_match.similarity ?? 0) > 0.7 ? '#10b981' : '#ef4444',
                        }}>
                          {report.voice.speaker_match.enrolled
                            ? `${Math.round((report.voice.speaker_match.similarity ?? 0) * 100)}% match`
                            : 'Not enrolled'}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', fontStyle: 'italic' }}>
                  Voice analysis unavailable for this recording.
                </p>
              )}
            </Section>

            {/* Tactical Action Protocol (Verification) */}
            {report.verification && (
              <Section
                icon={<PhoneOffIcon size={15} />}
                title="Tactical Action Protocol"
                accentColor="#ef4444"
                badge={
                  <span style={{
                    fontSize: '0.65rem', fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                    background: 'rgba(239,68,68,0.15)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.3)',
                    letterSpacing: '0.08em',
                  }}>
                    PRIORITY ALERT
                  </span>
                }
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{
                    padding: '1rem', borderRadius: 10,
                    background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
                  }}>
                    <p style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 6 }}>
                      IMMEDIATE ACTION
                    </p>
                    <p style={{ fontSize: '1rem', fontWeight: 800, color: '#ef4444', letterSpacing: '0.02em', lineHeight: 1.4 }}>
                      HANG UP & CALL BACK USING OFFICIAL NUMBER
                    </p>
                  </div>

                  {report.verification.action && (
                    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                      <PhoneIcon size={14} style={{ color: 'var(--color-accent)', flexShrink: 0, marginTop: 2 }} />
                      <div>
                        <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontWeight: 600, margin: 0 }}>
                          {report.verification.action.replace(/_/g, ' ').toUpperCase()}
                        </p>
                        <p style={{ fontSize: '0.875rem', color: 'var(--color-text)', margin: '2px 0 0' }}>
                          {report.verification.target}
                        </p>
                      </div>
                    </div>
                  )}

                  {report.verification.safe_word_prompt && (
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '0.625rem 0.875rem', borderRadius: 8,
                      background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)',
                    }}>
                      <CheckCircle2Icon size={14} style={{ color: '#10b981', flexShrink: 0 }} />
                      <span style={{ fontSize: '0.8125rem', color: 'var(--color-text)' }}>
                        Ask for your agreed <strong style={{ color: '#10b981' }}>safe word / passphrase</strong>
                      </span>
                    </div>
                  )}

                  <a
                    href="https://cybercrime.gov.in"
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                      padding: '0.625rem', borderRadius: 8, textDecoration: 'none',
                      background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)',
                      color: '#ef4444', fontSize: '0.8125rem', fontWeight: 600,
                    }}
                  >
                    <ExternalLinkIcon size={13} />
                    Report at cybercrime.gov.in
                  </a>
                </div>
              </Section>
            )}

            {/* Immediate Safeguards */}
            {report.recommended_actions.length > 0 && (
              <Section
                icon={<ShieldIcon size={15} />}
                title="Immediate Safeguards"
                accentColor="#10b981"
              >
                <ol style={{ margin: 0, paddingLeft: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {report.recommended_actions.map((action, i) => (
                    <li key={i} style={{
                      display: 'flex', gap: 10, alignItems: 'flex-start',
                      padding: '0.625rem 0.75rem', borderRadius: 8,
                      background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)',
                    }}>
                      <span style={{
                        width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                        background: i === 0 ? 'rgba(239,68,68,0.15)' : 'rgba(16,185,129,0.1)',
                        border: `1.5px solid ${i === 0 ? 'rgba(239,68,68,0.4)' : 'rgba(16,185,129,0.3)'}`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '0.625rem', fontWeight: 800,
                        color: i === 0 ? '#ef4444' : '#10b981',
                      }}>
                        {i + 1}
                      </span>
                      <span style={{
                        fontSize: '0.8125rem', color: 'var(--color-text)', lineHeight: 1.5,
                        fontWeight: i === 0 ? 700 : 400,
                      }}>
                        {action}
                      </span>
                    </li>
                  ))}
                </ol>
              </Section>
            )}
          </div>
        </div>
      )}

      {/* ── TRANSCRIPT TAB ───────────────────────────────────────── */}
      {activeTab === 'transcript' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '1.25rem' }}>
          <Section
            icon={<FileTextIcon size={15} />}
            title="Forensic Transcript & Audio Stream"
            accentColor="#06b6d4"
            badge={
              <div style={{ display: 'flex', gap: 8 }}>
                {report.transcript && (
                  <span style={{
                    fontSize: '0.65rem', fontWeight: 700, padding: '2px 8px', borderRadius: 99,
                    background: 'rgba(16,185,129,0.12)', color: '#10b981', border: '1px solid rgba(16,185,129,0.25)',
                  }}>
                    {report.transcript.is_mock ? 'MOCK' : 'REAL'} TRACK
                  </span>
                )}
              </div>
            }
          >
            {report.transcript?.segments && report.transcript.segments.length > 0 ? (
              <div>
                {report.transcript.segments.map((seg, i) => (
                  <TranscriptSegment key={i} seg={seg} index={i} />
                ))}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-text-muted)' }}>
                <MessageSquareIcon size={28} strokeWidth={1} style={{ marginBottom: 8 }} />
                <p>No transcript available</p>
              </div>
            )}
          </Section>

          {/* Social engineering reasons in transcript tab */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {report.reasons.length > 0 && (
              <Section icon={<ActivityIcon size={15} />} title="Behaviour Analysis" accentColor="#f59e0b">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {report.reasons.map((r, i) => (
                    <div key={i} style={{
                      display: 'flex', gap: 8, alignItems: 'flex-start',
                      padding: '0.5rem 0.75rem', borderRadius: 8,
                      background: 'rgba(245,158,11,0.05)', border: '1px solid rgba(245,158,11,0.15)',
                    }}>
                      <AlertTriangleIcon size={13} style={{ color: '#f59e0b', flexShrink: 0, marginTop: 2 }} />
                      <span style={{ fontSize: '0.8125rem', color: 'var(--color-text)', lineHeight: 1.5 }}>{r}</span>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Recording info */}
            <Section icon={<FileAudioIcon size={15} />} title="Recording Metadata" accentColor="#6b7280">
              <dl style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[
                  { label: 'Call ID', value: report.call_id },
                  { label: 'Status', value: report.status.toUpperCase() },
                  { label: 'Mode', value: report.analysis_mode.toUpperCase() },
                  { label: 'Language', value: report.language ?? 'EN' },
                  { label: 'Created', value: new Date(report.created_at).toLocaleString() },
                  report.completed_at ? { label: 'Completed', value: new Date(report.completed_at).toLocaleString() } : null,
                ].filter(Boolean).map(({ label, value }) => (
                  <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                    <dt style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontWeight: 600, flexShrink: 0 }}>{label}</dt>
                    <dd style={{ fontSize: '0.75rem', color: 'var(--color-text)', fontFamily: 'var(--font-mono)', textAlign: 'right', wordBreak: 'break-all' }}>
                      {value}
                    </dd>
                  </div>
                ))}
              </dl>
            </Section>
          </div>
        </div>
      )}
    </div>
  )
}
