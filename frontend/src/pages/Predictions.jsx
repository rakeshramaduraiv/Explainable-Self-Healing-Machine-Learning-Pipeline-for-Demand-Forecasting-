import { useState, useMemo, memo, useCallback, useEffect, useRef } from 'react'
import {
  ComposedChart, Area, Line, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend, Brush,
  AreaChart, BarChart, ReferenceLine, Cell
} from 'recharts'
import { useFetch, usePredictions } from '../api.js'
import { SkeletonCard, ErrorBox, KPI, SectionCard, fmtD, CHART_STYLE } from '../ui.jsx'

const MONTHS_BTN = memo(({ months, selected, onChange }) => (
  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 20 }}>
    {months.map(m => (
      <button key={m}
        className={`btn ${selected === m ? 'btn-primary' : 'btn-outline'}`}
        style={{ padding: '4px 11px', fontSize: 11 }}
        onClick={() => onChange(m)}>{m}
      </button>
    ))}
  </div>
))

// Custom tooltip with CI info
const PredTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  if (!d) return null
  return (
    <div style={{ background:'var(--card)', border:'1px solid var(--border)', padding:'10px 14px', borderRadius:8, fontSize:12, minWidth:200 }}>
      <div style={{ fontWeight:700, color:'var(--text)', marginBottom:6 }}>
        {d.Store ? `Store ${d.Store}` : `Row ${label}`}
        {d.Date ? <span style={{ color:'var(--text3)', fontWeight:400, marginLeft:8 }}>{d.Date?.slice(0,10)}</span> : null}
      </div>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'3px 16px' }}>
        <span style={{ color:'var(--text3)' }}>Actual</span>
        <span style={{ color:'var(--blue)', fontWeight:600 }}>{fmtD(d.Actual ?? d.Weekly_Sales)}</span>
        <span style={{ color:'var(--text3)' }}>Predicted</span>
        <span style={{ color:'var(--orange)', fontWeight:600 }}>{fmtD(d.Predicted)}</span>
        {d.CI_Lower != null && <>
          <span style={{ color:'var(--text3)' }}>95% CI</span>
          <span style={{ color:'var(--text2)' }}>{fmtD(d.CI_Lower)} – {fmtD(d.CI_Upper)}</span>
        </>}
        <span style={{ color:'var(--text3)' }}>Abs Error</span>
        <span style={{ color: d.Error_Pct > 10 ? 'var(--red)' : 'var(--green)', fontWeight:600 }}>
          {fmtD(d.Abs_Error ?? d.Error)} ({d.Error_Pct?.toFixed(1) ?? '—'}%)
        </span>
      </div>
    </div>
  )
}

export default function Predictions() {
  const { data: months, loading: lm, error: em } = useFetch('/api/processed-months', { pollMs: 15_000 })
  const { data: monthly }                         = useFetch('/api/monthly-sales', { pollMs: 30_000 })
  const [selected, setSelected]   = useState(null)
  const [storeFilter, setStore]   = useState(null)
  const [highlight, setHighlight] = useState(null)
  const prevNewest = useRef(null)

  // Auto-advance to newest month when a new one appears
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

  const stores = useMemo(() => [...new Set(allRows.map(r => r.Store).filter(Boolean))].sort((a,b)=>a-b), [allRows])

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

  const mae   = rows.length ? (rows.reduce((s,r) => s + (r.Abs_Error ?? Math.abs((r.Weekly_Sales??0)-r.Predicted)), 0) / rows.length) : null
  const rmse  = rows.length ? Math.sqrt(rows.reduce((s,r) => { const e=(r.Weekly_Sales??0)-r.Predicted; return s+e*e }, 0) / rows.length) : null
  const mape  = rows.length ? (rows.reduce((s,r) => s + (r.Error_Pct ?? 0), 0) / rows.length) : null
  const r2    = useMemo(() => {
    if (!rows.length) return null
    const actuals = rows.map(r => r.Weekly_Sales ?? 0)
    const preds_  = rows.map(r => r.Predicted)
    const mean_a  = actuals.reduce((s,v)=>s+v,0)/actuals.length
    const ss_tot  = actuals.reduce((s,v)=>s+(v-mean_a)**2,0)
    const ss_res  = actuals.reduce((s,v,i)=>s+(v-preds_[i])**2,0)
    return ss_tot > 0 ? (1 - ss_res/ss_tot) : null
  }, [rows])

  const onBarClick = useCallback(data => {
    if (!data?.activePayload?.[0]) return
    const s = data.activePayload[0].payload.Store
    setStore(prev => prev === s ? null : s)
  }, [])

  if (em) return <ErrorBox msg={em} />
  if (lm) return <SkeletonCard rows={4} />

  return (
    <>
      <div className="page-header">
        <div className="page-title">Predictions Explorer</div>
        <div className="page-sub">Actual vs predicted · confidence intervals · cross-filter by store</div>
      </div>

      {/* Live status bar */}
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:12, fontSize:11, color:'var(--text3)' }}>
        <span style={{
          display:'inline-block', width:7, height:7, borderRadius:'50%',
          background: fresh ? 'var(--green)' : 'var(--text3)',
          boxShadow: fresh ? '0 0 6px var(--green)' : 'none',
          transition: 'all 0.4s'
        }} />
        <span>{fresh ? 'Data refreshed' : updatedAt ? `Last updated ${updatedAt.toLocaleTimeString()}` : 'Loading…'}</span>
        <span style={{ marginLeft:'auto', color:'var(--text3)' }}>Auto-polls every 10s · <button
          className="btn btn-outline" style={{ padding:'2px 8px', fontSize:10 }}
          onClick={reload}>↻ Refresh now</button></span>
      </div>

      <MONTHS_BTN months={months || []} selected={activeMonth} onChange={m => { setSelected(m); setStore(null) }} />

      {lp ? <SkeletonCard rows={5} /> : ep ? <ErrorBox msg={ep} /> : (
        <>
          {/* KPI row */}
          <div className="kpi-grid" style={{ gridTemplateColumns:'repeat(6,1fr)' }}>
            <KPI label="Month"    value={activeMonth} />
            <KPI label="Rows"     value={rows.length} delta={storeFilter ? `Store ${storeFilter}` : 'All stores'} />
            <KPI label="MAE"      value={mae  ? fmtD(mae)  : '—'} color="var(--orange)" />
            <KPI label="RMSE"     value={rmse ? fmtD(rmse) : '—'} color="var(--red)" />
            <KPI label="MAPE"     value={mape != null ? mape.toFixed(2)+'%' : '—'}
              color={mape != null && mape < 5 ? 'var(--green)' : 'var(--orange)'} />
            <KPI label="R²"       value={r2 != null ? r2.toFixed(4) : '—'}
              color={r2 != null && r2 > 0.9 ? 'var(--green)' : 'var(--orange)'} />
          </div>

          {/* Store cross-filter pills */}
          {stores.length > 0 && (
            <div style={{ display:'flex', gap:5, flexWrap:'wrap', marginBottom:16, alignItems:'center' }}>
              <span style={{ fontSize:11, color:'var(--text3)', marginRight:4 }}>Filter by store:</span>
              <button className={`btn ${storeFilter==null?'btn-primary':'btn-outline'}`}
                style={{ padding:'3px 10px', fontSize:11 }} onClick={() => setStore(null)}>All</button>
              {stores.map(s => (
                <button key={s}
                  className={`btn ${storeFilter===s?'btn-primary':'btn-outline'}`}
                  style={{ padding:'3px 10px', fontSize:11 }}
                  onClick={() => setStore(prev => prev===s ? null : s)}>
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Main chart — Actual vs Predicted with CI band + Brush zoom */}
          <SectionCard title="Actual vs Predicted — with 95% Confidence Band">
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={chartData} margin={{ top:8, right:16, bottom:20, left:0 }}
                onClick={onBarClick}>
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
                <XAxis dataKey="idx" tick={{ fontSize:9 }}
                  label={{ value:'Row', position:'insideBottom', offset:-12, fill:'var(--text3)', fontSize:10 }} />
                <YAxis tick={{ fontSize:10 }} tickFormatter={v => '$'+(v/1000).toFixed(0)+'K'} />
                <Tooltip content={<PredTooltip />} />
                <Legend wrapperStyle={{ fontSize:12 }} />
                {/* CI band */}
                <Area type="monotone" dataKey="CI_Upper" stroke="none" fill="url(#gCI)"
                  name="CI Upper" legendType="none" dot={false} />
                <Area type="monotone" dataKey="CI_Lower" stroke="none" fill="var(--bg)"
                  name="CI Lower" legendType="none" dot={false} />
                <Area type="monotone" dataKey="Actual" stroke="var(--blue)"
                  fill="url(#gAct)" strokeWidth={2} dot={false} name="Actual" />
                <Line type="monotone" dataKey="Predicted" stroke="var(--orange)"
                  strokeWidth={2} dot={false} strokeDasharray="4 2" name="Predicted" />
                <Brush dataKey="idx" height={20} stroke="var(--border2)"
                  fill="var(--card2)" travellerWidth={6}
                  startIndex={0} endIndex={Math.min(49, chartData.length-1)} />
              </ComposedChart>
            </ResponsiveContainer>
          </SectionCard>

          <div className="grid-2">
            {/* Error bar chart — click bar to filter store */}
            <SectionCard title="Absolute Error per Row — click bar to filter store">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} margin={{ top:4, right:8, bottom:0, left:0 }}
                  onClick={onBarClick}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="idx" tick={{ fontSize:9 }} />
                  <YAxis tick={{ fontSize:10 }} tickFormatter={v => '$'+(v/1000).toFixed(0)+'K'} />
                  <Tooltip content={<PredTooltip />} />
                  <Bar dataKey="Abs_Error" name="Abs Error" radius={[2,2,0,0]}>
                    {chartData.map((d, i) => (
                      <Cell key={i}
                        fill={d.Store === storeFilter ? 'var(--blue)' :
                              (d.Error_Pct > 15 ? 'var(--red)' :
                               d.Error_Pct > 8  ? 'var(--orange)' : 'var(--green)')}
                        fillOpacity={highlight === i ? 1 : 0.75}
                      />
                    ))}
                  </Bar>
                  {mae && <ReferenceLine y={mae} stroke="var(--orange)" strokeDasharray="4 2"
                    label={{ value:'MAE', fill:'var(--orange)', fontSize:10, position:'insideTopRight' }} />}
                </BarChart>
              </ResponsiveContainer>
            </SectionCard>

            {/* Monthly trend */}
            <SectionCard title="Monthly Avg — Actual vs Predicted">
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={monthly || []} margin={{ top:4, right:8, bottom:0, left:0 }}>
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
                  <XAxis dataKey="month" tick={{ fontSize:9 }} />
                  <YAxis tick={{ fontSize:10 }} tickFormatter={v => '$'+(v/1000).toFixed(0)+'K'} />
                  <Tooltip {...CHART_STYLE} formatter={v => ['$'+Number(v).toLocaleString()]} />
                  <Legend wrapperStyle={{ fontSize:12 }} />
                  <Area type="monotone" dataKey="actual"    stroke="var(--green)"  fill="url(#gM1)" strokeWidth={2} dot={false} name="Actual" />
                  <Area type="monotone" dataKey="predicted" stroke="var(--orange)" fill="url(#gM2)" strokeWidth={2} dot={false} name="Predicted" strokeDasharray="4 2" />
                  {activeMonth && <ReferenceLine x={activeMonth} stroke="var(--blue)" strokeDasharray="3 2"
                    label={{ value:'Selected', fill:'var(--blue)', fontSize:9, position:'insideTopRight' }} />}
                </AreaChart>
              </ResponsiveContainer>
            </SectionCard>
          </div>

          {/* Professional prediction table with conditional formatting */}
          <SectionCard title={`Prediction Detail — ${activeMonth}${storeFilter ? ` · Store ${storeFilter}` : ''} (${Math.min(rows.length,100)} rows)`}>
            <div style={{ overflowX:'auto', maxHeight:360, overflowY:'auto' }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Store</th><th>Date</th>
                    <th>Actual</th><th>Predicted</th>
                    <th>CI Lower</th><th>CI Upper</th>
                    <th>Abs Error</th><th>Error %</th><th>Quality</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0,100).map((r, i) => {
                    const actual = r.Weekly_Sales ?? r.actual ?? 0
                    const absErr = r.Abs_Error ?? Math.abs(actual - r.Predicted)
                    const errPct = r.Error_Pct ?? (actual ? absErr/actual*100 : 0)
                    const quality = errPct < 3 ? {label:'Excellent', color:'var(--green)'}
                                  : errPct < 8 ? {label:'Good',      color:'var(--blue)'}
                                  : errPct < 15? {label:'Fair',      color:'var(--orange)'}
                                  :              {label:'Poor',      color:'var(--red)'}
                    return (
                      <tr key={i}
                        onMouseEnter={() => setHighlight(i)}
                        onMouseLeave={() => setHighlight(null)}
                        onClick={() => setStore(prev => prev===r.Store ? null : r.Store)}
                        style={{ cursor:'pointer', background: highlight===i ? 'rgba(59,130,246,0.06)' : undefined }}>
                        <td className="mono" style={{ color:'var(--blue)' }}>{r.Store ?? '—'}</td>
                        <td className="mono" style={{ fontSize:11 }}>{r.Date?.slice(0,10) ?? '—'}</td>
                        <td className="mono">{fmtD(actual)}</td>
                        <td className="mono" style={{ color:'var(--orange)' }}>{fmtD(r.Predicted)}</td>
                        <td className="mono" style={{ color:'var(--text3)', fontSize:11 }}>{r.CI_Lower != null ? fmtD(r.CI_Lower) : '—'}</td>
                        <td className="mono" style={{ color:'var(--text3)', fontSize:11 }}>{r.CI_Upper != null ? fmtD(r.CI_Upper) : '—'}</td>
                        <td className="mono" style={{ color: errPct>15?'var(--red)':'var(--text2)' }}>{fmtD(absErr)}</td>
                        <td className="mono" style={{ color: errPct>15?'var(--red)':errPct>8?'var(--orange)':'var(--green)' }}>
                          {errPct.toFixed(2)}%
                          <div className="progress-bar" style={{ width:60, display:'inline-block', marginLeft:6, verticalAlign:'middle' }}>
                            <div className="progress-fill" style={{ width:`${Math.min(errPct*4,100)}%`, background: quality.color }} />
                          </div>
                        </td>
                        <td><span className="badge" style={{ background:`${quality.color}18`, color:quality.color, border:`1px solid ${quality.color}44`, fontSize:10 }}>{quality.label}</span></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div style={{ marginTop:10, fontSize:11, color:'var(--text3)', display:'flex', gap:16 }}>
              <span>🟢 Excellent &lt;3%</span>
              <span>🔵 Good &lt;8%</span>
              <span>🟠 Fair &lt;15%</span>
              <span>🔴 Poor ≥15%</span>
              <span style={{ marginLeft:'auto' }}>Click row to filter · Hover for details</span>
            </div>
          </SectionCard>
        </>
      )}
    </>
  )
}
