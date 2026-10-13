import {
  ActivityIcon,
  CheckCircle2Icon,
  ClockIcon,
  XCircleIcon,
} from 'lucide-react'
import { RecentAnalyses } from '../components/overview/RecentAnalyses'
import { SummaryCard } from '../components/overview/SummaryCard'
import { UploadPanel } from '../components/overview/UploadPanel'

/**
 * Overview page.
 * Summary cards show null values (→ "—") until the backend is connected.
 * No fake data, mock records, or fabricated scores.
 */
export function Overview() {
  return (
    <div className="overview-page">
      {/* Page heading */}
      <div className="overview-page__heading">
        <h1 className="overview-page__title">Call Security Overview</h1>
        <p className="overview-page__subtitle">
          Monitor call analyses and identify potential fraud signals.
        </p>
      </div>

      {/* Summary cards — values are null until backend provides them */}
      <div className="summary-cards" role="list" aria-label="Analysis summary">
        <SummaryCard
          label="Total Analyses"
          value={null}
          icon={<ActivityIcon size={18} strokeWidth={1.75} />}
          variant="muted"
        />
        <SummaryCard
          label="Completed"
          value={null}
          icon={<CheckCircle2Icon size={18} strokeWidth={1.75} />}
          variant="accent"
        />
        <SummaryCard
          label="In Progress"
          value={null}
          icon={<ClockIcon size={18} strokeWidth={1.75} />}
          variant="warn"
        />
        <SummaryCard
          label="Failed"
          value={null}
          icon={<XCircleIcon size={18} strokeWidth={1.75} />}
          variant="critical"
        />
      </div>

      {/* Upload / analyse panel */}
      <UploadPanel />

      {/* Recent analyses table */}
      <RecentAnalyses />
    </div>
  )
}
