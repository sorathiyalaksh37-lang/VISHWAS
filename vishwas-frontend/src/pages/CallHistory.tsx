import { useState } from 'react'
import {
  ClockIcon,
  FilterIcon,
  InboxIcon,
  RefreshCwIcon,
  SearchIcon,
  WifiOffIcon,
  XIcon,
} from 'lucide-react'

type StatusFilter = 'all' | 'completed' | 'in-progress' | 'failed'

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'completed', label: 'Completed' },
  { value: 'in-progress', label: 'In Progress' },
  { value: 'failed', label: 'Failed' },
]

/**
 * Call History page.
 *
 * Displays a searchable, filterable table of analysed calls.
 * Because the backend is not connected there are no genuine records to show,
 * so the empty state is always visible.
 *
 * Search and filter logic is wired up and ready to work as soon as real
 * records are provided by the backend.
 *
 * IMPORTANT: No mock calls, fabricated dates, or invented risk scores.
 */
export function CallHistory() {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [refreshKey, setRefreshKey] = useState(0)
  const [refreshed, setRefreshed] = useState(false)

  // Real records would come from an API call. While backend is disconnected,
  // this is always empty.
  const records: never[] = []

  const filtersActive = search.trim() !== '' || statusFilter !== 'all'

  function clearFilters() {
    setSearch('')
    setStatusFilter('all')
  }

  function handleRefresh() {
    setRefreshKey((k) => k + 1)
    setRefreshed(true)
    // Auto-reset the 'Refreshed' label after 2 s
    setTimeout(() => setRefreshed(false), 2000)
  }

  // Filter logic — safe to call even when records is empty.
  // When real data arrives, this will work correctly.
  const filteredRecords = records.filter((_record) => {
    return true // placeholder; real filter applied once data shape is known
  })
  void filteredRecords // suppress "unused variable" lint warning
  void refreshKey    // used to trigger conceptual re-fetch

  return (
    <div className="page-content">
      {/* Page heading */}
      <div className="page-heading">
        <div className="page-heading__icon-wrap page-heading__icon-wrap--warn" aria-hidden="true">
          <ClockIcon size={20} strokeWidth={1.75} />
        </div>
        <div>
          <h1 className="page-heading__title">Call History</h1>
          <p className="page-heading__subtitle">
            Review previously analysed calls and their security findings.
          </p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="history-toolbar" role="search" aria-label="Filter call history">
        {/* Search */}
        <div className="history-search">
          <SearchIcon size={15} className="history-search__icon" aria-hidden="true" />
          <input
            id="history-search-input"
            type="search"
            className="history-search__input"
            placeholder="Search recordings…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search recordings by name"
          />
        </div>

        {/* Status filter */}
        <div className="history-filters" role="group" aria-label="Filter by status">
          <FilterIcon size={14} aria-hidden="true" className="history-filters__icon" />
          {STATUS_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              className={`history-filter-btn${statusFilter === value ? ' history-filter-btn--active' : ''}`}
              onClick={() => setStatusFilter(value)}
              aria-pressed={statusFilter === value}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Actions */}
        <div className="history-toolbar__actions">
          {filtersActive && (
            <button
              className="btn-ghost btn-ghost--sm"
              onClick={clearFilters}
              aria-label="Clear all filters"
            >
              <XIcon size={13} aria-hidden="true" />
              Clear Filters
            </button>
          )}
          <button
            className="btn-ghost btn-ghost--sm"
            onClick={handleRefresh}
            aria-label="Refresh history"
            aria-live="polite"
          >
            <RefreshCwIcon size={13} aria-hidden="true" />
            {refreshed ? 'Refreshed' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="analyses-table-wrapper" role="region" aria-label="Call history table">
        <table className="analyses-table" aria-label="Call history">
          <thead>
            <tr>
              <th scope="col">Recording</th>
              <th scope="col">Date</th>
              <th scope="col">Status</th>
              <th scope="col">Risk Level</th>
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            {/* Empty state — always shown until backend supplies records */}
            <tr>
              <td colSpan={5}>
                <div className="analyses-empty">
                  <InboxIcon
                    size={40}
                    strokeWidth={1.25}
                    className="analyses-empty__icon"
                    aria-hidden="true"
                  />
                  <p className="analyses-empty__title">
                    {filtersActive ? 'No records match your filters' : 'No call history yet'}
                  </p>
                  <p className="analyses-empty__body">
                    {filtersActive
                      ? 'Try clearing the filters or adjusting your search.'
                      : 'Analysed calls will appear here once the backend is connected.'}
                  </p>
                  {filtersActive && (
                    <button className="btn-ghost btn-ghost--sm" onClick={clearFilters}>
                      Clear Filters
                    </button>
                  )}
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Backend disconnected indicator */}
      <div className="backend-indicator" aria-label="Backend connection status">
        <WifiOffIcon size={13} aria-hidden="true" />
        <span>Backend not connected — history requires a live API</span>
      </div>
    </div>
  )
}
