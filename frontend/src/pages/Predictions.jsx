import { useState, useMemo, memo, useCallback, useEffect, useRef } from 'react'
import {
  ComposedChart, Area, Line, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend, Brush,
  AreaChart, BarChart, ReferenceLine, Cell
} from 'recharts'
import { useFetch, usePredictions } from '../api.js'
import { SkeletonCard, ErrorBox, KPI, SectionCard, fmtD, CHART_STYLE } from '../ui.jsx'


const pName = (id, names) => names?.[id] || `Product ${id}`

const PALETTE = ['#3b82f6','#6366f1','#8b5cf6','#10b981','#f59e0b','#ef4444','#60a5fa','#34d399','#06b6d4','#a78bfa','#f472b6','#fb923c','#4ade80','#818cf8','#e879f9']

const QUALITY = errPct =>
  errPct < 3  ? { label: 'Excellent', color: 'var(--green)',  cls: 'b-green'  } :
  errPct < 8  ? { label: 'Good',      color: 'var(--blue)',   cls: 'b-blue'   } :
  errPct < 15 ? { label: 'Fair',      color: 'var(--orange)', cls: 'b-orange' } :
                { label: 'Poor',      color: 'var(--red)',    cls: 'b-red'    }

const MonthBtn = memo(({ m, selected, onClick }) => (
  <button className={`btn ${selected ? 'btn-primary' : 'btn-outline'}`}
    style={{ padding: '4px 12px', fontSize: 11 }} onClick={onClick}>{m}</button>
))

const PredTooltip = memo(({ active, payload, productNames }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  if (!d) return null
  const q = QUALITY(d.Error_Pct || 0)
  return (
    <div style={{ background: '#fff', border: '1px solid var(--border2)', padding: '12px 16px', borderRadius: 10, fontSize: 12, minWidth: 220, boxShadow: '0 4px 20px rgba(37,99,235,0.12)' }}>
      <div style={{ fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>
        {d.Product ? pName(d.Product, d._pnames) : `Row ${d.idx}`}
        {d.Date && <span style={{ color: 'var(--text3)', fontWeight: 400, marginLeft: 8, fontSize: 11 }}>{d.Date?.slice(0, 10)}</span>}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px' }}>
        <span style={{ color: 'var(--text3)' }}>Test Set</span>
        <span style={{ color: 'var(--blue)', fontWeight: 600 }}>{fmtD(d.Actual)} units</span>
        <span style={{ color: 'var(--text3)' }}>Predicted</span>
        <span style={{ color: 'var(--orange)', fontWeight: 600 }}>{fmtD(d.Predicted)} units</span>
        {d.CI_Lower != null && <>
          <span style={{ color: 'var(--text3)' }}>95% CI</span>
          <span style={{ color: 'var(--text2)', fontSize: 11 }}>{fmtD(d.CI_Lower)} – {fmtD(d.CI_Upper)}</span>
        </>}
        <span style={{ color: 'var(--text3)' }}>Error</span>
        <span style={{ color: q.color, fontWeight: 600 }}>{fmtD(d.Abs_Error)} ({d.Error_Pct?.toFixed(1) ?? '—'}%)</span>
      </div>
      <div style={{ marginTop: 8 }}><span className={`badge ${q.cls}`}>{q.label}</span></div>
    </div>
  )
})

const PredRow = memo(({ r, i, highlight, onHover, onClick }) => {
  const actual  = r.Demand ?? r.actual ?? 0
  const absErr  = r.Abs_Error ?? Math.abs(actual - r.Predicted)
  const errPct  = r.Error_Pct ?? (actual ? absErr / actual * 100 : 0)
  const q       = QUALITY(errPct)
  return (
    <tr onMouseEnter={() => onHover(i)} onMouseLeave={() => onHover(null)}
      onClick={() => onClick(r.Product)}
      style={{ cursor: 'pointer', background: highlight === i ? 'rgba(59,130,246,0.06)' : undefined }}>
      <td style={{ color: 'var(--blue)', fontWeight: 600 }}>{pName(r.Product, r._pnames)}</td>
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
  const { data: months, loading: lm, error: em } = useFetch('/api/processed-months', { pollMs: 30_000 })
  const { data: monthly }                         = useFetch('/api/monthly-sales',    { pollMs: 60_000 })
  const { data: productNames }                     = useFetch('/api/product-names')
  const [selected, setSelected]   = useState(null)
  const [prodFilter, setProd]     = useState(null)
  const [highlight, setHighlight] = useState(null)
  const prevNewest = useRef(null)

  useEffect(() => {
    if (!months?.length) return
    const newest = months[months.length - 1]
    if (prevNewest.current && newest !== prevNewest.current && selected === prevNewest.current) {
      setSelected(newest); setProd(null)
    }
    prevNewest.current = newest
  }, [months, selected])

  const activeMonth = selected || (months?.[months.length - 1] ?? null)
  const { data: preds, loading: lp, error: ep, updatedAt, fresh, reload } = usePredictions(activeMonth)

  const allRows = useMemo(() =>
    (preds || []).filter(r => (r.Demand ?? r.actual) != null && r.Predicted != null),
  [preds])

  const products = useMemo(() => [...new Set(allRows.map(r => r.Product).filter(Boolean))].sort((a, b) => a - b), [allRows])

  const rows = useMemo(() =>
    prodFilter != null ? allRows.filter(r => r.Product === prodFilter) : allRows,
  [allRows, prodFilter])

  const chartData = useMemo(() => rows.slice(0, 150).map((r, i) => ({
    idx:       i + 1,
    Product:   r.Product,
    _pnames:   productNames,
    Date:      r.Date,
    Actual:    r.Demand ?? r.actual,
    Predicted: r.Predicted,
    CI_Lower:  r.CI_Lower,
    CI_Upper:  r.CI_Upper,
    Abs_Error: r.Abs_Error ?? Math.abs((r.Demand ?? 0) - r.Predicted),
    Error_Pct: r.Error_Pct,
  })), [rows])

  const stats = useMemo(() => {
    if (!rows.length) return {}
    const actuals = rows.map(r => r.Demand ?? 0)
    const ps      = rows.map(r => r.Predicted)
    const mae     = rows.reduce((s, r) => s + (r.Abs_Error ?? Math.abs((r.Demand ?? 0) - r.Predicted)), 0) / rows.length
    const rmse    = Math.sqrt(rows.reduce((s, r) => { const e = (r.Demand ?? 0) - r.Predicted; return s + e * e }, 0) / rows.length)
    const mape    = rows.reduce((s, r) => s + (r.Error_Pct ?? 0), 0) / rows.length
    const mean_a  = actuals.reduce((s, v) => s + v, 0) / actuals.length
    const ss_tot  = actuals.reduce((s, v) => s + (v - mean_a) ** 2, 0)
    const ss_res  = actuals.reduce((s, v, i) => s + (v - ps[i]) ** 2, 0)
    const r2      = ss_tot > 0 ? 1 - ss_res / ss_tot : null
    return { mae, rmse, mape, r2 }
  }, [rows])

  // Per-product summary for this month
  const prodSummary = useMemo(() => {
    if (!allRows.length) return []
    const map = {}
    allRows.forEach(r => {
      const p = r.Product
      if (!p) return
      if (!map[p]) map[p] = { Product: p, name: pName(p, productNames), sumAct: 0, sumPred: 0, sumErr: 0, n: 0 }
      const act = r.Demand ?? 0
      map[p].sumAct += act
      map[p].sumPred += r.Predicted
      map[p].sumErr += r.Abs_Error ?? Math.abs(act - r.Predicted)
      map[p].n++
    })
    return Object.values(map).map(d => ({
      ...d,
      avgActual: Math.round(d.sumAct / d.n),
      avgPred: Math.round(d.sumPred / d.n),
      mae: Math.round(d.sumErr / d.n),
      mape: d.sumAct ? +(d.sumErr / d.sumAct * 100).toFixed(1) : 0,
    })).sort((a, b) => b.avgActual - a.avgActual)
  }, [allRows])

  const onBarClick = useCallback(data => {
    if (!data?.activePayload?.[0]) return
    const s = data.activePayload[0].payload.Product
    setProd(prev => prev === s ? null : s)
  }, [])

  const onProdClick = useCallback(s => setProd(prev => prev === s ? null : s), [])

  if (em) return <ErrorBox msg={em} />
  if (lm) return <SkeletonCard rows={4} />

  return (
    <>
      <div className="page-header">
        <div className="page-title">Predictions Explorer</div>
        <div className="page-sub">Test set vs predicted · confidence intervals · cross-filter by product</div>
      </div>

      {/* Live status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, fontSize: 11, color: 'var(--text3)', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 14px' }}>
        <span style={{
          width: 7, height: 7, borderRadius: '50%', display: 'inline-block',
          background: fresh ? 'var(--green)' : 'var(--text3)',
          boxShadow: fresh ? '0 0 8px var(--green)' : 'none',
          transition: 'all 0.4s', flexShrink: 0,
        }} />
        <span>{fresh ? 'Data refreshed' : updatedAt ? `Last updated ${updatedAt.toLocaleTimeString()}` : 'Loading…'}</span>
        <span style={{ marginLeft: 'auto' }}>
          Auto-refreshes on change ·{' '}
          <button className="btn btn-outline" style={{ padding: '2px 10px', fontSize: 10 }} onClick={reload}>Refresh</button>
        </span>
      </div>

      {/* Month selector */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 20 }}>
        {(months || []).map(m => (
          <MonthBtn key={m} m={m} selected={activeMonth === m} onClick={() => { setSelected(m); setProd(null) }} />
        ))}
      </div>

      {lp ? <SkeletonCard rows={5} /> : ep ? <ErrorBox msg={ep} /> : (
        <>
          <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(6,1fr)' }}>
            <KPI label="Month"  value={activeMonth} />
            <KPI label="Rows"   value={rows.length} delta={prodFilter ? pName(prodFilter, productNames) : 'All products'} />
            <KPI label="MAE"    value={stats.mae  ? Math.round(stats.mae) + ' units'  : '—'} color="var(--orange)" />
            <KPI label="RMSE"   value={stats.rmse ? Math.round(stats.rmse) + ' units' : '—'} color="var(--red)" />
            <KPI label="MAPE"   value={stats.mape != null ? stats.mape.toFixed(2) + '%' : '—'}
              color={stats.mape != null && stats.mape < 5 ? 'var(--green)' : 'var(--orange)'} />
            <KPI label="R²"     value={stats.r2 != null ? stats.r2.toFixed(4) : '—'}
              color={stats.r2 != null && stats.r2 > 0.9 ? 'var(--green)' : 'var(--orange)'} />
          </div>

          {/* Product filter pills */}
          {products.length > 0 && (
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 12px' }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginRight: 4 }}>Product</span>
              <button className={`btn ${prodFilter == null ? 'btn-primary' : 'btn-outline'}`}
                style={{ padding: '3px 10px', fontSize: 11 }} onClick={() => setProd(null)}>All</button>
              {products.map(p => (
                <button key={p} className={`btn ${prodFilter === p ? 'btn-primary' : 'btn-outline'}`}
                  style={{ padding: '3px 10px', fontSize: 11 }}
                  onClick={() => setProd(prev => prev === p ? null : p)}>{pName(p, productNames)}</button>
              ))}
            </div>
          )}

          <SectionCard title="Test Set vs Predicted — with 95% Confidence Band">
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
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip content={<PredTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Area type="monotone" dataKey="CI_Upper" stroke="none" fill="url(#gCI)"  name="CI Upper" legendType="none" dot={false} />
                <Area type="monotone" dataKey="CI_Lower" stroke="none" fill="var(--bg)"  name="CI Lower" legendType="none" dot={false} />
                <Area type="monotone" dataKey="Actual"   stroke="var(--blue)"   fill="url(#gAct)" strokeWidth={2} dot={false} name="Test Set" />
                <Line type="monotone" dataKey="Predicted" stroke="var(--orange)" strokeWidth={2} dot={false} strokeDasharray="4 2" name="Predicted" />
                <Brush dataKey="idx" height={22} stroke="var(--border2)" fill="var(--card2)" travellerWidth={6}
                  startIndex={0} endIndex={Math.min(chartData.length - 1, 149)} />
              </ComposedChart>
            </ResponsiveContainer>
          </SectionCard>

          <div className="grid-2">
            {/* Per-product avg demand vs predicted for this month */}
            <SectionCard title={`Product Demand Summary — ${activeMonth}`}>
              <ResponsiveContainer width="100%" height={Math.max(230, prodSummary.length * 22)}>
                <BarChart data={prodSummary} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 110 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 10 }} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={110} />
                  <Tooltip {...CHART_STYLE} formatter={v => [v + ' units']} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="avgActual" name="Test Set" fill="var(--blue)" radius={[0, 4, 4, 0]} barSize={8}
                    onClick={d => setProd(prev => prev === d.Product ? null : d.Product)} />
                  <Bar dataKey="avgPred" name="Predicted" fill="var(--green)" radius={[0, 4, 4, 0]} barSize={8} />
                </BarChart>
              </ResponsiveContainer>
            </SectionCard>

            <SectionCard title="Monthly Avg — Test Set vs Predicted">
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
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip {...CHART_STYLE} formatter={v => [Number(v).toLocaleString() + ' units']} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area type="monotone" dataKey="actual"    stroke="var(--green)"  fill="url(#gM1)" strokeWidth={2} dot={false} name="Test Set"  connectNulls={false} />
                  <Area type="monotone" dataKey="predicted" stroke="var(--orange)" fill="url(#gM2)" strokeWidth={2} dot={false} name="Predicted" strokeDasharray="4 2" connectNulls={false} />
                  {activeMonth && <ReferenceLine x={activeMonth} stroke="var(--blue)" strokeDasharray="3 2"
                    label={{ value: 'Selected', fill: 'var(--blue)', fontSize: 9, position: 'insideTopRight' }} />}
                </AreaChart>
              </ResponsiveContainer>
            </SectionCard>
          </div>

          {/* Error distribution */}
          <SectionCard title={`Absolute Error per Row — ${activeMonth}${prodFilter ? ' · ' + pName(prodFilter, productNames) : ''}`}>
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }} onClick={onBarClick}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="idx" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip content={<PredTooltip />} />
                <Bar dataKey="Abs_Error" name="Abs Error" radius={[2, 2, 0, 0]}>
                  {chartData.map((d, i) => (
                    <Cell key={i}
                      fill={d.Product === prodFilter ? 'var(--blue)' :
                            d.Error_Pct > 15 ? 'var(--red)' :
                            d.Error_Pct > 8  ? 'var(--orange)' : 'var(--green)'}
                      fillOpacity={0.8}
                    />
                  ))}
                </Bar>
                {stats.mae != null && <ReferenceLine y={stats.mae} stroke="var(--orange)" strokeDasharray="4 2"
                  label={{ value: 'MAE', fill: 'var(--orange)', fontSize: 10, position: 'insideTopRight' }} />}
              </BarChart>
            </ResponsiveContainer>
          </SectionCard>

          <SectionCard title={`Prediction Detail — ${activeMonth}${prodFilter ? ' · ' + pName(prodFilter, productNames) : ''} (${Math.min(rows.length, 100)} rows)`}>
            <div style={{ overflowX: 'auto', maxHeight: 380, overflowY: 'auto' }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Product</th><th>Date</th><th>Test Set</th><th>Predicted</th>
                    <th>CI Lower</th><th>CI Upper</th><th>Abs Error</th><th>Error %</th><th>Quality</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 100).map((r, i) => (
                    <PredRow key={i} r={{...r, _pnames: productNames}} i={i} highlight={highlight}
                      onHover={setHighlight} onClick={onProdClick} />
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text3)', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <span style={{ color: 'var(--green)' }}>● Excellent &lt;3%</span>
              <span style={{ color: 'var(--blue)' }}>● Good &lt;8%</span>
              <span style={{ color: 'var(--orange)' }}>● Fair &lt;15%</span>
              <span style={{ color: 'var(--red)' }}>● Poor ≥15%</span>
              <span style={{ marginLeft: 'auto' }}>Click row/bar to filter by product</span>
            </div>
          </SectionCard>
        </>
      )}
    </>
  )
}
