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
          ['Dataset',        `Retail Sales — ${(insp.rows || 0).toLocaleString()} rows${insp.stores ? `, ${insp.stores} stores` : ''}, ${insp.products || '—'} products`],
          ['Date Range',     `${dr[0]?.slice(0, 10) || '—'} → ${dr[1]?.slice(0, 10) || '—'}`],
          ['Train Period',   split.train_start && split.train_end ? `${split.train_start} → ${split.train_end}` : (split.train_years ? split.train_years.join(', ') : '—')],
          ['Test Period',    split.test_start  && split.test_end  ? `${split.test_start} → ${split.test_end}`  : (split.test_year || '—')],
          ['Train / Test Rows', `${(split.train_rows || 0).toLocaleString()} train / ${(split.test_rows || 0).toLocaleString()} test`],
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
  const { data: summary,  loading: ls, error: es } = useFetch('/api/summary',         { pollMs: 15000 })
  const { data: baseline, loading: lb, error: eb } = useFetch('/api/baseline',        { pollMs: 15000 })
  const { data: drift,    loading: ld, error: ed } = useFetch('/api/drift',           { pollMs: 15000 })
  const { data: monthly,  loading: lm }            = useFetch('/api/monthly-sales',   { pollMs: 15000 })
  const { data: datasets }                         = useFetch('/api/datasets',        { pollMs: 15000 })
  const { data: healing }                          = useFetch('/api/healing-actions', { pollMs: 15000 })
  const { data: testMetrics }                      = useFetch('/api/test-metrics',    { pollMs: 15000 })

  const loading = (ls && !summary) || (lb && !baseline) || (ld && !drift) || (lm && !monthly)
  const error   = es || eb || ed
  const m       = baseline?.train || summary?.train_metrics || {}
  const severe  = useMemo(() => drift?.filter(d => d.severity === 'severe').length ?? 0, [drift])
  const months  = drift?.length ?? 0

  // Use real test metrics from all 130K rows (preferred) or fall back to monthly averages
  const live = useMemo(() => {
    if (testMetrics?.mae != null) return testMetrics
    if (!monthly?.length) return null
    const valid = monthly.filter(d => d.actual != null && d.predicted != null)
    if (!valid.length) return null
    const mae  = valid.reduce((s, d) => s + Math.abs(d.actual - d.predicted), 0) / valid.length
    const mape = valid.reduce((s, d) => s + (d.actual ? Math.abs(d.actual - d.predicted) / Math.abs(d.actual) * 100 : 0), 0) / valid.length
    return { mae: Math.round(mae), mape: Math.round(mape), accuracy: Math.round(100 - mape) }
  }, [testMetrics, monthly])

  // Check if we have actual comparison data (both actual and predicted)
  const hasComparisons = useMemo(() => {
    if (!monthly || !monthly.length) return false
    return monthly.some(d => d.actual != null && d.predicted != null)
  }, [monthly])

  // Chart 1 — MAE trend: baseline=1.44 flat, test=2.98–6.56 per month
  const errorData = useMemo(() => (drift || []).map(d => ({
    month:          d.month,
    'Test MAE':     d.error_trend?.current_error  ?? null,
    'Baseline MAE': d.error_trend?.baseline_error ?? null,
  })), [drift])

  // Chart 2 — Stacked bar: severe + mild drifted features
  const featureData = useMemo(() => (drift || []).map(d => ({
    month:  d.month,
    Severe: d.severe_features || 0,
    Mild:   d.mild_features   || 0,
  })), [drift])

  // Chart 3 — Area: monthly mean actual demand vs predicted (162–290 units)
  const salesData = useMemo(() => (monthly || []).map(d => ({
    month:       d.month,
    'Test Set':  d.actual    != null ? +d.actual.toFixed(2)    : null,
    'Predicted': d.predicted != null ? +d.predicted.toFixed(2) : null,
  })), [monthly])

  // Chart 4 — MAE bar per month (0.13–6.06 units)
  const maeData = useMemo(() => (monthly || []).map(d => ({
    month: d.month,
    MAE:   d.mae != null ? +d.mae.toFixed(2) : 0,
  })), [monthly])



  if (error) return <ErrorBox msg={error} />

  const skel = h => <div className="skel" style={{ height: h }} />

  return (
    <>
      <div className="page-header">
        <div className="page-title">Training Overview</div>
        <div className="page-sub">
          Phase 1 — Ultra-Fast Retail Demand Forecasting{datasets?.inspection?.stores ? ` · ${datasets.inspection.stores} stores` : ''} · {datasets?.inspection?.products ?? '—'} products · Train: {datasets?.split?.train_start?.slice(0,4) ?? '2019'}–{datasets?.split?.train_end?.slice(0,4) ?? '2022'} · Test: {datasets?.split?.test_year ?? '2023'}
        </div>
      </div>

      {/* Technical note */}
      <div className="alert alert-g" style={{ marginBottom: 16, fontSize: 11 }}>
        <strong>⚡ Ultra-Speed Mode:</strong> 5x faster training with 2-fold CV, 2 iterations, 30 RF trees, 
        optimized features (~20-30 vs 40-87+), XGBoost hist method, minimal validation splits
      </div>

      {/* KPI Row */}
      <div className="kpi-grid">
        {loading
          ? Array.from({ length: 6 }).map((_, i) => <div key={i} className="kpi">{skel(60)}</div>)
          : <>
            <KPI label="R² (Test 2023)"   value={live?.r2   != null ? live.r2.toFixed(1)   + '%'   : (m.R2   != null ? Math.round(m.R2)   + '%'   : '—')} delta={live?.n_rows ? `${live.n_rows.toLocaleString()} test rows` : 'Train baseline'} />
            <KPI label="MAE (Test 2023)"  value={live?.mae  != null ? live.mae.toFixed(2)  + ' u'   : (m.MAE  != null ? Math.round(m.MAE)  + ' u'   : '—')} delta={live?.n_rows ? 'Live · all test rows' : 'Baseline'} />
            <KPI label="RMSE (Test 2023)" value={live?.rmse != null ? live.rmse.toFixed(2) + ' u'   : (m.RMSE != null ? Math.round(m.RMSE) + ' u'   : '—')} delta={live?.n_rows ? 'Live · all test rows' : 'Baseline'} />
            <KPI label="MAPE (Test 2023)" value={live?.mape != null ? live.mape.toFixed(2) + '%'    : (m.MAPE != null ? Math.round(m.MAPE) + '%'    : '—')} delta={live?.n_rows ? 'Live · all test rows' : 'Baseline'} />
            <KPI label="Accuracy"         value={live?.accuracy != null ? live.accuracy.toFixed(1) + '%' : (m.Accuracy != null ? m.Accuracy + '%' : '—')} color="var(--green)" delta={live?.n_rows ? 'Test 2023' : 'Baseline'} />
            <KPI label="Severe Drift"     value={`${severe}/${months}`} color="var(--red)" delta="2023 test months" />
          </>
        }
      </div>

      {/* Row 1 — MAE Trend + Drifted Features */}
      <div className="grid-2">
        <SectionCard title="MAE — Baseline (Train 2019–2022) vs Test Set (2023)">
          {ld ? skel(H) :
          <ResponsiveContainer width="100%" height={H}>
            <LineChart data={errorData} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => v.toFixed(2)} domain={[0, 'auto']} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="Baseline MAE" stroke="#10b981" strokeWidth={2} dot={false} strokeDasharray="5 3" />
              <Line type="monotone" dataKey="Test MAE"     stroke="#ef4444" strokeWidth={2} dot={{ r: 3, fill: '#ef4444' }} />
            </LineChart>
          </ResponsiveContainer>}
        </SectionCard>

        <SectionCard title="Drifted Features per Test Month (2023)">
          {ld ? skel(H) :
          <ResponsiveContainer width="100%" height={H}>
            <BarChart data={featureData} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
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

      {/* Row 2 — Test Set Actual vs Predicted + Monthly MAE */}
      <div className="grid-2">
        <SectionCard title="Test Set vs Predicted — Mean Demand per Month (2023)">
          {lm ? skel(H) : !hasComparisons ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>
              <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.5 }}>📊</div>
              <div style={{ fontWeight: 500 }}>No test set data yet</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>Run python main.py to generate test results</div>
            </div>
          ) :
          <ResponsiveContainer width="100%" height={H}>
            <AreaChart data={salesData} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
              {GRAD}
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => v.toFixed(0)} domain={['auto', 'auto']} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="Test Set"  stroke="#2563eb" fill="url(#gA)" strokeWidth={2} dot={{ r: 3 }} />
              <Area type="monotone" dataKey="Predicted" stroke="#10b981" fill="url(#gP)" strokeWidth={2} dot={{ r: 3 }} strokeDasharray="4 2" />
            </AreaChart>
          </ResponsiveContainer>}
        </SectionCard>

        <SectionCard title="Monthly MAE — Test Set 2023 (units)">
          {lm ? skel(H) : !hasComparisons ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>
              <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.5 }}>📊</div>
              <div style={{ fontWeight: 500 }}>No test set error data yet</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>Run python main.py to evaluate on the test set</div>
            </div>
          ) :
          <ResponsiveContainer width="100%" height={H}>
            <BarChart data={maeData} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => v.toFixed(1)} domain={[0, 'auto']} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="MAE" fill="#2563eb" opacity={0.85} radius={[3, 3, 0, 0]} />
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
