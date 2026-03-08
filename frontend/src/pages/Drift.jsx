import { useState, useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, Legend, ReferenceLine } from 'recharts'
import { useFetch } from '../api.js'
import { Spinner, ErrorBox, KPI, SectionCard, SevBadge, fmtD, CHART_STYLE } from '../ui.jsx'
import { SlicerPanel, useSlicerStore, slicerActions } from '../slicer.jsx'

export default function Drift() {
  const { data: drift, loading, error } = useFetch('/api/drift')
  const slicer = useSlicerStore()

  const months   = useMemo(() => (drift||[]).map(d => d.month), [drift])
  const filtered = useMemo(() => (drift||[]).filter(d => {
    if (slicer.months.length   && !slicer.months.includes(d.month))    return false
    if (slicer.severity        && d.severity !== slicer.severity)       return false
    return true
  }), [drift, slicer])

  const isActive = d => {
    if (!slicer.months.length && !slicer.severity) return true
    return filtered.some(f => f.month === d.month)
  }

  if (error)   return <ErrorBox msg={error} />
  if (loading) return <Spinner />

  const sevColor = s => s==='severe'?'var(--red)':s==='mild'?'var(--orange)':'var(--green)'

  const errorData   = (drift||[]).map(d => ({ month:d.month, Increase: d.error_trend?.error_increase ? +(d.error_trend.error_increase*100).toFixed(1):0, sev:d.severity }))
  const featureData = (drift||[]).map(d => ({ month:d.month, Severe:d.severe_features||0, Mild:d.mild_features||0 }))

  const avgIncrease = filtered.length
    ? (filtered.reduce((s,d)=>s+(d.error_trend?.error_increase||0),0)/filtered.length*100).toFixed(0)+'%' : '—'

  const onBarClick = e => { if (e?.activeLabel) slicerActions.toggleMonth(e.activeLabel) }

  return (
    <>
      <div className="page-header">
        <div className="page-title">Drift Analysis</div>
        <div className="page-sub">5 detection methods: KS Test · PSI · Wasserstein · JS Divergence · Error Trend</div>
      </div>

      <SlicerPanel months={months} slicer={slicer} />

      <div className="kpi-grid" style={{ gridTemplateColumns:'repeat(3,1fr)' }}>
        <KPI label="Months Monitored" value={filtered.length} delta={filtered.length !== drift?.length ? `of ${drift?.length} total` : 'all'} />
        <KPI label="Severe Months"    value={filtered.filter(d=>d.severity==='severe').length} color="var(--red)" />
        <KPI label="Avg Error Increase" value={avgIncrease} color="var(--orange)" />
      </div>

      <div className="grid-2">
        <SectionCard title="Error Increase % — click bar to filter">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={errorData} margin={{ top:4, right:8, bottom:0, left:0 }} onClick={onBarClick}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize:10 }} />
              <YAxis tick={{ fontSize:10 }} tickFormatter={v => v+'%'} />
              <Tooltip {...CHART_STYLE} formatter={v => [v+'%','Error Increase']} />
              <Bar dataKey="Increase" radius={[3,3,0,0]}>
                {errorData.map((d,i) => (
                  <Cell key={i} fill={sevColor(d.sev)} opacity={isActive(d) ? 1 : 0.2}
                    stroke={slicer.months.includes(d.month) ? '#fff' : 'none'} strokeWidth={1.5} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>

        <SectionCard title="Drifted Feature Count — click bar to filter">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={featureData} margin={{ top:4, right:8, bottom:0, left:0 }} onClick={onBarClick}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize:10 }} />
              <YAxis tick={{ fontSize:10 }} />
              <Tooltip {...CHART_STYLE} />
              <Legend />
              <Bar dataKey="Severe" fill="var(--red)"    stackId="a">
                {featureData.map((d,i) => <Cell key={i} opacity={isActive(d)?1:0.2} />)}
              </Bar>
              <Bar dataKey="Mild"   fill="var(--orange)" stackId="a" radius={[3,3,0,0]}>
                {featureData.map((d,i) => <Cell key={i} opacity={isActive(d)?1:0.2} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>
      </div>

      <SectionCard title="Drift History">
        <div style={{ overflowX:'auto' }}>
          <table className="tbl">
            <thead>
              <tr><th>Month</th><th>Severity</th><th>Severe Feats</th><th>Mild Feats</th><th>Baseline MAE</th><th>Current MAE</th><th>Error Increase</th></tr>
            </thead>
            <tbody>
              {(drift||[]).map(d => (
                <tr key={d.month}
                  onClick={() => slicerActions.toggleMonth(d.month)}
                  style={{ cursor:'pointer', opacity: isActive(d) ? 1 : 0.3,
                    background: slicer.months.includes(d.month) ? 'rgba(59,130,246,.07)' : undefined }}>
                  <td className="mono">{d.month}</td>
                  <td><SevBadge severity={d.severity} /></td>
                  <td style={{ color:'var(--red)' }}>{d.severe_features}</td>
                  <td style={{ color:'var(--orange)' }}>{d.mild_features}</td>
                  <td className="mono">{fmtD(d.error_trend?.baseline_error)}</td>
                  <td className="mono">{fmtD(d.error_trend?.current_error)}</td>
                  <td className="mono" style={{ color:'var(--red)' }}>+{((d.error_trend?.error_increase||0)*100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ marginTop:8, fontSize:11, color:'var(--text3)' }}>Click row or bar to add to month filter</div>
      </SectionCard>
    </>
  )
}
