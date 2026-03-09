import { memo } from 'react'
import { useFetch } from '../api.js'
import { Spinner, ErrorBox, KPI, SectionCard, SevBadge, fmtD, EmptyState } from '../ui.jsx'

const BatchRow = memo(({ b }) => (
  <tr>
    <td className="mono" style={{ fontWeight: 600 }}>{b.month}</td>
    <td style={{ color: 'var(--text2)' }}>{b.records ?? '—'}</td>
    <td className="mono">{b.mean_actual != null ? fmtD(b.mean_actual) : '—'}</td>
    <td className="mono">{b.mean_pred   != null ? fmtD(b.mean_pred)   : '—'}</td>
    <td className="mono" style={{ color: 'var(--orange)' }}>{b.mae != null ? fmtD(b.mae) : '—'}</td>
    <td className="mono">{b.error_ratio != null ? b.error_ratio.toFixed(2) + 'x' : '—'}</td>
    <td><SevBadge severity={b.severity?.toLowerCase()} /></td>
  </tr>
))

export default function Datasets() {
  const { data, loading, error, reload } = useFetch('/api/datasets')

  if (error)   return <ErrorBox msg={error} onRetry={reload} />
  if (loading) return <Spinner />

  const split   = data?.split || {}
  const insp    = data?.inspection || {}
  const batches = data?.batches || []
  const dr      = insp.date_range || ['—', '—']

  const sevCounts = batches.reduce((acc, b) => {
    const s = b.severity?.toLowerCase() || 'none'
    acc[s] = (acc[s] || 0) + 1
    return acc
  }, {})

  return (
    <>
      <div className="page-header">
        <div className="page-title">Datasets</div>
        <div className="page-sub">Reference dataset · uploaded batches · data management</div>
      </div>

      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(5,1fr)' }}>
        <KPI label="Train Rows"    value={(split.train_rows || 0).toLocaleString()} />
        <KPI label="Test Rows"     value={(split.test_rows  || 0).toLocaleString()} />
        <KPI label="Cutoff Date"   value={split.cutoff_date || '—'} />
        <KPI label="Stores"        value={insp.stores || 45} />
        <KPI label="Batches"       value={batches.length} delta={`${sevCounts.severe || 0} severe`} color={sevCounts.severe ? 'var(--red)' : undefined} />
      </div>

      <div className="grid-2">
        <SectionCard title="Reference Dataset — Training Split">
          <table className="tbl">
            <tbody>
              {[
                ['Source',          'Walmart Weekly Sales'],
                ['Total Records',   (insp.rows || 6435).toLocaleString() + ' rows'],
                ['Date Range',      `${dr[0]?.slice(0, 10)} → ${dr[1]?.slice(0, 10)}`],
                ['Train Rows',      (split.train_rows || 0).toLocaleString()],
                ['Test Rows',       (split.test_rows  || 0).toLocaleString()],
                ['Cutoff',          split.cutoff_date || '—'],
                ['Missing Values',  insp.missing_values ?? 0],
              ].map(([k, v]) => (
                <tr key={k}>
                  <td style={{ color: 'var(--text3)', width: 160, fontWeight: 500 }}>{k}</td>
                  <td className="mono">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>

        <SectionCard title="Drift Severity Summary">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '4px 0' }}>
            {[
              { label: 'Severe Batches', count: sevCounts.severe || 0, color: 'var(--red)',    bg: 'rgba(239,68,68,0.08)' },
              { label: 'Mild Batches',   count: sevCounts.mild   || 0, color: 'var(--orange)', bg: 'rgba(245,158,11,0.08)' },
              { label: 'No Drift',       count: sevCounts.none   || 0, color: 'var(--green)',  bg: 'rgba(16,185,129,0.08)' },
            ].map(({ label, count, color, bg }) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: bg, borderRadius: 8, padding: '10px 14px' }}>
                <span style={{ fontSize: 13, color: 'var(--text2)', fontWeight: 500 }}>{label}</span>
                <span style={{ fontSize: 20, fontWeight: 800, color, fontFamily: 'var(--mono)' }}>{count}</span>
              </div>
            ))}
            <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>
              Total: {batches.length} monitored batches
            </div>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="Monitored Batches">
        {batches.length === 0 ? (
          <EmptyState title="No batch data" sub="Run python main.py first to generate batch predictions." />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead>
                <tr><th>Month</th><th>Records</th><th>Actual</th><th>Predicted</th><th>MAE</th><th>Error Ratio</th><th>Drift</th></tr>
              </thead>
              <tbody>
                {batches.map(b => <BatchRow key={b.month} b={b} />)}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </>
  )
}
