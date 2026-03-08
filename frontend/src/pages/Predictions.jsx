import { useState, useMemo, memo, useCallback, useEffect, useRef } from 'react'
import {
  ComposedChart, Area, Line, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend, Brush,
  AreaChart, BarChart, ReferenceLine, Cell
} from 'recharts'
import { useFetch, usePredictions } from '../api.js'
import { SkeletonCard, ErrorBox, KPI, SectionCard, fmtD, CHART_STYLE } from '../ui.jsx'

const QUALITY = errPct =>
  errPct < 3  ? { label: 'Excellent', color: 'var(--green)',  cls: 'b-green'  } :
  errPct < 8  ? { label: 'Good',      color: 'var(--blue)',   cls: 'b-blue'   } :
  errPct < 15 ? { label: 'Fair',      color: 'var(--orange)', cls: 'b-orange' } :
                { label: 'Poor',      color: 'var(--red)',    cls: 'b-red'    }

const MonthBtn = memo(({ m, selected, onClick }) => (
  <button className={`btn ${selected ? 'btn-primary' : 'btn-outline'}`}
    style={{ padding: '4px 12px', fontSize: 11 }} onClick={onClick}>{m}</button>
))

const PredTooltip = memo(({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  if (!d) return null
  const q = QUALITY(d.Error_Pct || 0)
  return (
    <div style={{ background: 'var(--card)', border: '1px solid var(--border2)', padding: '12px 16px', borderRadius: 10, fontSize: 12, minWidth: 210, boxShadow: '0 8px 24px rgba(0,0,0,0.4)' }}>
      <div style={{ fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>
        {d.Store ? `Store ${d.Store}` : `Row ${d.idx}`}
        {d.Date && <span style={{ color: 'var(--text3)', fontWeight: 400, marginLeft: 8, fontSize: 11 }}>{d.Date?.slice(0, 10)}</span>}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px' }}>
        <span style={{ color: 'var(--text3)' }}>Actual</span>
        <span style={{ color: 'var(--blue)', fontWeight: 600 }}>{fmtD(d.Actual)}</span>
        <span style={{ color: 'var(--text3)' }}>Predicted</span>
        <span style={{ color: 'var(--orange)', fontWeight: 600 }}>{fmtD(d.Predicted)}</span>
        {d.CI_Lower != null && <>
          <span style={{ color: 'var(--text3)' }}>95% CI</span>
          <span style={{ color: 'var(--text2)', fontSize: 11 }}>{fmtD(d.CI_Lower)} – {fmtD(d.CI_Upper)}</span>
        </>}
        <span style={{ color: 'var(--text3)' }}>Error</span>
        <span style={{ color: q.color, fontWeight: 600 }}>{fmtD(d.Abs_Error)} ({d.Error_Pct?.toFixed(1) ?? '—'}%)</span>
      </div>
      <div style={{ marginTop: 8 }}>
        <span className={`badge ${q.cls}`}>{q.label}</span>
      </div>
    </div>
  )
})

const PredRow = memo(({ r, i, highlight, onHover, onClick }) => {
  const actual  = r.Weekly_Sales ?? r.actual ?? 0
  const absErr  = r.Abs_Error ?? Math.abs(actual - r.Predicted)
  const errPct  = r.Error_Pct ?? (actual ? absErr / actual * 100 : 0)
  const q       = QUALITY(errPct)
  return (
    <tr onMouseEnter={() => onHover(i)} onMouseLeave={() => onHover(null)}
      onClick={() => onClick(r.Store)}
      style={{ cursor: 'pointer', background: highlight === i ? 'rgba(59,130,246,0.06)' : undefined }}>
      <td className="mono" style={{ color: 'var(--blue)', fontWeight: 600 }}>{r.Store ?? '—'}</td>
      <td className="mono" style={{ fontSize: 11 }}>{r.Date?.slice(0, 10) ?? '—'}</td>
      <td className="mono">{fmtD(actual)}</td>
      <td className="mono" style={{ color: 'var(--orange)' }}>{fmtD(r.Predicted)}</td>
      <td className="mono" style={{ color: 'var(--text3)', fontSize: 11 }}>{r.CI_Lower != null ? fmtD(r.CI_Lower) : '—'}</td>
      <td className="mono" style={{ color: 'var(--text3)', fontSize: 11 }}>{r.CI_Upper != null ? fmtD(r.CI_Upper) : '—'}</td>
      <td className="mono" style={{ color: errPct > 15 ? 'var(--red)' : 'var(--text2)' }}>{fmtD(absErr)}</td>
      <td className="mono">
        <span style={{ color: q.color, fontWeight: 600 }}>{errPct.toFixed(2)}%</span>
        <div className="progress-bar" style={{ width: 50, display: 'inline-block', marginLeft: 6, verticalAlign: 'middle' }}>
          <div className="progress-fill" style={{ width: `${Math.min(errPct * 4, 100)}%`, background: q.color }} />
        </div>
      </td>
      <td><span className={`badge ${q.cls}`} style={{ fontSize: 10 }}>{q.label}</span></td>
    </tr>
  )
})

export default function Predictions() {
  const { data: months, loading: lm, error: em } = useFetch('/api/processed-months', { pollMs: 15_000 })
  const { data: monthly }                         = useFetch('/api/monthly-sales',    { pollMs: 30_000 })
  const [selected, setSelected]   = useState(null)
  const [storeFilter, setStore]   = useState(null)
  const [highlight, setHighlight] = useState(null)
  const prevNewest = useRef(null)

  useEffect(() => {
    if (!months?.length) return
    const newest = months[months.length - 1]
    if (prevNewest.current && newest !== prevNewest.current && selected === prevNewest.current) {
      setSelected(newest); setStore(null)
    }
    prevNewest.current = newest
  }, [months])

  const activeMonth = selected || (months?.[months.length - 1] ?? null)
  const { data: preds, loading: lp, error: ep, updatedAt, fresh, reload } = usePredictions(activeMonth)

  const allRows = useMemo(() =>
    (preds || []).filter(r => (r.Weekly_Sales ?? r.actual) != null && r.Predicted != null),
  [preds])

  const stores = useMemo(() => [...new Set(allRows.map(r => r.Store).filter(Boolean))].sort((a, b) => a - b), [allRows])

  const rows = useMemo(() =>
    storeFilter != null ? allRows.filter(r => r.Store === storeFilter) : allRows,
  [allRows, storeFilter])

  const chartData = useMemo(() => rows.slice(0, 150).map((r, i) => ({
    idx:       i + 1,
    Store:     r.Store,
    Date:      r.Date,
    Actual:    r.Weekly_Sales ?? r.actual,
    Predicted: r.Predicted,
    CI_Lower:  r.CI_Lower,
    CI_Upper:  r.CI_Upper,
    Abs_Error: r.Abs_Error ?? Math.abs((r.Weekly_Sales ?? 0) - r.Predicted),
    Error_Pct: r.Error_Pct,
  })), [rows])

  const stats = useMemo(() => {
    if (!rows.length) return {}
    const actuals = rows.map(r => r.Weekly_Sales ?? 0)
    const ps      = rows.map(r => r.Predicted)
    const mae     = rows.reduce((s, r) => s + (r.Abs_Error ?? Math.abs((r.Weekly_Sales ?? 0) - r.Predicted)), 0) / rows.length
    const rmse    = Math.sqrt(rows.reduce((s, r) => { const e = (r.Weekly_Sales ?? 0) - r.Predicted; return s + e * e }, 0) / rows.length)
    const mape    = rows.reduce((s, r) => s + (r.Error_Pct ?? 0), 0) / rows.length
    const mean_a  = actuals.reduce((s, v) => s + v, 0) / actuals.length
    const ss_tot  = actuals.reduce((s, v) => s + (v - mean_a) ** 2, 0)
    const ss_res  = actuals.reduce((s, v, i) => s + (v - ps[i]) ** 2, 0)
    const r2      = ss_tot > 0 ? 1 - ss_res / ss_tot : null
    return { mae, rmse, mape, r2 }
  }, [rows])

  const onBarClick = useCallback(data => {
    if (!data?.activePayload?.[0]) return
    const s = data.activePayload[0].payload.Store
    setStore(prev => prev === s ? null : s)
  }, [])

  const onStoreClick = useCallback(s => setStore(prev => prev === s ? null : s), [])

  if (em) return <ErrorBox msg={em} />
  if (lm) return <SkeletonCard rows={4} />

  return (
    <>
      <div className="page-header">
        <div className="page-title">Predictions Explorer</div>
        <div className="page-sub">Actual vs predicted · confidence intervals · cross-filter by store</div>
      </div>

      {/* Live status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, fontSize: 11, color: 'var(--text3)', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 14px' }}>
        <span style={{
          width: 7, height: 7, borderRadius: '50%', display: 'inline-block',
          background: fresh ? 'var(--green)' : 'var(--text3)',
          boxShadow: fresh ? '0 0 8px var(--green)' : 'none',
          transition: 'all 0.4s', flexShrink: 0,
        }} />
        <span>{fresh ? '✓ Data refreshed' : updatedAt ? `Last updated ${updatedAt.toLocaleTimeString()}` : 'Loading…'}</span>
        <span style={{ marginLeft: 'auto' }}>
          Auto-polls every 12s ·{' '}
          <button className="btn btn-outline" style={{ padding: '2px 10px', fontSize: 10 }} onClick={reload}>↻ Refresh</button>
        </span>
      </div>

      {/* Month selector */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 20 }}>
        {(months || []).map(m => (
          <MonthBtn key={m} m={m} selected={activeMonth === m} onClick={() => { setSelected(m); setStore(null) }} />
        ))}
      </div>

      {lp ? <SkeletonCard rows={5} /> : ep ? <ErrorBox msg={ep} /> : (
        <>
          <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(6,1fr)' }}>
            <KPI label="Month"  value={activeMonth} />
            <KPI label="Rows"   value={rows.length} delta={storeFilter ? `Store ${storeFilter}` : 'All stores'} />
            <KPI label="MAE"    value={stats.mae  ? fmtD(stats.mae)  : '—'} color="var(--orange)" />
            <KPI label="RMSE"   value={stats.rmse ? fmtD(stats.rmse) : '—'} color="var(--red)" />
            <KPI label="MAPE"   value={stats.mape != null ? stats.mape.toFixed(2) + '%' : '—'}
              color={stats.mape != null && stats.mape < 5 ? 'var(--green)' : 'var(--orange)'} />
            <KPI label="R²"     value={stats.r2 != null ? stats.r2.toFixed(4) : '—'}
              color={stats.r2 != null && stats.r2 > 0.9 ? 'var(--green)' : 'var(--orange)'} />
          </div>

          {/* Store filter pills */}
          {stores.length > 0 && (
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 12px' }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginRight: 4 }}>Store</span>
              <button className={`btn ${storeFilter == null ? 'btn-primary' : 'btn-outline'}`}
                style={{ padding: '3px 10px', fontSize: 11 }} onClick={() => setStore(null)}>All</button>
              {stores.map(s => (
                <button key={s} className={`btn ${storeFilter === s ? 'btn-primary' : 'btn-outline'}`}
                  style={{ padding: '3px 10px', fontSize: 11 }}
                  onClick={() => setStore(prev => prev === s ? null : s)}>{s}</button>
              ))}
            </div>
          )}

          <SectionCard title="Actual vs Predicted — with 95% Confidence Band">
            <ResponsiveContainer width="100%" height={310}>
              <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 20, left: 0 }} onClick={onBarClick}>
                <defs>
                  <linearGradient id="gAct" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gCI" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#8b5cf6" stopOpacity={0.08} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="idx" tick={{ fontSize: 9 }} label={{ value: 'Row', position: 'insideBottom', offset: -12, fill: 'var(--text3)', fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v / 1000).toFixed(0) + 'K'} />
                <Tooltip content={<PredTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Area type="monotone" dataKey="CI_Upper" stroke="none" fill="url(#gCI)"  name="CI Upper" legendType="none" dot={false} />
                <Area type="monotone" dataKey="CI_Lower" stroke="none" fill="var(--bg)"  name="CI Lower" legendType="none" dot={false} />
                <Area type="monotone" dataKey="Actual"   stroke="var(--blue)"   fill="url(#gAct)" strokeWidth={2} dot={false} name="Actual" />
                <Line type="monotone" dataKey="Predicted" stroke="var(--orange)" strokeWidth={2} dot={false} strokeDasharray="4 2" name="Predicted" />
                <Brush dataKey="idx" height={22} stroke="var(--border2)" fill="var(--card2)" travellerWidth={6}
                  startIndex={0} endIndex={Math.min(49, chartData.length - 1)} />
              </ComposedChart>
            </ResponsiveContainer>
          </SectionCard>

          <div className="grid-2">
            <SectionCard title="Absolute Error per Row — click bar to filter store">
              <ResponsiveContainer width="100%" height={230}>
                <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }} onClick={onBarClick}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="idx" tick={{ fontSize: 9 }} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v / 1000).toFixed(0) + 'K'} />
                  <Tooltip content={<PredTooltip />} />
                  <Bar dataKey="Abs_Error" name="Abs Error" radius={[2, 2, 0, 0]}>
                    {chartData.map((d, i) => (
                      <Cell key={i}
                        fill={d.Store === storeFilter ? 'var(--blue)' :
                              d.Error_Pct > 15 ? 'var(--red)' :
                              d.Error_Pct > 8  ? 'var(--orange)' : 'var(--green)'}
                        fillOpacity={0.8}
                      />
                    ))}
                  </Bar>
                  {stats.mae && <ReferenceLine y={stats.mae} stroke="var(--orange)" strokeDasharray="4 2"
                    label={{ value: 'MAE', fill: 'var(--orange)', fontSize: 10, position: 'insideTopRight' }} />}
                </BarChart>
              </ResponsiveContainer>
            </SectionCard>

            <SectionCard title="Monthly Avg — Actual vs Predicted">
              <ResponsiveContainer width="100%" height={230}>
                <AreaChart data={monthly || []} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="gM1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#10b981" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gM2" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#f59e0b" stopOpacity={0.12} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" tick={{ fontSize: 9 }} />
                  <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v / 1000).toFixed(0) + 'K'} />
                  <Tooltip {...CHART_STYLE} formatter={v => ['$' + Number(v).toLocaleString()]} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area type="monotone" dataKey="actual"    stroke="var(--green)"  fill="url(#gM1)" strokeWidth={2} dot={false} name="Actual" />
                  <Area type="monotone" dataKey="predicted" stroke="var(--orange)" fill="url(#gM2)" strokeWidth={2} dot={false} name="Predicted" strokeDasharray="4 2" />
                  {activeMonth && <ReferenceLine x={activeMonth} stroke="var(--blue)" strokeDasharray="3 2"
                    label={{ value: 'Selected', fill: 'var(--blue)', fontSize: 9, position: 'insideTopRight' }} />}
                </AreaChart>
              </ResponsiveContainer>
            </SectionCard>
          </div>

          <SectionCard title={`Prediction Detail — ${activeMonth}${storeFilter ? ` · Store ${storeFilter}` : ''} (${Math.min(rows.length, 100)} rows)`}>
            <div style={{ overflowX: 'auto', maxHeight: 380, overflowY: 'auto' }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Store</th><th>Date</th><th>Actual</th><th>Predicted</th>
                    <th>CI Lower</th><th>CI Upper</th><th>Abs Error</th><th>Error %</th><th>Quality</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 100).map((r, i) => (
                    <PredRow key={i} r={r} i={i} highlight={highlight}
                      onHover={setHighlight} onClick={onStoreClick} />
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text3)', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <span style={{ color: 'var(--green)' }}>● Excellent &lt;3%</span>
              <span style={{ color: 'var(--blue)' }}>● Good &lt;8%</span>
              <span style={{ color: 'var(--orange)' }}>● Fair &lt;15%</span>
              <span style={{ color: 'var(--red)' }}>● Poor ≥15%</span>
              <span style={{ marginLeft: 'auto' }}>Click row to filter · Hover for details</span>
            </div>
          </SectionCard>
        </>
      )}
    </>
  )
}
