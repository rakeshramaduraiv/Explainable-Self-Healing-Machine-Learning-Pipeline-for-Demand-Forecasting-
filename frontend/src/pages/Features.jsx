import { useState, useMemo, memo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Cell, RadialBarChart, RadialBar, Legend,
  Treemap,
} from 'recharts'
import { useFetch } from '../api.js'
import { Spinner, ErrorBox, KPI, SectionCard } from '../ui.jsx'

const PALETTE = ['#2563eb','#7c3aed','#0891b2','#059669','#d97706','#dc2626','#6366f1','#10b981','#f59e0b','#ef4444']

const GROUP_COLOR = {
  'Lag':         '#2563eb',
  'Rolling':     '#7c3aed',
  'Temporal':    '#0891b2',
  'Store Stats': '#059669',
  'Interaction': '#d97706',
  'Raw Inputs':  '#dc2626',
}

const GROUPS = {
  'Lag':         f => f.startsWith('Lag_'),
  'Rolling':     f => f.startsWith('Rolling_') || f.startsWith('Momentum_') || f.startsWith('Volatility_'),
  'Temporal':    f => ['Year','Month','Week','Quarter','DayOfYear','Season','Is_Year_End','Is_Year_Start','Is_Q4','Near_Holiday','Week_Sin','Week_Cos','Month_Sin','Month_Cos'].includes(f) || f.startsWith('Weeks_To_'),
  'Store Stats': f => f.startsWith('Store_') || f.startsWith('Sales_vs_'),
  'Interaction': f => ['Temp_Fuel','Price_Index','Fuel_Unemployment','CPI_Fuel','Temp_Holiday','Store_Holiday','Holiday_Q4','Unemployment_CPI'].includes(f),
  'Raw Inputs':  f => ['Holiday_Flag','Temperature','Fuel_Price','CPI','Unemployment'].includes(f),
}

const getGroup = name => Object.keys(GROUPS).find(g => GROUPS[g](name)) || 'Other'

// ── Custom Tooltip ────────────────────────────────────────────────────────────
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

// ── Treemap custom content ────────────────────────────────────────────────────
const TreeContent = ({ x, y, width, height, name, value, color }) => {
  if (width < 30 || height < 20) return <rect x={x} y={y} width={width} height={height} fill={color} rx={3} />
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={color} rx={3} stroke="#fff" strokeWidth={2} />
      {width > 60 && height > 28 && (
        <text x={x + width / 2} y={y + height / 2} textAnchor="middle" dominantBaseline="middle"
          fill="#fff" fontSize={Math.min(12, width / 6)} fontWeight={600}>
          {name}
        </text>
      )}
      {width > 60 && height > 44 && (
        <text x={x + width / 2} y={y + height / 2 + 14} textAnchor="middle" dominantBaseline="middle"
          fill="rgba(255,255,255,0.75)" fontSize={10}>
          {(value * 100).toFixed(1)}%
        </text>
      )}
    </g>
  )
}

export default function Features() {
  const { data: summary, loading: ls, error: es } = useFetch('/api/summary')
  const { data: fiData,   loading: lf, error: ef } = useFetch('/api/feature-importances')
  const [activeGroup, setGroup] = useState(null)
  const [selectedFeat, setFeat] = useState(null)

  const features    = fiData?.feature_names || summary?.feature_names || []
  const importances = fiData?.importances   || null

  // Top 20 sorted
  const top20 = useMemo(() => features
    .map(name => ({ name, value: importances ? +(importances[name] || 0) : 0, group: getGroup(name) }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 20),
  [features, importances])

  // Filtered by group
  const chartData = useMemo(() =>
    activeGroup ? top20.filter(d => d.group === activeGroup) : top20,
  [top20, activeGroup])

  // Group totals for treemap + group bar
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

  // Top 10 for radial
  const radialData = useMemo(() => top20.slice(0, 10).map((d, i) => ({
    name: d.name.length > 18 ? d.name.slice(0, 16) + '…' : d.name,
    fullName: d.name,
    value: +(d.value * 100).toFixed(2),
    fill: PALETTE[i % PALETTE.length],
  })), [top20])

  if (es || ef) return <ErrorBox msg={es || ef} />
  if (ls || lf) return <Spinner />

  const totalImp = top20.reduce((s, d) => s + d.value, 0)

  return (
    <>
      <div className="page-header">
        <div className="page-title">Feature Importance</div>
        <div className="page-sub">{features.length || 60}+ engineered features across 6 groups — click any chart element to inspect</div>
      </div>

      {/* KPIs */}
      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
        <KPI label="Total Features"   value={features.length || 60} delta="Engineered" />
        <KPI label="Feature Groups"   value={6} delta="Categories" />
        <KPI label="Top Feature"      value={top20[0]?.name || '—'} delta={top20[0] ? (top20[0].value * 100).toFixed(1) + '% importance' : ''} />
        <KPI label="Top 20 Coverage"  value={(totalImp * 100).toFixed(1) + '%'} delta="of total importance" />
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
      </div>

      {/* Row 1 — Horizontal Bar (Top 20) + Treemap (Group Share) */}
      <div className="grid-2" style={{ alignItems: 'start' }}>
        <SectionCard title={`Top ${chartData.length} Feature Importance — click bar to inspect`}>
          <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 26)}>
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
                    strokeWidth={1.5}
                    style={{ cursor: 'pointer' }}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

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

        <SectionCard title="Feature Group Share — area proportional to total importance">
          <ResponsiveContainer width="100%" height={300}>
            <Treemap
              data={groupTotals}
              dataKey="value"
              nameKey="name"
              aspectRatio={4 / 3}
              content={<TreeContent />}
            >
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
          </ResponsiveContainer>
        </SectionCard>
      </div>

      {/* Row 2 — Radial Bar (Top 10) + Group Avg Bar */}
      <div className="grid-2">
        <SectionCard title="Top 10 Features — radial importance scale">
          <ResponsiveContainer width="100%" height={320}>
            <RadialBarChart cx="50%" cy="50%" innerRadius={20} outerRadius={140}
              data={radialData} startAngle={180} endAngle={-180}>
              <RadialBar minAngle={4} dataKey="value" cornerRadius={4} label={false} />
              <Tooltip content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const d = payload[0]?.payload
                return (
                  <div style={{ background: '#fff', border: '1px solid var(--border2)', borderRadius: 8, padding: '10px 14px', fontSize: 12, boxShadow: '0 4px 20px rgba(37,99,235,0.12)' }}>
                    <div style={{ fontWeight: 700, color: 'var(--text)', marginBottom: 4 }}>{d?.fullName}</div>
                    <div style={{ color: 'var(--text2)' }}>Importance: <strong>{d?.value}%</strong></div>
                  </div>
                )
              }} />
              <Legend iconSize={8} wrapperStyle={{ fontSize: 10, paddingTop: 8 }}
                formatter={(value, entry) => entry.payload.name} />
            </RadialBarChart>
          </ResponsiveContainer>
        </SectionCard>

        <SectionCard title="Avg Importance by Group — click bar to filter">
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={groupTotals} margin={{ top: 8, right: 16, bottom: 40, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--text2)' }} angle={-25} textAnchor="end" interval={0} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => (v * 100).toFixed(0) + '%'} />
              <Tooltip content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null
                const d = payload[0]?.payload
                return (
                  <div style={{ background: '#fff', border: '1px solid var(--border2)', borderRadius: 8, padding: '10px 14px', fontSize: 12, boxShadow: '0 4px 20px rgba(37,99,235,0.12)' }}>
                    <div style={{ fontWeight: 700, color: d?.color, marginBottom: 4 }}>{label}</div>
                    <div style={{ color: 'var(--text2)' }}>Total share: <strong>{(d?.value * 100).toFixed(1)}%</strong></div>
                    <div style={{ color: 'var(--text3)' }}>{d?.count} features</div>
                  </div>
                )
              }} />
              <Bar dataKey="value" name="Group Share" radius={[4, 4, 0, 0]}
                onClick={d => setGroup(p => p === d.name ? null : d.name)}>
                {groupTotals.map((d, i) => (
                  <Cell key={i}
                    fill={d.color}
                    opacity={activeGroup && activeGroup !== d.name ? 0.2 : 1}
                    stroke={activeGroup === d.name ? '#1e3a8a' : 'none'}
                    strokeWidth={1.5}
                    style={{ cursor: 'pointer' }}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>
      </div>

      {/* Feature group detail cards */}
      <div className="grid-2">
        {Object.entries(GROUPS).map(([group, test]) => {
          const feats = features.filter(test)
            .map(f => ({ name: f, val: importances?.[f] || 0 }))
            .sort((a, b) => b.val - a.val)
          const color = GROUP_COLOR[group]
          return (
            <SectionCard key={group}
              title={`${group} — ${feats.length} features`}
              style={{ opacity: !activeGroup || activeGroup === group ? 1 : 0.35, transition: 'opacity 0.15s' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                {feats.length
                  ? feats.map(({ name, val }) => (
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
              </div>
            </SectionCard>
          )
        })}
      </div>
    </>
  )
}
