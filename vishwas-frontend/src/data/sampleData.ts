/**
 * sampleData.ts
 *
 * Illustrative demo data for the Trust Graph and Overview pages.
 * ⚠️  NONE of this data represents real users, contacts, or call records.
 *
 * Replace this module with real API responses when the backend is connected.
 */

// ── Types ────────────────────────────────────────────────────────────────────

export type NodeCategory = 'self' | 'trusted' | 'verified' | 'unverified' | 'pending'

export interface ContactNode {
  id: string
  label: string
  category: NodeCategory
  relationship: string
  verificationStatus: string
  /** Illustrative trust level 0–100 */
  trustLevel: number
  description: string
}

export interface TrustEdge {
  source: string
  target: string
  label?: string
}

// ── Contact nodes ─────────────────────────────────────────────────────────────

export const DEMO_CONTACTS: ContactNode[] = [
  {
    id: 'self',
    label: 'You',
    category: 'self',
    relationship: 'Account owner',
    verificationStatus: 'Verified',
    trustLevel: 100,
    description: 'The central account — this is you within the VISHWAS system.',
  },
  {
    id: 'mother',
    label: 'Mother',
    category: 'trusted',
    relationship: 'Family',
    verificationStatus: 'Trusted',
    trustLevel: 97,
    description:
      'Close family member. Long-term established contact with consistent communication patterns.',
  },
  {
    id: 'brother',
    label: 'Brother',
    category: 'trusted',
    relationship: 'Family',
    verificationStatus: 'Trusted',
    trustLevel: 95,
    description:
      'Close family member. Regular contact; call patterns match established behaviour.',
  },
  {
    id: 'best-friend',
    label: 'Best Friend',
    category: 'trusted',
    relationship: 'Personal',
    verificationStatus: 'Trusted',
    trustLevel: 88,
    description:
      'Long-standing personal contact with high interaction frequency and stable identity signals.',
  },
  {
    id: 'bank-contact',
    label: 'Bank Contact',
    category: 'verified',
    relationship: 'Institution',
    verificationStatus: 'Verified',
    trustLevel: 82,
    description:
      'Institutional contact verified against a known financial organisation. Caller ID validated.',
  },
  {
    id: 'unknown',
    label: 'Unknown Number',
    category: 'unverified',
    relationship: 'Unknown',
    verificationStatus: 'Unverified',
    trustLevel: 10,
    description:
      'No prior interaction history. Caller identity cannot be established. Exercise caution.',
  },
  {
    id: 'new-contact',
    label: 'New Contact',
    category: 'pending',
    relationship: 'Unknown',
    verificationStatus: 'Pending verification',
    trustLevel: 40,
    description:
      'Recently added contact. Verification has been initiated but not yet completed.',
  },
]

// ── Edges ─────────────────────────────────────────────────────────────────────

export const DEMO_EDGES: TrustEdge[] = [
  { source: 'self', target: 'mother',       label: 'Family' },
  { source: 'self', target: 'brother',      label: 'Family' },
  { source: 'self', target: 'best-friend',  label: 'Personal' },
  { source: 'self', target: 'bank-contact', label: 'Verified' },
  { source: 'self', target: 'unknown',      label: 'Unverified' },
  { source: 'self', target: 'new-contact',  label: 'Pending' },
]

// ── Overview summary cards ────────────────────────────────────────────────────

export interface OverviewMetric {
  label: string
  value: string
}

export const DEMO_METRICS: OverviewMetric[] = [
  { label: 'Trusted Contacts',    value: '8'  },
  { label: 'Calls Analysed',      value: '24' },
  { label: 'High-Risk Calls',     value: '3'  },
  { label: 'Pending Verifications', value: '2' },
]

// ── Recent Activity ───────────────────────────────────────────────────────────

export type RiskLevel = 'low' | 'high' | 'medium'

export interface ActivityEntry {
  id: string
  contact: string
  trustStatus: string
  riskLevel: RiskLevel
  time: string
}

export const DEMO_ACTIVITY: ActivityEntry[] = [
  {
    id: 'act-1',
    contact: 'Family contact',
    trustStatus: 'Trusted',
    riskLevel: 'low',
    time: 'Today, 09:15',
  },
  {
    id: 'act-2',
    contact: 'Unknown number',
    trustStatus: 'Unverified',
    riskLevel: 'high',
    time: 'Today, 08:42',
  },
  {
    id: 'act-3',
    contact: 'Bank contact',
    trustStatus: 'Verification required',
    riskLevel: 'medium',
    time: 'Yesterday, 14:30',
  },
  {
    id: 'act-4',
    contact: 'Best Friend',
    trustStatus: 'Trusted',
    riskLevel: 'low',
    time: 'Yesterday, 11:00',
  },
]

// ── Trust Graph preview nodes (Overview page, smaller set) ────────────────────

export const PREVIEW_CONTACTS = [
  { id: 'self',         label: 'You',            category: 'self'       as NodeCategory },
  { id: 'family',       label: 'Family Member',  category: 'trusted'    as NodeCategory },
  { id: 'friend',       label: 'Best Friend',    category: 'trusted'    as NodeCategory },
  { id: 'bank',         label: 'Bank Contact',   category: 'verified'   as NodeCategory },
  { id: 'unknown-prev', label: 'Unknown Number', category: 'unverified' as NodeCategory },
]

export const PREVIEW_EDGES: TrustEdge[] = [
  { source: 'self', target: 'family'       },
  { source: 'self', target: 'friend'       },
  { source: 'self', target: 'bank'         },
  { source: 'self', target: 'unknown-prev' },
]
