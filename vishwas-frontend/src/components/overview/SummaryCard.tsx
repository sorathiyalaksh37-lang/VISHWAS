import type { ReactNode } from 'react'

export interface SummaryCardProps {
  label: string
  /** Pass `null` when value is not yet available from backend */
  value: string | null
  icon: ReactNode
  /** Optional colour modifier: 'accent' | 'warn' | 'critical' | 'muted' */
  variant?: 'accent' | 'warn' | 'critical' | 'muted'
}

export function SummaryCard({ label, value, icon, variant = 'muted' }: SummaryCardProps) {
  return (
    <div className={`summary-card summary-card--${variant}`} role="status" aria-label={`${label}: ${value ?? 'not available'}`}>
      <div className="summary-card__icon" aria-hidden="true">
        {icon}
      </div>
      <div className="summary-card__body">
        <span className="summary-card__value">{value ?? '—'}</span>
        <span className="summary-card__label">{label}</span>
      </div>
    </div>
  )
}
