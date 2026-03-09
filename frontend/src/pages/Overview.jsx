import { useMemo, memo } from 'react'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  ComposedChart, RadarChart, Radar, PolarGrid, PolarAngleAxis,
  XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer, CartesianGrid, ReferenceLine,
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
const CustomTooltip = ({ active, payload, label, dollar }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#fff', border: '1px solid var(--border2)', borderRadius: 8, padding: '10px 14px', fontSize: 12, boxShadow: '0 4px 20px rgba(37,99,235,0.12)' }}>
      <div style={{ fontWeight: 600, color: 'var(--text2)', marginBottom: 6 }}>{label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color, marginBottom: 2 }}>
          {p.name}: <strong>{dollar ? '$' + Number(p.value).toLocaleString() : p.value}</strong>
        </div>
      ))}
    </div>
  )
}

// ── System Info Table ─────────────────────────────────────────────────────────
const SystemTable = memo(({ m, summary }) => (
  <SectionCard title="System Summary">
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 32px' }}>
      {[
        ['Dataset',        'Walmart Weekly Sales — 6,435 rows, 45 stores'],
        ['Date Range',     'Feb 2010 – Oct 2012'],
        ['Train Period',   'First 12 months (2010)'],
        ['Test Period',    '21 months (2011–2012)'],
        ['Features',       '60+ engineered features'],
        ['Best Model',     m.model || 'XGB Stack'],
        ['Final Severity', summary?.final_severity?.toUpperCase() || '—'],
        ['Recommendation', summary?.recommendation || '—'],
      ].map(([k, v]) => (
        <div key={k} style={{ display: 'flex', gap: 12, padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
          <span style={{ color: 'var(--text3)', fontWeight: 500, minWidth: 140, fontSize: 12 }}>{k}</span>
          <span style={{ fontSize: 12, color: 'var(--text)', fontFamily: 'monospace' }}>{v}</span>
        </div>
      ))}
    </div>
  </SectionCard>
))

export default function Overview() {
  const { data: summary,  loading: ls, error: es } = useFetch('/api/summary',       { pollMs: 30000 })
  const { data: baseline, loading: lb, error: eb } = useFetch('/api/baseline',      { pollMs: 30000 })
  const { data: drift,    loading: ld, error: ed } = useFetch('/api/drift',         { pollMs: 15000 })
  const { data: monthly,  loading: lm }            = useFetch('/api/monthly-sales', { pollMs: 30000 })

  const loading = ls || lb || ld
  const error   = es || eb || ed
  const m       = baseline?.train || summary?.train_metrics || {}
  const severe  = useMemo(() => drift?.filter(d => d.severity === 'severe').length ?? 0, [drift])
  const months  = drift?.length ?? 0

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

  // Chart 3 — Area: actual vs predicted monthly sales
  const salesData = useMemo(() => (monthly || []).map(d => ({
    month:     d.month,
    Actual:    d.actual,
    Predicted: d.predicted,
  })), [monthly])

  // Chart 4 — Composed: MAE bar + error ratio line
  const maeData = useMemo(() => (monthly || []).map(d => ({
    month: d.month,
    MAE:   +(d.mae || 0).toFixed(0),
  })), [monthly])

  // Chart 5 — Radar: model metric profile
  const radarData = useMemo(() => [
    { metric: 'R²',    value: m.R2   ? +(m.R2   * 100).toFixed(1) : 0 },
    { metric: 'MAPE',  value: m.MAPE ? +(100 - m.MAPE).toFixed(1) : 0 },
    { metric: 'WMAPE', value: m.WMAPE? +(100 - m.WMAPE).toFixed(1): 0 },
    { metric: 'Acc',   value: m.R2   ? +(m.R2   * 100).toFixed(1) : 0 },
    { metric: 'Stab',  value: severe === 0 ? 100 : +(((months - severe) / (months || 1)) * 100).toFixed(1) },
  ], [m, severe, months])

  if (error) return <ErrorBox msg={error} />

  const skel = h => <div className="skel" style={{ height: h }} />

  return (
    <>
      <div className="page-header">
        <div className="page-title">Overview</div>
        <div className="page-sub">Phase 1 — Walmart weekly sales · 45 stores · Feb 2010 – Oct 2012</div>
      </div>

      {/* KPI Row */}
      <div className="kpi-grid">
        {loading
          ? Array.from({ length: 6 }).map((_, i) => <div key={i} className="kpi">{skel(60)}</div>)
          : <>
            <KPI label="R²"               value={fmt(m.R2)}                               delta="Training accuracy" />
            <KPI label="MAE"              value={fmtK(m.MAE)}                             delta="Mean abs error" />
            <KPI label="RMSE"             value={fmtK(m.RMSE)}                            delta="Root mean sq error" />
            <KPI label="MAPE"             value={m.MAPE ? m.MAPE.toFixed(2) + '%' : '—'} delta="Mean abs % error" />
            <KPI label="Months Monitored" value={months}                                  delta="Test period" />
            <KPI label="Severe Drift"     value={`${severe}/${months}`} color="var(--red)" delta="Months triggered" />
          </>
        }
      </div>

      {/* Row 1 — Error Trend + Stacked Features */}
      <div className="grid-2">
        <SectionCard title="MAE Trend — Baseline vs Current">
          {ld ? skel(H) :
          <ResponsiveContainer width="100%" height={H}>
            <LineChart data={errorData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v / 1000).toFixed(0) + 'K'} />
              <Tooltip content={<CustomTooltip dollar />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <ReferenceLine y={m.MAE} stroke="#94a3b8" strokeDasharray="4 2" label={{ value: 'Train MAE', fontSize: 10, fill: '#94a3b8' }} />
              <Line type="monotone" dataKey="Baseline" stroke="#10b981" strokeWidth={2} dot={false} strokeDasharray="5 3" />
              <Line type="monotone" dataKey="Current"  stroke="#ef4444" strokeWidth={2} dot={{ r: 3, fill: '#ef4444' }} />
            </LineChart>
          </ResponsiveContainer>}
        </SectionCard>

        <SectionCard title="Drifted Features per Month">
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

      {/* Row 2 — Area Sales + Composed MAE */}
      <div className="grid-2">
        <SectionCard title="Monthly Avg Sales — Actual vs Predicted">
          {lm ? skel(H) :
          <ResponsiveContainer width="100%" height={H}>
            <AreaChart data={salesData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              {GRAD}
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v / 1000).toFixed(0) + 'K'} />
              <Tooltip content={<CustomTooltip dollar />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="Actual"    stroke="#2563eb" fill="url(#gA)" strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="Predicted" stroke="#10b981" fill="url(#gP)" strokeWidth={2} dot={false} strokeDasharray="4 2" />
            </AreaChart>
          </ResponsiveContainer>}
        </SectionCard>

        <SectionCard title="Monthly MAE — Prediction Error">
          {lm ? skel(H) :
          <ResponsiveContainer width="100%" height={H}>
            <ComposedChart data={maeData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v / 1000).toFixed(0) + 'K'} />
              <Tooltip content={<CustomTooltip dollar />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="MAE" fill="#2563eb" opacity={0.8} radius={[3, 3, 0, 0]} />
              <Line type="monotone" dataKey="MAE" stroke="#f59e0b" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>}
        </SectionCard>
      </div>

      {/* Row 3 — Radar */}
      <SectionCard title="Model Quality Profile">
        {loading ? skel(H) :
        <ResponsiveContainer width="100%" height={H}>
          <RadarChart data={radarData} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
            <PolarGrid stroke="var(--border)" />
            <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11, fill: 'var(--text2)' }} />
            <Radar name="Score" dataKey="value" stroke="#2563eb" fill="#2563eb" fillOpacity={0.2} strokeWidth={2} />
            <Tooltip content={<CustomTooltip />} />
          </RadarChart>
        </ResponsiveContainer>}
      </SectionCard>

      <SystemTable m={m} summary={summary} />
    </>
  )
}
