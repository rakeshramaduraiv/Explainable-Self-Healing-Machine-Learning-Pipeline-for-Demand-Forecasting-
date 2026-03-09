import { useMemo, useState, memo } from 'react'
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend, ComposedChart, Bar,
  Brush, Cell, ReferenceLine
} from 'recharts'
import { useFetch } from '../api.js'
import { SkeletonCard, ErrorBox, KPI, SectionCard, fmt, fmtK, fmtD, CHART_STYLE } from '../ui.jsx'

const GRADIENT_DEFS = (
  <defs>
    <linearGradient id="gActual" x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.2} />
      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
    </linearGradient>
    <linearGradient id="gPred" x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%"  stopColor="#f59e0b" stopOpacity={0.15} />
      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
    </linearGradient>
  </defs>
)

const SystemTable = memo(({ m, summary }) => (
  <SectionCard title="System Summary">
    <table className="tbl">
      <tbody>
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
          <tr key={k}>
            <td style={{ color: 'var(--text3)', width: 180, fontWeight: 500 }}>{k}</td>
            <td className="mono">{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </SectionCard>
))

export default function Overview() {
  const { data: summary,  loading: ls, error: es } = useFetch('/api/summary',       { pollMs: 30000 })
  const { data: baseline, loading: lb, error: eb } = useFetch('/api/baseline',      { pollMs: 30000 })
  const { data: drift,    loading: ld, error: ed } = useFetch('/api/drift',         { pollMs: 15000 })
  const { data: monthly,  loading: lm }            = useFetch('/api/monthly-sales', { pollMs: 30000 })
  const [activeMonth, setActiveMonth] = useState(null)

  const loading = ls || lb || ld
  const error   = es || eb || ed
  const m       = baseline?.train || summary?.train_metrics || {}
  const severe  = useMemo(() => drift?.filter(d => d.severity === 'severe').length ?? 0, [drift])
  const months  = drift?.length ?? 0

  const errorData = useMemo(() => (drift || []).map(d => ({
    month:    d.month,
    Current:  d.error_trend?.current_error,
    Baseline: d.error_trend?.baseline_error,
    active:   d.month === activeMonth,
  })), [drift, activeMonth])

  const featureData = useMemo(() => (drift || []).map(d => ({
    month:  d.month,
    Severe: d.severe_features || 0,
    Mild:   d.mild_features   || 0,
  })), [drift])

  const monthlySalesData = useMemo(() => (monthly || []).map(d => ({
    month:     d.month,
    Actual:    d.actual,
    Predicted: d.predicted,
  })), [monthly])

  if (error) return <ErrorBox msg={error} />

  return (
    <>
      <div className="page-header">
        <div className="page-title">Overview</div>
        <div className="page-sub">Phase 1 — Walmart weekly sales · 45 stores · Feb 2010 – Oct 2012</div>
      </div>

      <div className="kpi-grid">
        {loading ? Array.from({length:6}).map((_,i)=><div key={i} className="kpi"><div className="skel" style={{height:60}}/></div>)
        : <>
          <KPI label="R²"               value={fmt(m.R2)}                               delta="Training score" />
          <KPI label="MAE"              value={fmtK(m.MAE)}                             delta="Mean abs error" />
          <KPI label="RMSE"             value={fmtK(m.RMSE)}                            delta="Root mean sq error" />
          <KPI label="MAPE"             value={m.MAPE ? m.MAPE.toFixed(2) + '%' : '—'} delta="Mean abs % error" />
          <KPI label="Months Monitored" value={months}                                  delta="Test period" />
          <KPI label="Severe Drift"     value={`${severe}/${months}`} color="var(--red)" delta="Months triggered" />
        </>}
      </div>

      {!loading && <div className="alert alert-r" style={{ marginBottom: 16 }}>
        All <strong>{months}</strong> monitored months show <strong>SEVERE drift</strong> — model trained on 2010 data vs 2011–2012 test. Phase 2 retraining required.
      </div>}

          <div className="grid-2">
            <SectionCard title="Error Trend — Baseline vs Current MAE">
              {ld ? <div className="skel" style={{height:230}}/> :
              <ResponsiveContainer width="100%" height={230} debounce={200}>
                <LineChart data={errorData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
                  onClick={e => e?.activeLabel && setActiveMonth(p => p === e.activeLabel ? null : e.activeLabel)}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v / 1000).toFixed(0) + 'K'} />
                  <Tooltip {...CHART_STYLE} formatter={v => ['$' + Number(v).toLocaleString()]} />
                  <Legend />
                  {activeMonth && <ReferenceLine x={activeMonth} stroke="var(--blue)" strokeDasharray="3 2" />}
                  <Line type="monotone" dataKey="Baseline" stroke="var(--green)" strokeWidth={2} dot={false} strokeDasharray="5 3" />
                  <Line type="monotone" dataKey="Current"  stroke="var(--red)"   strokeWidth={2}
                    dot={({ cx, cy, payload }) => payload.active
                      ? <circle key={cx} cx={cx} cy={cy} r={5} fill="var(--red)" stroke="#fff" strokeWidth={2} />
                      : <circle key={cx} cx={cx} cy={cy} r={3} fill="var(--red)" />} />
                </LineChart>
              </ResponsiveContainer>}
            </SectionCard>

            <SectionCard title="Drifted Features per Month">
              {ld ? <div className="skel" style={{height:230}}/> :
              <ResponsiveContainer width="100%" height={230} debounce={200}>
                <ComposedChart data={featureData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
                  onClick={e => e?.activeLabel && setActiveMonth(p => p === e.activeLabel ? null : e.activeLabel)}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip {...CHART_STYLE} />
                  <Legend />
                  <Bar dataKey="Severe" fill="var(--red)"    stackId="a" />
                  <Bar dataKey="Mild"   fill="var(--orange)" stackId="a" radius={[3, 3, 0, 0]} />
                </ComposedChart>
              </ResponsiveContainer>}
            </SectionCard>
          </div>

          {monthlySalesData.length > 0 && (
            <SectionCard title="Monthly Avg Sales — Actual vs Predicted (drag to zoom)">
              {lm ? <div className="skel" style={{height:270}}/> :
              <ResponsiveContainer width="100%" height={270} debounce={200}>
                <AreaChart data={monthlySalesData} margin={{ top: 4, right: 16, bottom: 24, left: 0 }}>
                  {GRADIENT_DEFS}
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v / 1000).toFixed(0) + 'K'} />
                  <Tooltip {...CHART_STYLE} formatter={v => ['$' + Number(v).toLocaleString()]} />
                  <Legend />
                  <Area type="monotone" dataKey="Actual"    stroke="var(--blue)"   fill="url(#gActual)" strokeWidth={2} dot={false} />
                  <Area type="monotone" dataKey="Predicted" stroke="var(--orange)" fill="url(#gPred)"   strokeWidth={2} dot={false} strokeDasharray="4 2" />
                  <Brush dataKey="month" height={22} stroke="var(--border2)" fill="var(--card2)" travellerWidth={6} />
                </AreaChart>
              </ResponsiveContainer>}
            </SectionCard>
          )}

          <SystemTable m={m} summary={summary} />
        </>
      )}
    </>
  )
}
