import { useState, useMemo, memo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Cell, Treemap,
} from 'recharts'
import { useFetch } from '../api.js'
import { ErrorBox, KPI, SectionCard } from '../ui.jsx'

const PALETTE = ['#2563eb','#7c3aed','#0891b2','#059669','#d97706','#dc2626','#6366f1','#10b981','#f59e0b','#ef4444']

const GROUP_COLOR = {
  'Lag':           '#2563eb',
  'Rolling':       '#7c3aed',
  'Temporal':      '#0891b2',
  'Product Stats': '#059669',
  'Interaction':   '#d97706',
  'Raw Inputs':    '#dc2626',
}

const GROUPS = {
  'Lag':           f => f.startsWith('Lag_'),
  'Rolling':       f => f.startsWith('Rolling_') || f.startsWith('Momentum_') || f.startsWith('Volatility_'),
  'Temporal':      f => ['Year','Month','Week','Quarter','DayOfYear','Season','Is_Year_End','Is_Year_Start','Is_Q4','Near_Holiday','Week_Sin','Week_Cos','Month_Sin','Month_Cos'].includes(f) || f.startsWith('Weeks_To_'),
  'Product Stats': f => f.startsWith('Store_') || f.startsWith('Product_') || f.startsWith('Demand_vs_'),
  'Interaction':   f => f.includes('_x_') || ['Temp_Fuel','Price_Index','Fuel_Unemployment','CPI_Fuel','Temp_Holiday','Store_Holiday','Holiday_Q4','Unemployment_CPI','Store_Product','Product_Holiday'].includes(f),
  'Raw Inputs':    f => !f.startsWith('Lag_') && !f.startsWith('Rolling_') && !f.startsWith('Momentum_') && !f.startsWith('Volatility_') && !f.startsWith('Store_') && !f.startsWith('Product_') && !f.startsWith('Demand_vs_') && !f.startsWith('Weeks_To_') && !['Year','Month','Week','Quarter','DayOfYear','Season','Is_Year_End','Is_Year_Start','Is_Q4','Near_Holiday','Week_Sin','Week_Cos','Month_Sin','Month_Cos'].includes(f) && !f.includes('_x_') && !['Temp_Fuel','Price_Index','Fuel_Unemployment','CPI_Fuel','Temp_Holiday','Store_Holiday','Holiday_Q4','Unemployment_CPI','Store_Product','Product_Holiday','Lag_52_ratio'].includes(f),
}

const GROUP_DESC = {
  'Lag':           'Past demand values (1-26 weeks back) — captures product-specific demand memory',
  'Rolling':       'Moving averages, min/max, momentum, volatility — smooths weekly noise per product',
  'Temporal':      'Time features (month, week, season, holiday proximity) — captures seasonal demand patterns',
  'Product Stats': 'Per-product aggregates (mean, median, max, CV) — encodes product demand level',
  'Interaction':   'Cross-feature combinations — captures non-linear relationships between your input features',
  'Raw Inputs':    'Your original uploaded columns — the raw features from your dataset',
}

const getGroup = name => Object.keys(GROUPS).find(g => GROUPS[g](name)) || 'Other'

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#fff', border: '1px solid var(--border2)', borderRadius: 8, padding: '10px 14px', fontSize: 12, boxShadow: '0 4px 20px rgba(37,99,235,0.12)' }}>
      <div style={{ fontWeight: 700, color: 'var(--text)', marginBottom: 4 }}>{label || payload[0]?.payload?.name}</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color || 'var(--text2)' }}>
          {p.name}: <strong>{typeof p.value === 'number' ? p.value.toFixed(4) : p.value}</strong>
        </div>
      ))}
    </div>
  )
}

const TreeContent = ({ x, y, width, height, name, value, color }) => {
  if (width < 30 || height < 20) return <rect x={x} y={y} width={width} height={height} fill={color} rx={3} />
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={color} rx={3} stroke="#fff" strokeWidth={2} />
      {width > 60 && height > 28 && (
        <text x={x + width / 2} y={y + height / 2} textAnchor="middle" dominantBaseline="middle"
          fill="#fff" fontSize={Math.min(12, width / 6)} fontWeight={600}>{name}</text>
      )}
      {width > 60 && height > 44 && (
        <text x={x + width / 2} y={y + height / 2 + 14} textAnchor="middle" dominantBaseline="middle"
          fill="rgba(255,255,255,0.75)" fontSize={10}>{(value * 100).toFixed(1)}%</text>
      )}
    </g>
  )
}

export default function Features() {
  const { data: summary, loading: ls, error: es } = useFetch('/api/summary')
  const { data: fiData,   loading: lf, error: ef } = useFetch('/api/feature-importances')
  const { data: monthly }                           = useFetch('/api/monthly-sales')
  const [activeGroup, setGroup] = useState(null)
  const [selectedFeat, setFeat] = useState(null)

  const features    = fiData?.feature_names || summary?.feature_names || []
  const importances = fiData?.importances   || null

  // Top 10 for simplified view
  const top10 = useMemo(() => features
    .map(name => ({ name, value: importances ? +(importances[name] || 0) : 0, group: getGroup(name) }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10),
  [features, importances])

  const chartData = useMemo(() =>
    activeGroup ? top10.filter(d => d.group === activeGroup) : top10,
  [top10, activeGroup])

  // Group totals
  const groupTotals = useMemo(() => {
    const totals = {}
    features.forEach(name => {
      const g = getGroup(name)
      totals[g] = (totals[g] || 0) + (importances?.[name] || 0)
    })
    const sum = Object.values(totals).reduce((a, b) => a + b, 0) || 1
    return Object.entries(totals)
      .map(([name, val]) => ({ name, value: +(val / sum).toFixed(4), color: GROUP_COLOR[name] || '#94a3b8', count: features.filter(GROUPS[name] || (() => false)).length }))
      .sort((a, b) => b.value - a.value)
  }, [features, importances])

  // Live model accuracy
  const liveAccuracy = useMemo(() => {
    if (!monthly?.length) return null
    const valid = monthly.filter(d => d.actual != null && d.predicted != null)
    if (!valid.length) return null
    const mape = valid.reduce((s, d) => s + (d.actual ? Math.abs(d.actual - d.predicted) / Math.abs(d.actual) * 100 : 0), 0) / valid.length
    return Math.round(100 - mape)
  }, [monthly])

  if (es || ef) return <ErrorBox msg={es || ef} />

  const loading  = ls || lf
  const totalImp = top10.reduce((s, d) => s + d.value, 0)
  const topFeat  = top10[0]

  return (
    <>
      <div className="page-header">
        <div className="page-title">Feature Importance</div>
        <div className="page-sub">{loading ? 'Loading…' : `${features.length} ultra-optimized features driving product demand predictions`}</div>
      </div>

      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(5,1fr)' }}>
        <KPI label="Total Features"  value={loading ? '…' : features.length} delta="Ultra-optimized" />
        <KPI label="Feature Groups"  value={loading ? '…' : groupTotals.length} delta="Categories" />
        <KPI label="Top Feature"     value={loading ? '…' : (topFeat?.name || '—')} delta={topFeat ? (topFeat.value * 100).toFixed(1) + '% importance' : ''} />
        <KPI label="Top 10 Coverage" value={loading ? '…' : (totalImp * 100).toFixed(1) + '%'} delta="of total importance" />
        <KPI label="Model Accuracy"  value={liveAccuracy != null ? liveAccuracy + '%' : '—'} color="var(--green)" delta="Live · test set" />
      </div>

      {/* Technical note */}
      <div className="alert alert-g" style={{ marginBottom: 16, fontSize: 11 }}>
        <strong>⚡ Speed Optimizations:</strong> Reduced from 40-87+ to ~20-30 features using minimal lag windows (4 vs 8), 
        fewer rolling stats (2 vs 4), essential temporal features only, and limited interactions (5 vs 10 pairs)
      </div>

      {/* Group filter pills */}
      <div className="card" style={{ marginBottom: 16, padding: '14px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginRight: 4 }}>Filter Group</span>
          {Object.keys(GROUPS).map(g => (
            <button key={g} onClick={() => { setGroup(p => p === g ? null : g); setFeat(null) }}
              style={{
                padding: '4px 13px', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                border: `1px solid ${activeGroup === g ? GROUP_COLOR[g] : 'var(--border2)'}`,
                background: activeGroup === g ? GROUP_COLOR[g] + '18' : 'transparent',
                color: activeGroup === g ? GROUP_COLOR[g] : 'var(--text3)',
                transition: 'all 0.15s',
              }}>
              {g}
            </button>
          ))}
          {activeGroup && (
            <button className="btn btn-outline" style={{ padding: '3px 10px', fontSize: 11, marginLeft: 'auto' }}
              onClick={() => { setGroup(null); setFeat(null) }}>Clear</button>
          )}
        </div>
        {activeGroup && GROUP_DESC[activeGroup] && (
          <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text2)', padding: '8px 12px', background: 'var(--bg2)', borderRadius: 6, border: '1px solid var(--border)' }}>
            {GROUP_DESC[activeGroup]}
          </div>
        )}
      </div>

      {/* Main Charts - Only 2 charts for simplicity */}
      <div className="grid-2" style={{ alignItems: 'start' }}>
        <SectionCard title={`Top ${chartData.length} Features — click to inspect`}>
          {loading
            ? <div className="skel" style={{ height: 300, borderRadius: 8 }} />
            : <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 26)}>
            <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 40, bottom: 0, left: 140 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" />
              <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={v => (v * 100).toFixed(1) + '%'} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: 'var(--text2)' }} width={140} />
              <Tooltip content={<Tip />} />
              <Bar dataKey="value" name="Importance" radius={[0, 4, 4, 0]}
                onClick={d => setFeat(p => p === d.name ? null : d.name)}>
                {chartData.map((d, i) => (
                  <Cell key={i}
                    fill={GROUP_COLOR[d.group] || PALETTE[i % PALETTE.length]}
                    opacity={selectedFeat && selectedFeat !== d.name ? 0.18 : 1}
                    stroke={selectedFeat === d.name ? '#1e3a8a' : 'none'}
                    strokeWidth={1.5} style={{ cursor: 'pointer' }}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>}

          {selectedFeat && (
            <div style={{ marginTop: 12, padding: '10px 14px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12 }}>
              <span>
                <strong style={{ color: 'var(--blue)' }}>{selectedFeat}</strong>
                {' — '}<strong>{((importances?.[selectedFeat] || 0) * 100).toFixed(2)}%</strong> importance
                {' · '}Group: <strong style={{ color: GROUP_COLOR[getGroup(selectedFeat)] }}>{getGroup(selectedFeat)}</strong>
              </span>
              <button className="btn btn-outline" style={{ padding: '2px 10px', fontSize: 11 }} onClick={() => setFeat(null)}>Clear</button>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Feature Group Share">
          {loading
            ? <div className="skel" style={{ height: 300, borderRadius: 8 }} />
            : <ResponsiveContainer width="100%" height={300}>
            <Treemap data={groupTotals.map(g => ({
              ...g,
              opacity: !activeGroup || activeGroup === g.name ? 1 : 0.3
            }))} dataKey="value" nameKey="name" aspectRatio={4 / 3} 
              content={({ x, y, width, height, name, value, color, opacity = 1 }) => {
                if (width < 30 || height < 20) return <rect x={x} y={y} width={width} height={height} fill={color} rx={3} opacity={opacity} />
                return (
                  <g>
                    <rect x={x} y={y} width={width} height={height} fill={color} rx={3} stroke="#fff" strokeWidth={2} opacity={opacity} />
                    {width > 60 && height > 28 && (
                      <text x={x + width / 2} y={y + height / 2} textAnchor="middle" dominantBaseline="middle"
                        fill="#fff" fontSize={Math.min(12, width / 6)} fontWeight={600} opacity={opacity}>{name}</text>
                    )}
                    {width > 60 && height > 44 && (
                      <text x={x + width / 2} y={y + height / 2 + 14} textAnchor="middle" dominantBaseline="middle"
                        fill="rgba(255,255,255,0.75)" fontSize={10} opacity={opacity}>{(value * 100).toFixed(1)}%</text>
                    )}
                  </g>
                )
              }}>
              <Tooltip content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const d = payload[0]?.payload
                return (
                  <div style={{ background: '#fff', border: '1px solid var(--border2)', borderRadius: 8, padding: '10px 14px', fontSize: 12, boxShadow: '0 4px 20px rgba(37,99,235,0.12)' }}>
                    <div style={{ fontWeight: 700, color: d?.color, marginBottom: 4 }}>{d?.name}</div>
                    <div style={{ color: 'var(--text2)' }}>Share: <strong>{(d?.value * 100).toFixed(1)}%</strong></div>
                    <div style={{ color: 'var(--text3)' }}>Features: {d?.count}</div>
                  </div>
                )
              }} />
            </Treemap>
          </ResponsiveContainer>}
        </SectionCard>
      </div>

      {/* Feature group detail cards - simplified */}
      <SectionCard title="Feature Groups Detail" style={{ marginTop: 20 }}>
        <div className="grid-2">
          {Object.entries(GROUPS).map(([group, test]) => {
            const feats = features.filter(test)
              .map(f => ({ name: f, val: importances?.[f] || 0 }))
              .sort((a, b) => b.val - a.val)
            const color = GROUP_COLOR[group]
            return (
              <div key={group}
                style={{
                  padding: '16px 20px', borderRadius: 10, border: '1px solid var(--border)',
                  background: 'var(--card2)', opacity: !activeGroup || activeGroup === group ? 1 : 0.35,
                  transition: 'opacity 0.15s',
                }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: color, marginBottom: 8 }}>
                  {group} — {feats.length} features
                </div>
                {GROUP_DESC[group] && (
                  <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 12 }}>{GROUP_DESC[group]}</div>
                )}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                  {feats.length
                    ? feats.slice(0, 8).map(({ name, val }) => (
                      <span key={name}
                        onClick={() => setFeat(p => p === name ? null : name)}
                        style={{
                          padding: '2px 9px', borderRadius: 4, fontSize: 10.5, fontWeight: 600,
                          cursor: 'pointer', border: `1px solid ${color}30`,
                          background: selectedFeat === name ? color : color + '12',
                          color: selectedFeat === name ? '#fff' : color,
                          opacity: selectedFeat && selectedFeat !== name ? 0.3 : 1,
                          transition: 'all 0.12s',
                        }}>
                        {name}
                      </span>
                    ))
                    : <span style={{ color: 'var(--text3)', fontSize: 12 }}>None</span>
                  }
                  {feats.length > 8 && (
                    <span style={{ color: 'var(--text3)', fontSize: 10, fontStyle: 'italic' }}>
                      +{feats.length - 8} more
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </SectionCard>
    </>
  )
}
