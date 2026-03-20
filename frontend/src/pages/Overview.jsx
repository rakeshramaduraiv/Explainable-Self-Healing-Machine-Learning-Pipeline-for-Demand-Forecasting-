import { useMemo, memo } from 'react'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { useFetch } from '../api.js'
import { ErrorBox, KPI, SectionCard, fmt, fmtK, CHART_STYLE } from '../ui.jsx'

const GRAD = (
  <defs>
    <linearGradient id="gA" x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%"  stopColor="#2563eb" stopOpacity={0.18} />
      <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
    </linearGradient>
    <linearGradient id="gP" x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%"  stopColor="#10b981" stopOpacity={0.15} />
      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
    </linearGradient>
  </defs>
)

const H = 240

// ── Custom Tooltip ────────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label, unit }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#fff', border: '1px solid var(--border2)', borderRadius: 8, padding: '10px 14px', fontSize: 12, boxShadow: '0 4px 20px rgba(37,99,235,0.12)' }}>
      <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: 6 }}>{label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color, marginBottom: 2 }}>
          {p.name}: <strong>{unit ? unit + Number(p.value).toLocaleString() : p.value}</strong>
        </div>
      ))}
    </div>
  )
}

// ── System Info Table ─────────────────────────────────────────────────────────
const SystemTable = memo(({ m, summary, datasets }) => {
  const split = datasets?.split || {}
  const insp = datasets?.inspection || {}
  const dr = insp.date_range || ['—', '—']
  return (
    <SectionCard title="System Summary">
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 32px' }}>
        {[
          ['Dataset',        `Product Demand — ${(insp.rows || 0).toLocaleString()} rows${insp.stores ? `, ${insp.stores} stores` : ''}, ${insp.products || '—'} products`],
          ['Date Range',     `${dr[0]?.slice(0, 10) || '—'} → ${dr[1]?.slice(0, 10) || '—'}`],
          ['Train / Test',   `${(split.train_rows || 0).toLocaleString()} (baseline) / ${(split.test_rows || 0).toLocaleString()} (test set) rows`],
          ['Train / Test Year', split.train_year && split.test_year ? `${split.train_year} / ${split.test_year}` : '—'],
          ['Features',       `${summary?.feature_names?.length || '60'}+ engineered`],
          ['Best Model',     m.model || 'Ensemble'],
          ['Final Severity', summary?.final_severity?.toUpperCase() || '—'],
          ['Recommendation', summary?.recommendation || '—'],
        ].map(([k, v]) => (
          <div key={k} style={{ display: 'flex', gap: 12, padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <span style={{ color: 'var(--text3)', fontWeight: 600, minWidth: 140, fontSize: 12 }}>{k}</span>
            <span style={{ fontSize: 12, color: 'var(--text)', fontFamily: 'var(--mono)' }}>{v}</span>
          </div>
        ))}
      </div>
    </SectionCard>
  )
})

export default function Overview() {
  const { data: summary,  loading: ls, error: es } = useFetch('/api/summary',         { pollMs: 120000 })
  const { data: baseline, loading: lb, error: eb } = useFetch('/api/baseline',        { pollMs: 120000 })
  const { data: drift,    loading: ld, error: ed } = useFetch('/api/drift',           { pollMs: 60000 })
  const { data: monthly,  loading: lm }            = useFetch('/api/monthly-sales',   { pollMs: 60000 })
  const { data: datasets }                         = useFetch('/api/datasets',        { pollMs: 120000 })
  const { data: healing }                          = useFetch('/api/healing-actions', { pollMs: 120000 })

  const loading = (ls && !baseline && !summary) || (lb && !baseline) || (ld && !drift) || (lm && !monthly)
  const error   = es || eb || ed
  const m       = baseline?.train || summary?.train_metrics || {}
  const severe  = useMemo(() => drift?.filter(d => d.severity === 'severe').length ?? 0, [drift])
  const months  = drift?.length ?? 0

  // Real-time KPIs from test set data
  const live = useMemo(() => {
    if (!monthly?.length) return null
    const valid = monthly.filter(d => d.actual != null && d.predicted != null)
    if (!valid.length) return null
    const actuals = valid.map(d => d.actual)
    const preds   = valid.map(d => d.predicted)
    const mae     = valid.reduce((s, d) => s + Math.abs(d.actual - d.predicted), 0) / valid.length
    const rmse    = Math.sqrt(valid.reduce((s, d) => s + (d.actual - d.predicted) ** 2, 0) / valid.length)
    const mape    = valid.reduce((s, d) => s + (d.actual ? Math.abs(d.actual - d.predicted) / Math.abs(d.actual) * 100 : 0), 0) / valid.length
    const meanA   = actuals.reduce((s, v) => s + v, 0) / actuals.length
    const ssTot   = actuals.reduce((s, v) => s + (v - meanA) ** 2, 0)
    const ssRes   = actuals.reduce((s, v, i) => s + (v - preds[i]) ** 2, 0)
    const r2      = ssTot > 0 ? (1 - ssRes / ssTot) * 100 : 100
    return { r2: Math.round(r2), mae: Math.round(mae), rmse: Math.round(rmse), mape: Math.round(mape), accuracy: Math.round(100 - mape) }
  }, [monthly])

  // Check if we have actual comparison data (both actual and predicted)
  const hasComparisons = useMemo(() => {
    if (!monthly || !monthly.length) return false
    return monthly.some(d => d.actual != null && d.predicted != null)
  }, [monthly])

  // Chart 1 — Error trend line
  const errorData = useMemo(() => (drift || []).map(d => ({
    month:    d.month,
    Current:  +(d.error_trend?.current_error  || 0).toFixed(0),
    Baseline: +(d.error_trend?.baseline_error || 0).toFixed(0),
  })), [drift])

  // Chart 2 — Stacked bar: severe + mild features
  const featureData = useMemo(() => (drift || []).map(d => ({
    month:  d.month,
    Severe: d.severe_features || 0,
    Mild:   d.mild_features   || 0,
  })), [drift])

  // Chart 3 — Area: test set actual vs baseline predicted
  const salesData = useMemo(() => (monthly || []).map(d => ({
    month:        d.month,
    'Test Set':   d.actual,
    'Predicted':  d.predicted,
  })), [monthly])

  // Chart 4 — Composed: MAE bar + error ratio line
  const maeData = useMemo(() => (monthly || []).map(d => ({
    month: d.month,
    MAE:   +(d.mae || 0).toFixed(0),
  })), [monthly])



  if (error) return <ErrorBox msg={error} />

  const skel = h => <div className="skel" style={{ height: h }} />

  return (
    <>
      <div className="page-header">
        <div className="page-title">Training Overview</div>
        <div className="page-sub">
          Phase 1 — Product Demand Forecasting{datasets?.inspection?.stores ? ` · ${datasets.inspection.stores} stores` : ''} · {datasets?.inspection?.products ?? '—'} products · {datasets?.inspection?.date_range?.[0]?.slice(0,10) ?? ''} – {datasets?.inspection?.date_range?.[1]?.slice(0,10) ?? ''}
        </div>
      </div>

      {/* KPI Row */}
      <div className="kpi-grid">
        {loading
          ? Array.from({ length: 6 }).map((_, i) => <div key={i} className="kpi">{skel(60)}</div>)
          : <>
            <KPI label="R²"               value={(live?.r2 ?? (m.R2 != null ? Math.round(m.R2) : null)) != null ? (live?.r2 ?? Math.round(m.R2)) + '%' : '—'} delta={live ? 'Live · test set' : 'Baseline'} />
            <KPI label="MAE"              value={(live?.mae ?? (m.MAE != null ? Math.round(m.MAE) : null)) != null ? (live?.mae ?? Math.round(m.MAE)).toLocaleString() + ' units' : '—'} delta={live ? 'Live · test set' : 'Baseline'} />
            <KPI label="RMSE"             value={(live?.rmse ?? (m.RMSE != null ? Math.round(m.RMSE) : null)) != null ? (live?.rmse ?? Math.round(m.RMSE)).toLocaleString() + ' units' : '—'} delta={live ? 'Live · test set' : 'Baseline'} />
            <KPI label="MAPE"             value={(live?.mape ?? (m.MAPE != null ? Math.round(m.MAPE) : null)) != null ? (live?.mape ?? Math.round(m.MAPE)) + '%' : '—'} delta={live ? 'Live · test set' : 'Baseline'} />
            <KPI label="Accuracy"         value={(live?.accuracy ?? (m.Accuracy != null ? m.Accuracy : m.MAPE != null ? Math.round(100 - m.MAPE) : null)) != null ? (live?.accuracy ?? (m.Accuracy ?? Math.round(100 - m.MAPE))) + '%' : '—'} color="var(--green)" delta={live ? 'Live · test set' : 'Baseline'} />
            <KPI label="Severe Drift"     value={`${severe}/${months}`} color="var(--red)" delta="Test months triggered" />
          </>
        }
      </div>

      {/* Row 1 — Error Trend + Stacked Features */}
      <div className="grid-2">
        <SectionCard title="MAE Trend — Baseline vs Test Set">
          {ld ? skel(H) :
          <ResponsiveContainer width="100%" height={H}>
            <LineChart data={errorData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => (v / 1000).toFixed(0) + 'K'} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="Baseline" stroke="#10b981" strokeWidth={2} dot={false} strokeDasharray="5 3" />
              <Line type="monotone" dataKey="Current"  stroke="#ef4444" strokeWidth={2} dot={{ r: 3, fill: '#ef4444' }} name="Test Set" />
            </LineChart>
          </ResponsiveContainer>}
        </SectionCard>

        <SectionCard title="Drifted Features per Test Month">
          {ld ? skel(H) :
          <ResponsiveContainer width="100%" height={H}>
            <BarChart data={featureData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="Severe" fill="#ef4444" stackId="a" />
              <Bar dataKey="Mild"   fill="#f59e0b" stackId="a" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>}
        </SectionCard>
      </div>

      {/* Row 2 — Year 2 Backtest Results */}
      <div className="grid-2">
        <SectionCard title="Test Set vs Predicted (per month)">
          {lm ? skel(H) : !hasComparisons ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>
              <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.5 }}>📊</div>
              <div style={{ fontWeight: 500 }}>No test set data yet</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>Upload data and run the pipeline to evaluate on the test set</div>
            </div>
          ) :
          <ResponsiveContainer width="100%" height={H}>
            <AreaChart data={salesData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              {GRAD}
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => (v / 1000).toFixed(0) + 'K'} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="Test Set"  stroke="#2563eb" fill="url(#gA)" strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="Predicted" stroke="#10b981" fill="url(#gP)" strokeWidth={2} dot={false} strokeDasharray="4 2" />
            </AreaChart>
          </ResponsiveContainer>}
        </SectionCard>

        <SectionCard title="Test Set — Monthly MAE">
          {lm ? skel(H) : !hasComparisons ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>
              <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.5 }}>📊</div>
              <div style={{ fontWeight: 500 }}>No test set error data yet</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>Run the pipeline to evaluate on the test set</div>
            </div>
          ) :
          <ResponsiveContainer width="100%" height={H}>
            <BarChart data={maeData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => (v / 1000).toFixed(0) + 'K'} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="MAE" fill="#2563eb" opacity={0.8} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>}
        </SectionCard>
      </div>

      {/* Healing Actions Summary */}
      {healing && healing.total_actions > 0 && (
        <SectionCard title="Self-Healing Actions">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
            {[
              { label: 'Total Actions', value: healing.total_actions, color: 'var(--blue)' },
              { label: 'Fine-Tuned', value: healing.fine_tuned, color: 'var(--purple)' },
              { label: 'Rollbacks', value: healing.rollbacks || 0, color: 'var(--orange)' },
              { label: 'Avg Improvement', value: (healing.avg_improvement * 100).toFixed(1) + '%', color: 'var(--cyan)' },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ textAlign: 'center', padding: '14px 8px', background: 'var(--card2)', borderRadius: 10, border: '1px solid var(--border)' }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginBottom: 8 }}>{label}</div>
                <div style={{ fontSize: 22, fontWeight: 800, color, fontFamily: 'var(--mono)' }}>{value}</div>
              </div>
            ))}
          </div>
          {healing.recommendation && (
            <div style={{ marginTop: 14, padding: '10px 14px', background: 'var(--card3)', borderRadius: 8, fontSize: 12, color: 'var(--text2)', border: '1px solid var(--border)' }}>
              <strong style={{ color: 'var(--text3)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '1px' }}>Recommendation:</strong>
              <span style={{ marginLeft: 8 }}>{healing.recommendation}</span>
            </div>
          )}
        </SectionCard>
      )}

      <SystemTable m={m} summary={summary} datasets={datasets} />
    </>
  )
}
