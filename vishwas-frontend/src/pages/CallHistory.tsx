import { useState, useEffect } from 'react'
import { HistoryIcon, RefreshCwIcon, WifiOffIcon, LoaderIcon } from 'lucide-react'
import { apiClient, type CallListItem } from '../services/api'

type FilterOption = 'all' | 'completed' | 'failed'

/**
 * Call History page.
 *
 * Displays a list of all analysed call recordings from the backend.
 * Includes filters for status and risk level.
 */
export function CallHistory() {
  const [records, setRecords] = useState<CallListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterOption>('all')
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    loadCallHistory()
  }, [refreshKey])

  async function loadCallHistory() {
    setLoading(true)
    setError(null)

    try {
      const response = await apiClient.listCalls(1, 50)

      if (!response) {
        setError('Failed to load call history. Please check backend connection.')
        setRecords([])
        return
      }

      setRecords(response.calls)
    } catch (err) {
      console.error('Error loading call history:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
      setRecords([])
    } finally {
      setLoading(false)
    }
  }

  function handleRefresh() {
    setRefreshKey(prev => prev + 1)
  }

  const filteredRecords = records.filter(record => {
    switch (filter) {
      case 'completed':
        return record.status === 'completed'
      case 'failed':
        return record.status === 'failed'
      default:
        return true
    }
  })

  function getRiskBadgeClass(riskLevel?: string): string {
    switch (riskLevel) {
      case 'low':
        return 'history__badge history__badge--low'
      case 'medium':
        return 'history__badge history__badge--medium'
      case 'high':
      case 'critical':
        return 'history__badge history__badge--high'
      default:
        return 'history__badge'
    }
  }

  function getStatusBadgeClass(status: string): string {
    switch (status) {
      case 'completed':
        return 'history__badge history__badge--completed'
      case 'processing':
      case 'queued':
        return 'history__badge history__badge--processing'
      case 'failed':
        return 'history__badge history__badge--failed'
      default:
        return 'history__badge'
    }
  }

  function formatDate(dateString: string): string {
    try {
      const date = new Date(dateString)
      const now = new Date()
      const diffMs = now.getTime() - date.getTime()
      const diffMins = Math.floor(diffMs / 60000)
      const diffHours = Math.floor(diffMs / 3600000)
      const diffDays = Math.floor(diffMs / 86400000)

      if (diffMins < 1) return 'Just now'
      if (diffMins < 60) return `${diffMins} min ago`
      if (diffHours < 24) return `${diffHours}h ago`
      if (diffDays === 1) return 'Yesterday'
      if (diffDays < 7) return `${diffDays} days ago`

      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
      })
    } catch {
      return dateString
    }
  }

  return (
    <div className="page-content">
      {/* Page heading */}
      <div className="page-heading">
        <div className="page-heading__icon-wrap" aria-hidden="true">
          <HistoryIcon size={20} strokeWidth={1.75} />
        </div>
        <div>
          <h1 className="page-heading__title">Call History</h1>
          <p className="page-heading__subtitle">
            View and manage all analysed call recordings.
          </p>
        </div>
      </div>

      {/* Filters & actions */}
      <div className="history__toolbar">
        <div className="history__filters" role="group" aria-label="Filter history">
          <button
            className={filter === 'all' ? 'filter-btn filter-btn--active' : 'filter-btn'}
            onClick={() => setFilter('all')}
            aria-pressed={filter === 'all'}
          >
            All Calls ({records.length})
          </button>
          <button
            className={filter === 'completed' ? 'filter-btn filter-btn--active' : 'filter-btn'}
            onClick={() => setFilter('completed')}
            aria-pressed={filter === 'completed'}
          >
            Completed
          </button>
          <button
            className={filter === 'failed' ? 'filter-btn filter-btn--active' : 'filter-btn'}
            onClick={() => setFilter('failed')}
            aria-pressed={filter === 'failed'}
          >
            Failed
          </button>
        </div>

        <button
          className="btn-ghost btn-ghost--sm"
          onClick={handleRefresh}
          disabled={loading}
          aria-label="Refresh history"
        >
          <RefreshCwIcon size={16} aria-hidden="true" />
          Refresh
        </button>
      </div>

      {/* Content area */}
      {loading && (
        <div className="history__loading">
          <LoaderIcon size={24} className="analysis-status__spinner" aria-hidden="true" />
          <p>Loading call history...</p>
        </div>
      )}

      {error && (
        <div className="backend-indicator backend-indicator--error" role="alert">
          <WifiOffIcon size={13} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {!loading && !error && filteredRecords.length === 0 && (
        <div className="history__empty">
          <p>No calls found matching the selected filter.</p>
          {filter !== 'all' && (
            <button className="btn-ghost btn-ghost--sm" onClick={() => setFilter('all')}>
              Show all calls
            </button>
          )}
        </div>
      )}

      {!loading && !error && filteredRecords.length > 0 && (
        <div className="history__list">
          <table className="history-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Status</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredRecords.map(record => (
                <tr key={record.call_id}>
                  <td className="history-table__filename">
                    {record.original_filename}
                  </td>
                  <td>
                    <span className={getStatusBadgeClass(record.status)}>
                      {record.status}
                    </span>
                  </td>
                  <td className="history-table__date">
                    {formatDate(record.created_at)}
                  </td>
                  <td>
                    {record.status === 'completed' && (
                      <button className="btn-ghost btn-ghost--xs">
                        View Report
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

