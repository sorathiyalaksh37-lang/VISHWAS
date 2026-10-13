import { InboxIcon } from 'lucide-react'

export function RecentAnalyses() {
  return (
    <section className="recent-analyses" aria-labelledby="recent-analyses-heading">
      <h2 id="recent-analyses-heading" className="section-title">
        Recent Analyses
      </h2>

      <div className="analyses-table-wrapper" role="region" aria-label="Recent analyses table">
        <table className="analyses-table" aria-label="Call analysis history">
          <thead>
            <tr>
              <th scope="col">Recording</th>
              <th scope="col">Date</th>
              <th scope="col">Status</th>
              <th scope="col">Risk Level</th>
            </tr>
          </thead>
          <tbody>
            {/* Empty state row */}
            <tr>
              <td colSpan={4}>
                <div className="analyses-empty">
                  <InboxIcon
                    size={36}
                    strokeWidth={1.25}
                    className="analyses-empty__icon"
                    aria-hidden="true"
                  />
                  <p className="analyses-empty__title">No analyses yet</p>
                  <p className="analyses-empty__body">
                    Upload a recording to get started.
                  </p>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  )
}
