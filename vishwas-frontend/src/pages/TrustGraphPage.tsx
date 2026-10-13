import { useMemo, useState } from 'react'
import { CheckCircle2Icon, GitForkIcon, RotateCcwIcon, SearchIcon, ShieldAlertIcon, ShieldCheckIcon, XCircleIcon } from 'lucide-react'
import { TrustGraphCanvas, NODE_FILL, NODE_STROKE } from '../components/trustgraph/TrustGraphCanvas'
import {
  DEMO_CONTACTS,
  DEMO_EDGES,
  type ContactNode,
  type NodeCategory,
} from '../data/sampleData'

// ── Filter definitions ────────────────────────────────────────────────────────

type Filter = 'all' | 'trusted' | 'verified' | 'unverified'

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all',        label: 'All' },
  { id: 'trusted',    label: 'Trusted' },
  { id: 'verified',   label: 'Verified' },
  { id: 'unverified', label: 'Unverified' },
]

function categoryMatchesFilter(category: NodeCategory, filter: Filter): boolean {
  if (filter === 'all') return true
  if (filter === 'trusted')    return category === 'trusted'
  if (filter === 'verified')   return category === 'verified'
  if (filter === 'unverified') return category === 'unverified' || category === 'pending'
  return true
}

// ── Legend config ─────────────────────────────────────────────────────────────

const LEGEND_ITEMS: { category: NodeCategory; label: string }[] = [
  { category: 'self',       label: 'You (account owner)' },
  { category: 'trusted',    label: 'Trusted contact' },
  { category: 'verified',   label: 'Verified institution' },
  { category: 'unverified', label: 'Unverified contact' },
  { category: 'pending',    label: 'Pending verification' },
]

// ── Contact detail helpers ────────────────────────────────────────────────────

const TRUST_ICON: Partial<Record<string, React.ReactNode>> = {
  Trusted:              <ShieldCheckIcon  size={14} aria-hidden="true" />,
  Verified:             <CheckCircle2Icon size={14} aria-hidden="true" />,
  Unverified:           <XCircleIcon      size={14} aria-hidden="true" />,
  'Pending verification': <ShieldAlertIcon  size={14} aria-hidden="true" />,
}

const TRUST_COLOR: Partial<Record<string, string>> = {
  Trusted:              'var(--color-accent)',
  Verified:             '#8B5CF6',
  Unverified:           'var(--color-critical)',
  'Pending verification': 'var(--color-warn)',
}

// ── ContactDetailPanel ────────────────────────────────────────────────────────

function ContactDetailPanel({ contact }: { contact: ContactNode }) {
  const fill   = NODE_FILL[contact.category]
  const stroke = NODE_STROKE[contact.category]
  const trustColor = TRUST_COLOR[contact.verificationStatus] ?? '#9CA3AF'
  const trustIcon  = TRUST_ICON[contact.verificationStatus]

  return (
    <aside className="tg-detail" aria-label={`Details for ${contact.label}`}>
      <div className="tg-detail__header">
        {/* Avatar */}
        <div
          className="tg-detail__avatar"
          style={{ background: `${fill}22`, border: `1.5px solid ${stroke}`, color: stroke }}
          aria-hidden="true"
        >
          {contact.label.charAt(0)}
        </div>
        <div>
          <p className="tg-detail__name">{contact.label}</p>
          <p className="tg-detail__relationship">{contact.relationship}</p>
        </div>
      </div>

      <div className="tg-detail__row">
        <span className="tg-detail__row-label">Verification</span>
        <span className="tg-detail__row-value" style={{ color: trustColor }}>
          {trustIcon}
          {contact.verificationStatus}
        </span>
      </div>

      <div className="tg-detail__row">
        <span className="tg-detail__row-label">Trust level</span>
        <div className="tg-detail__trust-wrap">
          <div className="tg-detail__trust-bar">
            <div
              className="tg-detail__trust-fill"
              style={{ width: `${contact.trustLevel}%`, background: trustColor }}
            />
          </div>
          <span className="tg-detail__trust-pct">{contact.trustLevel}%</span>
        </div>
      </div>

      <p className="tg-detail__description">{contact.description}</p>

      <p className="tg-detail__disclaimer">
        ⚠️ All trust levels and contact details are illustrative demo data. They do not
        represent real users, contacts, or call records.
      </p>
    </aside>
  )
}

// ── TrustGraphPage ────────────────────────────────────────────────────────────

/**
 * Dedicated Trust Graph page.
 * All data is illustrative — see src/data/sampleData.ts.
 */
export function TrustGraphPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [search, setSearch]         = useState('')
  const [filter, setFilter]         = useState<Filter>('all')

  // Derive filtered node list (always keep 'self' visible)
  const filteredNodes = useMemo(() => {
    return DEMO_CONTACTS.filter((node) => {
      if (node.category === 'self') return true
      const matchesFilter = categoryMatchesFilter(node.category, filter)
      const matchesSearch = node.label.toLowerCase().includes(search.toLowerCase())
      return matchesFilter && matchesSearch
    })
  }, [search, filter])

  // Only show edges whose both endpoints are in the filtered set
  const filteredEdges = useMemo(() => {
    const visibleIds = new Set(filteredNodes.map(n => n.id))
    return DEMO_EDGES.filter(e => visibleIds.has(e.source) && visibleIds.has(e.target))
  }, [filteredNodes])

  const selectedContact = selectedId
    ? DEMO_CONTACTS.find(c => c.id === selectedId) ?? null
    : null

  function handleReset() {
    setSelectedId(null)
    setSearch('')
    setFilter('all')
  }

  const hasResults = filteredNodes.length > 1 // "self" is always present

  return (
    <div className="page-content tg-page">
      {/* ── Page header ─────────────────────────────────────────── */}
      <div className="tg-page__header">
        <div className="page-heading">
          <div className="page-heading__icon-wrap" aria-hidden="true">
            <GitForkIcon size={20} strokeWidth={1.75} />
          </div>
          <div>
            <h1 className="page-heading__title">Trust Graph</h1>
            <p className="page-heading__subtitle">
              Explore trusted relationships, verification status, and connections relevant to call security.
            </p>
          </div>
        </div>
        <span className="demo-badge demo-badge--lg">DEMO DATA</span>
      </div>

      {/* ── Toolbar: search + filters + reset ───────────────────── */}
      <div className="tg-toolbar">
        {/* Search */}
        <div className="history-search tg-search" role="search">
          <SearchIcon size={15} className="history-search__icon" aria-hidden="true" />
          <input
            id="tg-search-input"
            type="search"
            className="history-search__input"
            placeholder="Search contacts…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search contacts by name"
          />
        </div>

        {/* Filter pills */}
        <div className="history-filters" role="group" aria-label="Filter by trust status">
          {FILTERS.map(({ id, label }) => (
            <button
              key={id}
              className={`history-filter-btn${filter === id ? ' history-filter-btn--active' : ''}`}
              onClick={() => setFilter(id)}
              aria-pressed={filter === id}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Reset */}
        <button
          className="btn-ghost btn-ghost--sm tg-reset-btn"
          onClick={handleReset}
          aria-label="Reset view — clear search, filters, and selection"
        >
          <RotateCcwIcon size={13} aria-hidden="true" />
          Reset View
        </button>
      </div>

      {/* ── Graph + Detail panel ─────────────────────────────────── */}
      <div className="tg-layout">
        {/* Graph area */}
        <div className="tg-graph-area">
          {hasResults ? (
            <TrustGraphCanvas
              nodes={filteredNodes}
              edges={filteredEdges}
              selectedId={selectedId}
              onSelectNode={setSelectedId}
            />
          ) : (
            <div className="tg-empty">
              <SearchIcon size={32} className="tg-empty__icon" aria-hidden="true" />
              <p className="tg-empty__title">No contacts found</p>
              <p className="tg-empty__body">
                No contacts match your current search or filter. Try adjusting them, or{' '}
                <button className="tg-empty__reset" onClick={handleReset}>
                  reset the view
                </button>
                .
              </p>
            </div>
          )}

          {/* Legend */}
          <div className="tg-legend" aria-label="Graph legend">
            {LEGEND_ITEMS.map(({ category, label }) => (
              <span key={category} className="tg-legend__item">
                <span
                  className="tg-legend__dot"
                  style={{ background: NODE_FILL[category] }}
                  aria-hidden="true"
                />
                {label}
              </span>
            ))}
          </div>
        </div>

        {/* Detail panel */}
        <div className="tg-detail-col">
          {selectedContact ? (
            <ContactDetailPanel contact={selectedContact} />
          ) : (
            <div className="tg-detail tg-detail--empty" aria-live="polite">
              <GitForkIcon size={28} className="tg-detail--empty__icon" aria-hidden="true" />
              <p className="tg-detail--empty__title">Select a node</p>
              <p className="tg-detail--empty__body">
                Click any contact in the graph to view its details here.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
