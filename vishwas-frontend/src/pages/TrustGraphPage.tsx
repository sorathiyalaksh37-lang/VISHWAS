import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import {
  UsersIcon, PlusIcon, UserIcon, BuildingIcon,
  ClockIcon, MicIcon, CheckCircle2Icon, XCircleIcon,
  LoaderIcon, SearchIcon, RefreshCwIcon, PhoneIcon, UploadIcon,
  AlertCircleIcon,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Contact {
  contact_id: string
  name: string
  relation: string | null
  saved_numbers: string[]
  voiceprint_enrolled: boolean
  voiceprint_enrolled_at: string | null
  trust_level: 'high' | 'medium' | 'low'
  trust_flagged_at: string | null
  trust_flagged_by_call_id: string | null
}

interface GraphNode {
  id: string
  label: string
  relation: string
  enrolled: boolean
  trust_level: string
  x: number
  y: number
  vx: number
  vy: number
}

// ── Constants ─────────────────────────────────────────────────────────────────

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const RELATION_OPTIONS = [
  'Mother', 'Father', 'Spouse', 'Sibling', 'Child',
  'Bank', 'Friend', 'Colleague', 'Doctor', 'Other',
]

function relationIcon(rel: string | null) {
  const r = (rel || '').toLowerCase()
  if (['bank', 'institution', 'company'].some(k => r.includes(k))) return BuildingIcon
  return UserIcon
}

function trustColor(trust: string | undefined): string {
  switch ((trust || 'high').toLowerCase()) {
    case 'low':    return '#ef4444'  // red — flagged
    case 'medium': return '#f59e0b'  // orange — suspicious
    default:       return '#10b981'  // green — trusted
  }
}

// ── Force-directed graph layout ───────────────────────────────────────────────

function layoutNodes(contacts: Contact[], width: number, height: number): GraphNode[] {
  const cx = width / 2
  const cy = height / 2
  const radius = Math.min(width, height) * 0.35
  return contacts.map((c, i) => {
    const angle = (i / contacts.length) * 2 * Math.PI - Math.PI / 2
    return {
      id: c.contact_id,
      label: c.name,
      relation: c.relation || 'Contact',
      enrolled: c.voiceprint_enrolled,
      trust_level: c.trust_level || 'high',
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
      vx: 0, vy: 0,
    }
  })
}

// ── Trust Graph Canvas ────────────────────────────────────────────────────────

function TrustGraphCanvas({
  nodes,
  selected,
  onSelect,
}: {
  nodes: GraphNode[]
  selected: string | null
  onSelect: (id: string) => void
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animRef = useRef<number>(0)
  const nodesRef = useRef(nodes)
  nodesRef.current = nodes

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    const W = canvas.width
    const H = canvas.height
    ctx.clearRect(0, 0, W, H)

    const cx = W / 2
    const cy = H / 2

    // Draw edges
    nodesRef.current.forEach(n => {
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.lineTo(n.x, n.y)
      ctx.strokeStyle = n.trust_level === 'low'
        ? 'rgba(239,68,68,0.3)'
        : n.trust_level === 'medium'
        ? 'rgba(245,158,11,0.2)'
        : n.enrolled
        ? 'rgba(16,185,129,0.25)'
        : 'rgba(156,163,175,0.15)'
      ctx.lineWidth = n.trust_level === 'low' ? 2 : n.enrolled ? 1.5 : 1
      ctx.setLineDash(n.trust_level === 'low' ? [6, 3] : n.enrolled ? [] : [4, 4])
      ctx.stroke()
      ctx.setLineDash([])
    })

    // Draw center "You" node
    ctx.beginPath()
    ctx.arc(cx, cy, 22, 0, Math.PI * 2)
    ctx.fillStyle = '#10b981'
    ctx.fill()
    ctx.strokeStyle = 'rgba(16,185,129,0.4)'
    ctx.lineWidth = 3
    ctx.stroke()
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 11px Inter, sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText('YOU', cx, cy)

    // Draw contact nodes
    nodesRef.current.forEach(n => {
      const isSelected = n.id === selected
      const color = trustColor(n.trust_level)
      const r = isSelected ? 20 : 16

      // Glow for selected
      if (isSelected) {
        ctx.beginPath()
        ctx.arc(n.x, n.y, r + 8, 0, Math.PI * 2)
        ctx.fillStyle = `${color}22`
        ctx.fill()
      }

      ctx.beginPath()
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2)
      ctx.fillStyle = '#111827'
      ctx.fill()
      ctx.strokeStyle = color
      ctx.lineWidth = isSelected ? 2.5 : 1.5
      ctx.stroke()

      // Initials
      const initials = n.label.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
      ctx.fillStyle = color
      ctx.font = `${isSelected ? 'bold' : '600'} ${isSelected ? 11 : 10}px Inter, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(initials, n.x, n.y)

      // Label below
      ctx.fillStyle = isSelected ? '#f9fafb' : '#9ca3af'
      ctx.font = `${isSelected ? '600' : '400'} 10px Inter, sans-serif`
      ctx.fillText(n.label.split(' ')[0], n.x, n.y + r + 11)

      // Status dot (top-right corner of node)
      if (n.trust_level === 'low') {
        // Red warning dot for flagged contacts
        ctx.beginPath()
        ctx.arc(n.x + r - 3, n.y - r + 3, 5, 0, Math.PI * 2)
        ctx.fillStyle = '#ef4444'
        ctx.fill()
        ctx.strokeStyle = '#111827'
        ctx.lineWidth = 1.5
        ctx.stroke()
        // Exclamation mark
        ctx.fillStyle = '#fff'
        ctx.font = 'bold 7px Inter, sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText('!', n.x + r - 3, n.y - r + 3)
      } else if (n.enrolled) {
        // Green check dot for enrolled contacts
        ctx.beginPath()
        ctx.arc(n.x + r - 3, n.y - r + 3, 4, 0, Math.PI * 2)
        ctx.fillStyle = '#10b981'
        ctx.fill()
        ctx.strokeStyle = '#111827'
        ctx.lineWidth = 1.5
        ctx.stroke()
      } else if (n.trust_level === 'medium') {
        // Orange warning dot for suspicious
        ctx.beginPath()
        ctx.arc(n.x + r - 3, n.y - r + 3, 4, 0, Math.PI * 2)
        ctx.fillStyle = '#f59e0b'
        ctx.fill()
        ctx.strokeStyle = '#111827'
        ctx.lineWidth = 1.5
        ctx.stroke()
      }
    })
  }, [selected])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio
      canvas.height = canvas.offsetHeight * window.devicePixelRatio
      const ctx = canvas.getContext('2d')!
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
    }
    resize()
    window.addEventListener('resize', resize)
    return () => window.removeEventListener('resize', resize)
  }, [])

  useEffect(() => {
    const loop = () => { draw(); animRef.current = requestAnimationFrame(loop) }
    animRef.current = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(animRef.current)
  }, [draw])

  // Click detection
  function handleClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current!
    const rect = canvas.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    for (const n of nodesRef.current) {
      const dx = mx - n.x
      const dy = my - n.y
      if (Math.sqrt(dx * dx + dy * dy) < 20) { onSelect(n.id); return }
    }
    onSelect('')
  }

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '100%', cursor: 'pointer', borderRadius: 12 }}
      onClick={handleClick}
    />
  )
}

// ── Add Contact Modal ─────────────────────────────────────────────────────────

function AddContactModal({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const [name, setName] = useState('')
  const [relation, setRelation] = useState('')
  const [numbers, setNumbers] = useState([''])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit() {
    if (!name.trim()) { setError('Name is required'); return }
    setLoading(true)
    setError('')
    const nums = numbers.filter(n => n.trim()).join(',')
    const url = `${API_BASE}/contacts?name=${encodeURIComponent(name.trim())}${relation ? `&relation=${encodeURIComponent(relation)}` : ''}${nums ? `&saved_numbers=${encodeURIComponent(nums)}` : ''}`
    try {
      const token = localStorage.getItem('vishwas:auth_token')
      const headers: HeadersInit = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }
      
      const r = await fetch(url, { method: 'POST', headers })
      if (!r.ok) {
        if (r.status === 401) {
          throw new Error('Authentication required. Please refresh the page.')
        }
        throw new Error(await r.text())
      }
      onAdded()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add contact')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Add Trusted Contact</h3>
          <button className="analyse-file-remove" onClick={onClose}><XCircleIcon size={18} /></button>
        </div>

        {error && (
          <div className="analysis-status analysis-status--error" style={{ marginBottom: 12 }}>
            <AlertCircleIcon size={14} />
            <span>{error}</span>
          </div>
        )}

        <div className="modal-field">
          <label className="modal-label">Name *</label>
          <input
            className="modal-input"
            placeholder="e.g. Mom, HDFC Bank"
            value={name}
            onChange={e => setName(e.target.value)}
          />
        </div>

        <div className="modal-field">
          <label className="modal-label">Relation</label>
          <select className="modal-input" value={relation} onChange={e => setRelation(e.target.value)}>
            <option value="">Select relation...</option>
            {RELATION_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>

        <div className="modal-field">
          <label className="modal-label">Phone Numbers</label>
          {numbers.map((n, i) => (
            <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
              <input
                className="modal-input"
                style={{ margin: 0, flex: 1 }}
                placeholder="+91-98xxxxxxxx"
                value={n}
                onChange={e => setNumbers(nums => nums.map((v, j) => j === i ? e.target.value : v))}
              />
              {i === numbers.length - 1 && (
                <button
                  className="btn-ghost btn-ghost--sm"
                  style={{ padding: '0 10px' }}
                  onClick={() => setNumbers(n => [...n, ''])}
                >
                  <PlusIcon size={14} />
                </button>
              )}
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button className="btn-ghost btn-ghost--sm" style={{ flex: 1 }} onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            style={{ flex: 2, justifyContent: 'center', display: 'flex', alignItems: 'center', gap: 6 }}
            disabled={loading}
            onClick={submit}
          >
            {loading ? <LoaderIcon size={14} className="analysis-status__spinner" /> : <PlusIcon size={14} />}
            Add Contact
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Voiceprint Enroll Modal ───────────────────────────────────────────────────

function EnrollModal({ contact, onClose, onEnrolled }: {
  contact: Contact; onClose: () => void; onEnrolled: () => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ enrolled: boolean; message: string } | null>(null)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  async function enroll() {
    if (!file) return
    setLoading(true); setError('')
    const fd = new FormData()
    fd.append('file', file)
    try {
      const token = localStorage.getItem('vishwas:auth_token')
      const headers: HeadersInit = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }
      
      const r = await fetch(`${API_BASE}/contacts/${contact.contact_id}/voiceprint`, { 
        method: 'POST',
        headers,
        body: fd 
      })
      
      if (!r.ok) {
        if (r.status === 401) {
          throw new Error('Authentication required. Please refresh the page.')
        }
        throw new Error(`HTTP ${r.status}`)
      }
      
      const data = await r.json()
      setResult(data)
      if (data.enrolled) onEnrolled()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Enrollment failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Enroll Voiceprint</h3>
          <button className="analyse-file-remove" onClick={onClose}><XCircleIcon size={18} /></button>
        </div>

        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginBottom: 16 }}>
          Upload a 10–15 second audio clip of <strong style={{ color: 'var(--color-text)' }}>{contact.name}</strong> speaking clearly.
          Only the voice embedding will be stored — the audio is deleted immediately.
        </p>

        {!result && (
          <>
            <div
              className={`analyse-dropzone${file ? ' analyse-dropzone--has-file' : ''}`}
              style={{ minHeight: 100 }}
              onClick={() => inputRef.current?.click()}
            >
              <input ref={inputRef} type="file" accept="audio/*" style={{ display: 'none' }}
                onChange={e => setFile(e.target.files?.[0] || null)} />
              {file ? (
                <div className="analyse-dropzone__file">
                  <MicIcon size={20} style={{ color: 'var(--color-accent)' }} />
                  <div className="analyse-file-info">
                    <p className="analyse-file-name">{file.name}</p>
                  </div>
                </div>
              ) : (
                <div className="analyse-dropzone__empty" style={{ padding: '1rem 0' }}>
                  <MicIcon size={24} strokeWidth={1.5} />
                  <p className="analyse-dropzone__hint">Click to select audio clip</p>
                </div>
              )}
            </div>

            {error && <p style={{ color: 'var(--color-critical)', fontSize: '0.8rem', marginTop: 8 }}>{error}</p>}

            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <button className="btn-ghost btn-ghost--sm" style={{ flex: 1 }} onClick={onClose}>Cancel</button>
              <button
                className="btn-primary"
                style={{ flex: 2, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 6 }}
                disabled={!file || loading}
                onClick={enroll}
              >
                {loading ? <LoaderIcon size={14} className="analysis-status__spinner" /> : <UploadIcon size={14} />}
                Enroll Voiceprint
              </button>
            </div>
          </>
        )}

        {result && (
          <div className={`analysis-status ${result.enrolled ? 'analysis-status--completed' : 'analysis-status--error'}`}>
            {result.enrolled ? <CheckCircle2Icon size={16} /> : <AlertCircleIcon size={16} />}
            <div className="analysis-status__text">
              <strong>{result.enrolled ? 'Enrolled!' : 'Failed'}</strong>
              <span> {result.message}</span>
            </div>
          </div>
        )}
        {result && (
          <button className="btn-ghost btn-ghost--sm" style={{ marginTop: 12, width: '100%' }} onClick={onClose}>
            Close
          </button>
        )}
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function TrustGraphPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth()
  const [contacts, setContacts] = useState<Contact[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)
  const [enrollContact, setEnrollContact] = useState<Contact | null>(null)
  const [nodes, setNodes] = useState<GraphNode[]>([])

  async function fetchContacts() {
    setLoading(true); setError('')
    try {
      const token = localStorage.getItem('vishwas:auth_token')
      
      if (!token) {
        throw new Error('Not authenticated. Please wait for auto-login to complete.')
      }
      
      const headers: HeadersInit = {
        'Authorization': `Bearer ${token}`
      }
      
      const r = await fetch(`${API_BASE}/contacts`, { headers })
      if (!r.ok) {
        if (r.status === 401) {
          throw new Error('Authentication failed. Token may be expired. Please refresh the page.')
        }
        throw new Error(`HTTP ${r.status}`)
      }
      const data: Contact[] = await r.json()
      setContacts(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load contacts')
    } finally {
      setLoading(false)
    }
  }

  // Wait for authentication before fetching contacts
  useEffect(() => { 
    if (!authLoading && isAuthenticated) {
      fetchContacts()
    } else if (!authLoading && !isAuthenticated) {
      setError('Authentication required. Auto-login may have failed.')
      setLoading(false)
    }
  }, [authLoading, isAuthenticated])

  // Update graph nodes when contacts change
  useEffect(() => {
    setNodes(layoutNodes(contacts, 520, 380))
  }, [contacts])

  const selectedContact = contacts.find(c => c.contact_id === selected)
  const filtered = contacts.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    (c.relation || '').toLowerCase().includes(search.toLowerCase())
  )

  const enrolledCount = contacts.filter(c => c.voiceprint_enrolled).length
  const flaggedCount = contacts.filter(c => c.trust_level === 'low').length
  const suspiciousCount = contacts.filter(c => c.trust_level === 'medium').length

  return (
    <div className="page-content">
      {/* Header */}
      <div className="page-heading">
        <div className="page-heading__icon-wrap">
          <UsersIcon size={20} strokeWidth={1.75} />
        </div>
        <div style={{ flex: 1 }}>
          <h1 className="page-heading__title">Trust Graph</h1>
          <p className="page-heading__subtitle">
            Manage your trusted contacts and voice enrollments to power caller verification.
          </p>
        </div>
        <button
          className="btn-primary"
          style={{ display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}
          onClick={() => setShowAddModal(true)}
        >
          <PlusIcon size={15} />
          Add Contact
        </button>
      </div>

      {/* Stats row */}
      <div className="summary-cards" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <div className="summary-card">
          <div className="summary-card__label">Total Contacts</div>
          <div className="summary-card__value">{contacts.length}</div>
        </div>
        <div className="summary-card">
          <div className="summary-card__label">Voiceprints Enrolled</div>
          <div className="summary-card__value" style={{ color: 'var(--color-accent)' }}>{enrolledCount}</div>
        </div>
        <div className="summary-card">
          <div className="summary-card__label">Suspicious</div>
          <div className="summary-card__value" style={{ color: '#f59e0b' }}>{suspiciousCount}</div>
        </div>
        <div className="summary-card">
          <div className="summary-card__label">🚨 Flagged (Low Trust)</div>
          <div className="summary-card__value" style={{ color: flaggedCount > 0 ? 'var(--color-critical)' : 'var(--color-text-muted)' }}>{flaggedCount}</div>
        </div>
      </div>

      {/* Main grid: graph + list */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '1.25rem' }}>

        {/* ── Graph Canvas ─────────────────────────────────────── */}
        <div style={{
          background: 'var(--color-panel)',
          border: '1px solid var(--color-border)',
          borderRadius: 12,
          overflow: 'hidden',
          height: 380,
          position: 'relative',
        }}>
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-text-muted)' }}>
              <LoaderIcon size={24} className="analysis-status__spinner" />
            </div>
          ) : error ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 8, color: 'var(--color-critical)' }}>
              <AlertCircleIcon size={24} />
              <p style={{ fontSize: '0.875rem' }}>{error}</p>
              <button className="btn-ghost btn-ghost--sm" onClick={fetchContacts}>Retry</button>
            </div>
          ) : contacts.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 12, color: 'var(--color-text-muted)' }}>
              <UsersIcon size={32} strokeWidth={1} />
              <p style={{ fontSize: '0.9rem' }}>No contacts yet</p>
              <button className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 6 }} onClick={() => setShowAddModal(true)}>
                <PlusIcon size={14} />Add First Contact
              </button>
            </div>
          ) : (
            <TrustGraphCanvas
              nodes={nodes}
              selected={selected}
              onSelect={id => setSelected(id || null)}
            />
          )}

          {/* Legend */}
          {contacts.length > 0 && (
            <div style={{
              position: 'absolute', bottom: 12, left: 12,
              display: 'flex', gap: 12, background: 'rgba(17,24,39,0.8)',
              backdropFilter: 'blur(4px)', borderRadius: 8,
              padding: '6px 10px', fontSize: '0.75rem', color: 'var(--color-text-muted)',
            }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
                High Trust
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} />
                Suspicious
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ef4444', display: 'inline-block' }} />
                Flagged
              </span>
            </div>
          )}
        </div>

        {/* ── Contact Detail / List ─────────────────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>

          {/* Search + refresh */}
          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ flex: 1, position: 'relative' }}>
              <SearchIcon size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)' }} />
              <input
                className="modal-input"
                style={{ paddingLeft: 30, margin: 0 }}
                placeholder="Search contacts..."
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            <button className="btn-ghost btn-ghost--sm" style={{ padding: '0 10px' }} onClick={fetchContacts} aria-label="Refresh">
              <RefreshCwIcon size={14} />
            </button>
          </div>

          {/* Selected contact detail */}
          {selectedContact && (
            <div style={{
              background: 'var(--color-panel)', border: '1px solid var(--color-accent)',
              borderRadius: 10, padding: '1rem',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                <div>
                  <p style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{selectedContact.name}</p>
                  <p style={{ color: 'var(--color-text-muted)', fontSize: '0.8125rem' }}>{selectedContact.relation || 'Contact'}</p>
                </div>
                <span style={{
                  fontSize: '0.7rem', padding: '2px 8px', borderRadius: 99,
                  background: selectedContact.voiceprint_enrolled ? 'rgba(16,185,129,0.1)' : 'rgba(107,114,128,0.1)',
                  color: selectedContact.voiceprint_enrolled ? 'var(--color-accent)' : 'var(--color-text-muted)',
                  border: `1px solid ${selectedContact.voiceprint_enrolled ? 'rgba(16,185,129,0.3)' : 'rgba(107,114,128,0.2)'}`,
                }}>
                  {selectedContact.voiceprint_enrolled ? '✓ Voice enrolled' : 'No voiceprint'}
                </span>
              </div>

              {/* Trust level display */}
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '0.5rem 0.75rem', borderRadius: 8, marginBottom: 10,
                background: selectedContact.trust_level === 'low'
                  ? 'rgba(239,68,68,0.08)'
                  : selectedContact.trust_level === 'medium'
                  ? 'rgba(245,158,11,0.08)'
                  : 'rgba(16,185,129,0.06)',
                border: `1px solid ${trustColor(selectedContact.trust_level)}33`,
              }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 700, color: trustColor(selectedContact.trust_level) }}>
                  {selectedContact.trust_level === 'low' ? '🔴 FLAGGED — LOW TRUST'
                    : selectedContact.trust_level === 'medium' ? '🟡 SUSPICIOUS — MEDIUM TRUST'
                    : '🟢 TRUSTED — HIGH TRUST'}
                </span>
                {selectedContact.trust_flagged_at && (
                  <span style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>
                    Flagged {new Date(selectedContact.trust_flagged_at).toLocaleDateString()}
                  </span>
                )}
              </div>

              {selectedContact.saved_numbers.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 4 }}>Saved numbers</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {selectedContact.saved_numbers.map((n, i) => (
                      <span key={i} style={{
                        display: 'flex', alignItems: 'center', gap: 4,
                        fontSize: '0.75rem', background: 'rgba(255,255,255,0.05)',
                        border: '1px solid var(--color-border)', borderRadius: 4, padding: '2px 8px',
                      }}>
                        <PhoneIcon size={10} />{n}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedContact.voiceprint_enrolled_at && (
                <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <ClockIcon size={11} />
                  Enrolled {new Date(selectedContact.voiceprint_enrolled_at).toLocaleDateString()}
                </p>
              )}

              <button
                className={selectedContact.voiceprint_enrolled ? 'btn-ghost btn-ghost--sm' : 'btn-primary'}
                style={{ width: '100%', justifyContent: 'center', display: 'flex', alignItems: 'center', gap: 6 }}
                onClick={() => setEnrollContact(selectedContact)}
              >
                <MicIcon size={13} />
                {selectedContact.voiceprint_enrolled ? 'Re-enroll Voiceprint' : 'Enroll Voiceprint'}
              </button>
            </div>
          )}

          {/* Contact list */}
          <div style={{
            background: 'var(--color-panel)',
            border: '1px solid var(--color-border)',
            borderRadius: 10, overflow: 'hidden',
            maxHeight: selectedContact ? 200 : 300,
            overflowY: 'auto',
          }}>
            {loading ? (
              <div style={{ padding: 24, textAlign: 'center', color: 'var(--color-text-muted)' }}>
                <LoaderIcon size={18} className="analysis-status__spinner" />
              </div>
            ) : filtered.length === 0 ? (
              <p style={{ padding: 16, textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                {search ? 'No matches' : 'No contacts yet'}
              </p>
            ) : (
              filtered.map(c => {
                const Icon = relationIcon(c.relation)
                const tc = trustColor(c.trust_level)
                return (
                  <div
                    key={c.contact_id}
                    className={`contact-list-item${selected === c.contact_id ? ' contact-list-item--selected' : ''}`}
                    onClick={() => setSelected(c.contact_id === selected ? null : c.contact_id)}
                    style={{ borderLeft: `3px solid ${tc}` }}
                  >
                    <div className="contact-list-icon" style={{ color: tc }}>
                      <Icon size={14} />
                    </div>
                    <div className="contact-list-info">
                      <span className="contact-list-name">{c.name}</span>
                      <span className="contact-list-meta">{c.relation || 'Contact'}</span>
                    </div>
                    <span style={{
                      fontSize: '0.6rem', fontWeight: 700, padding: '1px 6px', borderRadius: 99,
                      background: `${tc}15`, color: tc, border: `1px solid ${tc}33`,
                      letterSpacing: '0.06em', flexShrink: 0,
                    }}>
                      {(c.trust_level || 'high').toUpperCase()}
                    </span>
                  </div>
                )
              })
            )}
          </div>
        </div>
      </div>

      {/* Modals */}
      {showAddModal && (
        <AddContactModal onClose={() => setShowAddModal(false)} onAdded={fetchContacts} />
      )}
      {enrollContact && (
        <EnrollModal
          contact={enrollContact}
          onClose={() => setEnrollContact(null)}
          onEnrolled={fetchContacts}
        />
      )}
    </div>
  )
}
