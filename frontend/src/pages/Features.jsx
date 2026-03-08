import { useState, useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts'
import { useFetch } from '../api.js'
import { Spinner, ErrorBox, KPI, SectionCard, CHART_STYLE } from '../ui.jsx'

const PALETTE = ['#3b82f6','#6366f1','#8b5cf6','#a78bfa','#60a5fa','#34d399','#f59e0b','#f87171']

const GROUPS = {
  'Lag':         f => f.startsWith('Lag_'),
  'Rolling':     f => f.startsWith('Rolling_') || f.startsWith('Momentum_') || f.startsWith('Volatility_'),
  'Temporal':    f => ['Year','Month','Week','Quarter','DayOfYear','Season','Is_Year_End','Is_Year_Start','Is_Q4','Near_Holiday','Week_Sin','Week_Cos','Month_Sin','Month_Cos'].includes(f) || f.startsWith('Weeks_To_'),
  'Store Stats': f => f.startsWith('Store_') || f.startsWith('Sales_vs_'),
  'Interaction': f => ['Temp_Fuel','Price_Index','Fuel_Unemployment','CPI_Fuel','Temp_Holiday','Store_Holiday','Holiday_Q4','Unemployment_CPI'].includes(f),
  'Raw Inputs':  f => ['Holiday_Flag','Temperature','Fuel_Price','CPI','Unemployment'].includes(f),
}

export default function Features() {
  const { data: summary, loading: ls, error: es } = useFetch('/api/summary')
  const { data: tlog,    loading: lt, error: et } = useFetch('/api/training-log')
  const [activeGroup, setGroup] = useState(null)
  const [selectedFeat, setFeat] = useState(null)

  if (es||et) return <ErrorBox msg={es||et} />
  if (ls||lt) return <Spinner />

  const features    = summary?.feature_names || []
  const importances = tlog?.feature_importances || null

  const allChart = useMemo(() => features
    .map(name => ({ name, Importance: importances ? +(importances[name]||0).toFixed(4) : 0, group: Object.keys(GROUPS).find(g => GROUPS[g](name)) || 'Other' }))
    .sort((a,b) => b.Importance - a.Importance)
    .slice(0, 20),
  [features, importances])

  const chartData = useMemo(() =>
    activeGroup ? allChart.filter(d => d.group === activeGroup) : allChart,
  [allChart, activeGroup])

  const groupCounts = useMemo(() =>
    Object.fromEntries(Object.keys(GROUPS).map(g => [g, features.filter(GROUPS[g]).length])),
  [features])

  return (
    <>
      <div className="page-header">
        <div className="page-title">Feature Importance</div>
        <div className="page-sub">{features.length || 60}+ engineered features — click group to filter chart</div>
      </div>

      {/* Group slicer */}
      <div style={{ background:'var(--card)', border:'1px solid var(--border)', borderRadius:8, padding:'14px 16px', marginBottom:18 }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:10 }}>
          <span style={{ fontWeight:700, color:'var(--text)', fontSize:11, textTransform:'uppercase', letterSpacing:'1.2px' }}>▼ Feature Group Slicer</span>
          {activeGroup && <button className="btn btn-outline" style={{ padding:'2px 10px', fontSize:11 }} onClick={() => { setGroup(null); setFeat(null) }}>✕ Clear</button>}
        </div>
        <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
          {Object.keys(GROUPS).map(g => (
            <button key={g} onClick={() => { setGroup(p => p===g?null:g); setFeat(null) }}
              style={{
                padding:'4px 12px', borderRadius:4, fontSize:11, fontWeight:600, cursor:'pointer', border:'1px solid',
                borderColor: activeGroup===g ? 'var(--blue)' : 'var(--border2)',
                background:  activeGroup===g ? 'rgba(59,130,246,.15)' : 'transparent',
                color:       activeGroup===g ? 'var(--blue)' : 'var(--text3)',
              }}>
              {g} <span style={{ opacity:.6 }}>({groupCounts[g]||0})</span>
            </button>
          ))}
        </div>
        {activeGroup && <div style={{ marginTop:8, fontSize:11, color:'var(--text3)' }}>Showing <span style={{ color:'var(--blue)' }}>{activeGroup}</span> features only</div>}
      </div>

      <div className="kpi-grid" style={{ gridTemplateColumns:'repeat(3,1fr)' }}>
        <KPI label="Total Features" value={features.length || 60} />
        <KPI label="Feature Groups"  value={6} />
        <KPI label="Showing"         value={chartData.length} delta={activeGroup || 'Top 20'} />
      </div>

      <SectionCard title={`Feature Importance — ${activeGroup || 'Top 20'} — click bar to inspect`}>
        <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 22)}>
          <BarChart data={chartData} layout="vertical" margin={{ top:4, right:16, bottom:0, left:120 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" tick={{ fontSize:10 }} />
            <YAxis type="category" dataKey="name" tick={{ fontSize:11, fill:'var(--text2)' }} width={120} />
            <Tooltip {...CHART_STYLE} formatter={v => [v,'Importance']} />
            <Bar dataKey="Importance" radius={[0,3,3,0]} onClick={d => setFeat(p => p===d.name?null:d.name)}>
              {chartData.map((d,i) => (
                <Cell key={i}
                  fill={PALETTE[i % PALETTE.length]}
                  opacity={selectedFeat && selectedFeat!==d.name ? 0.25 : 1}
                  stroke={selectedFeat===d.name ? '#fff' : 'none'} strokeWidth={1.5}
                  style={{ cursor:'pointer' }}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        {selectedFeat && (
          <div className="alert alert-b" style={{ marginTop:10 }}>
            <strong>{selectedFeat}</strong> — Importance: <strong>{(importances?.[selectedFeat]||0).toFixed(4)}</strong> · Group: <strong>{Object.keys(GROUPS).find(g=>GROUPS[g](selectedFeat))||'Other'}</strong>
            <button className="btn btn-outline" style={{ marginLeft:12, padding:'2px 8px', fontSize:11 }} onClick={() => setFeat(null)}>✕</button>
          </div>
        )}
      </SectionCard>

      <div className="grid-2">
        {Object.entries(GROUPS).map(([group, test]) => {
          const feats = features.filter(test)
          const isActive = !activeGroup || activeGroup === group
          return (
            <SectionCard key={group} title={`${group} (${feats.length})`}
              style={{ opacity: isActive ? 1 : 0.35, cursor:'pointer', transition:'opacity .15s' }}
              action={<button className="btn btn-outline" style={{ padding:'1px 8px', fontSize:10 }}
                onClick={() => setGroup(p => p===group?null:group)}>
                {activeGroup===group ? '✕ Clear' : 'Filter'}
              </button>}>
              <div style={{ display:'flex', flexWrap:'wrap', gap:5 }}>
                {feats.length
                  ? feats.map(f => (
                    <span key={f}
                      onClick={() => setFeat(p => p===f?null:f)}
                      className={`badge ${selectedFeat===f?'b-blue':'b-purple'}`}
                      style={{ fontSize:10, cursor:'pointer', opacity: selectedFeat&&selectedFeat!==f?0.4:1 }}>{f}</span>
                  ))
                  : <span style={{ color:'var(--text3)', fontSize:12 }}>None</span>
                }
              </div>
            </SectionCard>
          )
        })}
      </div>
    </>
  )
}
