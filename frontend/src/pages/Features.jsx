import { useState, useMemo, memo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts'
import { useFetch } from '../api.js'
import { Spinner, ErrorBox, KPI, SectionCard, CHART_STYLE } from '../ui.jsx'

const PALETTE = ['#3b82f6','#6366f1','#8b5cf6','#a78bfa','#60a5fa','#34d399','#f59e0b','#f87171','#06b6d4','#10b981']

const GROUPS = {
  'Lag':         f => f.startsWith('Lag_'),
  'Rolling':     f => f.startsWith('Rolling_') || f.startsWith('Momentum_') || f.startsWith('Volatility_'),
  'Temporal':    f => ['Year','Month','Week','Quarter','DayOfYear','Season','Is_Year_End','Is_Year_Start','Is_Q4','Near_Holiday','Week_Sin','Week_Cos','Month_Sin','Month_Cos'].includes(f) || f.startsWith('Weeks_To_'),
  'Store Stats': f => f.startsWith('Store_') || f.startsWith('Sales_vs_'),
  'Interaction': f => ['Temp_Fuel','Price_Index','Fuel_Unemployment','CPI_Fuel','Temp_Holiday','Store_Holiday','Holiday_Q4','Unemployment_CPI'].includes(f),
  'Raw Inputs':  f => ['Holiday_Flag','Temperature','Fuel_Price','CPI','Unemployment'].includes(f),
}

const GroupCard = memo(({ group, feats, isActive, isSelected, selectedFeat, onFilter, onFeatClick }) => (
  <SectionCard
    title={`${group} (${feats.length})`}
    style={{ opacity: isActive ? 1 : 0.3, cursor: 'pointer', transition: 'opacity 0.15s' }}
    action={
      <button className="btn btn-outline" style={{ padding: '2px 10px', fontSize: 10 }} onClick={onFilter}>
        {isSelected ? '✕ Clear' : 'Filter'}
      </button>
    }
  >
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
      {feats.length
        ? feats.map(f => (
          <span key={f} onClick={() => onFeatClick(f)}
            className={`badge ${selectedFeat === f ? 'b-blue' : 'b-purple'}`}
            style={{ fontSize: 10, cursor: 'pointer', opacity: selectedFeat && selectedFeat !== f ? 0.35 : 1 }}>
            {f}
          </span>
        ))
        : <span style={{ color: 'var(--text3)', fontSize: 12 }}>None</span>
      }
    </div>
  </SectionCard>
))

export default function Features() {
  const { data: summary, loading: ls, error: es } = useFetch('/api/summary')
  const { data: tlog,    loading: lt, error: et } = useFetch('/api/training-log')
  const [activeGroup, setGroup]   = useState(null)
  const [selectedFeat, setFeat]   = useState(null)

  const features    = summary?.feature_names || []
  const importances = tlog?.feature_importances || null

  const allChart = useMemo(() => features
    .map(name => ({
      name,
      Importance: importances ? +(importances[name] || 0).toFixed(4) : 0,
      group: Object.keys(GROUPS).find(g => GROUPS[g](name)) || 'Other',
    }))
    .sort((a, b) => b.Importance - a.Importance)
    .slice(0, 20),
  [features, importances])

  const chartData = useMemo(() =>
    activeGroup ? allChart.filter(d => d.group === activeGroup) : allChart,
  [allChart, activeGroup])

  const groupCounts = useMemo(() =>
    Object.fromEntries(Object.keys(GROUPS).map(g => [g, features.filter(GROUPS[g]).length])),
  [features])

  if (es || et) return <ErrorBox msg={es || et} />
  if (ls || lt) return <Spinner />

  return (
    <>
      <div className="page-header">
        <div className="page-title">Feature Importance</div>
        <div className="page-sub">{features.length || 60}+ engineered features — click group to filter chart</div>
      </div>

      <div className="card" style={{ marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <span style={{ fontWeight: 700, color: 'var(--text)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '1.2px' }}>
            Feature Group Filter
          </span>
          {activeGroup && (
            <button className="btn btn-outline" style={{ padding: '3px 10px', fontSize: 11 }}
              onClick={() => { setGroup(null); setFeat(null) }}>✕ Clear</button>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {Object.keys(GROUPS).map(g => (
            <button key={g}
              onClick={() => { setGroup(p => p === g ? null : g); setFeat(null) }}
              style={{
                padding: '5px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                cursor: 'pointer', border: '1px solid',
                borderColor: activeGroup === g ? 'var(--blue)' : 'var(--border2)',
                background:  activeGroup === g ? 'rgba(59,130,246,0.12)' : 'transparent',
                color:       activeGroup === g ? 'var(--blue)' : 'var(--text3)',
                transition:  'all 0.15s',
              }}>
              {g} <span style={{ opacity: 0.6, fontSize: 11 }}>({groupCounts[g] || 0})</span>
            </button>
          ))}
        </div>
        {activeGroup && (
          <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text3)' }}>
            Showing <span style={{ color: 'var(--blue)', fontWeight: 600 }}>{activeGroup}</span> features only
          </div>
        )}
      </div>

      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
        <KPI label="Total Features" value={features.length || 60} />
        <KPI label="Feature Groups"  value={6} />
        <KPI label="Showing"         value={chartData.length} delta={activeGroup || 'Top 20'} />
      </div>

      <SectionCard title={`Feature Importance — ${activeGroup || 'Top 20'} — click bar to inspect`}>
        <ResponsiveContainer width="100%" height={Math.max(320, chartData.length * 24)}>
          <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 130 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 10 }} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: 'var(--text2)' }} width={130} />
            <Tooltip {...CHART_STYLE} formatter={v => [v, 'Importance']} />
            <Bar dataKey="Importance" radius={[0, 4, 4, 0]} onClick={d => setFeat(p => p === d.name ? null : d.name)}>
              {chartData.map((d, i) => (
                <Cell key={i}
                  fill={PALETTE[i % PALETTE.length]}
                  opacity={selectedFeat && selectedFeat !== d.name ? 0.2 : 1}
                  stroke={selectedFeat === d.name ? '#fff' : 'none'}
                  strokeWidth={1.5}
                  style={{ cursor: 'pointer' }}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {selectedFeat && (
          <div className="alert alert-b" style={{ marginTop: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>
              <strong>{selectedFeat}</strong> — Importance: <strong>{(importances?.[selectedFeat] || 0).toFixed(4)}</strong>
              {' · '}Group: <strong>{Object.keys(GROUPS).find(g => GROUPS[g](selectedFeat)) || 'Other'}</strong>
            </span>
            <button className="btn btn-outline" style={{ padding: '3px 10px', fontSize: 11 }} onClick={() => setFeat(null)}>✕</button>
          </div>
        )}
      </SectionCard>

      <div className="grid-2">
        {Object.entries(GROUPS).map(([group, test]) => {
          const feats = features.filter(test)
          return (
            <GroupCard key={group} group={group} feats={feats}
              isActive={!activeGroup || activeGroup === group}
              isSelected={activeGroup === group}
              selectedFeat={selectedFeat}
              onFilter={() => setGroup(p => p === group ? null : group)}
              onFeatClick={f => setFeat(p => p === f ? null : f)}
            />
          )
        })}
      </div>
    </>
  )
}
