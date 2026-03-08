import { useFetch } from '../api.js'
import { Spinner, ErrorBox, KPI, SectionCard, SevBadge, fmtD } from '../ui.jsx'

export default function Datasets() {
  const { data, loading, error } = useFetch('/api/datasets')

  if (error)   return <ErrorBox msg={error} />
  if (loading) return <Spinner />

  const split   = data?.split || {}
  const insp    = data?.inspection || {}
  const batches = data?.batches || []
  const dr      = insp.date_range || ['—', '—']

  return (
    <>
      <div className="page-header">
        <div className="page-title">Datasets</div>
        <div className="page-sub">Reference dataset · uploaded batches · data management</div>
      </div>

      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
        <KPI label="Train Rows"  value={(split.train_rows || 0).toLocaleString()} />
        <KPI label="Test Rows"   value={(split.test_rows  || 0).toLocaleString()} />
        <KPI label="Cutoff Date" value={split.cutoff_date || '—'} />
        <KPI label="Stores"      value={insp.stores || 45} />
      </div>

      <SectionCard title="Reference Dataset — Training Split">
        <table className="tbl">
          <tbody>
            {[
              ['Source',      'Walmart Weekly Sales'],
              ['Total Records', (insp.rows || 6435).toLocaleString() + ' rows'],
              ['Date Range',  `${dr[0]?.slice(0,10)} → ${dr[1]?.slice(0,10)}`],
              ['Train Rows',  (split.train_rows || 0).toLocaleString()],
              ['Test Rows',   (split.test_rows  || 0).toLocaleString()],
              ['Cutoff',      split.cutoff_date || '—'],
              ['Missing Values', insp.missing_values ?? 0],
            ].map(([k, v]) => (
              <tr key={k}>
                <td style={{ color: 'var(--text3)', width: 160 }}>{k}</td>
                <td className="mono">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionCard>

      <SectionCard title="Monitored Batches">
        {batches.length === 0 ? (
          <div className="alert alert-b">No batch data. Run <code>python main.py</code> first.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead>
                <tr><th>Month</th><th>Records</th><th>Actual</th><th>Predicted</th><th>MAE</th><th>Error Ratio</th><th>Drift</th></tr>
              </thead>
              <tbody>
                {batches.map(b => (
                  <tr key={b.month}>
                    <td className="mono">{b.month}</td>
                    <td>{b.records ?? '—'}</td>
                    <td className="mono">{b.mean_actual != null ? fmtD(b.mean_actual) : '—'}</td>
                    <td className="mono">{b.mean_pred   != null ? fmtD(b.mean_pred)   : '—'}</td>
                    <td className="mono">{b.mae         != null ? fmtD(b.mae)         : '—'}</td>
                    <td className="mono">{b.error_ratio != null ? b.error_ratio.toFixed(2) + 'x' : '—'}</td>
                    <td><SevBadge severity={b.severity?.toLowerCase()} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </>
  )
}
