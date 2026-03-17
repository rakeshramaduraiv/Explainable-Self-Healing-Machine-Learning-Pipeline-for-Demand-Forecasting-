import { useMemo, useState, memo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  ComposedChart, Line, Legend, Cell, Area, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis,
} from 'recharts'
import { useFetch } from '../api.js'
import { ErrorBox, KPI, SectionCard, fmtD, CHART_STYLE } from '../ui.jsx'

const PALETTE = ['#3b82f6','#6366f1','#8b5cf6','#10b981','#f59e0b','#ef4444','#60a5fa','#34d399','#06b6d4','#a78bfa','#f472b6','#fb923c','#4ade80','#818cf8','#e879f9']

const Skel = ({ h }) => <div className="skel" style={{ height: h, borderRadius: 8 }} />

export default function StoreStats() {
  const { data: products, loading: l1, error: e1 } = useFetch('/api/product-forecast', { pollMs: 15000 })
  const { data: monthly, loading: l2 }              = useFetch('/api/monthly-sales', { pollMs: 10000 })
  const { data: prodMonthly }                        = useFetch('/api/product-monthly', { pollMs: 15000 })
  const { data: drift }                              = useFetch('/api/drift', { pollMs: 10000 })
  const [selected, setSelected] = useState(null)

  const sorted = useMemo(() => (products || []).slice().sort((a, b) => b.total_demand - a.total_demand), [products])

  // Live metrics from monthly data
  const live = useMemo(() => {
    if (!monthly?.length) return null
    const valid = monthly.filter(d => d.actual != null && d.predicted != null)
    if (!valid.length) return null
    const mae  = valid.reduce((s, d) => s + Math.abs(d.actual - d.predicted), 0) / valid.length
    const mape = valid.reduce((s, d) => s + (d.actual ? Math.abs(d.actual - d.predicted) / Math.abs(d.actual) * 100 : 0), 0) / valid.length
    return { mae: Math.round(mae), mape: Math.round(mape), accuracy: Math.round(100 - mape), months: valid.length }
  }, [monthly])

  // Monthly forecast vs test set chart
  const forecastData = useMemo(() => (monthly || []).map(d => ({
    month: d.month,
    'Test Set': Math.round(d.actual),
    'Forecast': Math.round(d.predicted),
    Error: d.mae ? Math.round(d.mae) : 0,
  })), [monthly])

  // Product MAE chart
  const productMAE = useMemo(() => sorted.map((d, i) => ({
    name: d.name,
    product: d.Product,
    MAE: Math.round(d.mae),
    'Avg Demand': Math.round(d.avg_demand),
    Accuracy: Math.round(d.accuracy),
    fill: PALETTE[i % PALETTE.length],
  })), [sorted])

  // Accuracy per month
  const accuracyData = useMemo(() => (monthly || []).filter(d => d.actual && d.predicted).map(d => {
    const mape = Math.abs(d.actual - d.predicted) / Math.abs(d.actual) * 100
    return { month: d.month, Accuracy: Math.round(100 - mape), MAPE: +mape.toFixed(1) }
  }), [monthly])

  // Radar data for top products
  const radarData = useMemo(() => sorted.slice(0, 8).map(d => ({
    name: d.name.length > 14 ? d.name.slice(0, 12) + '…' : d.name,
    Accuracy: Math.round(d.accuracy),
    Demand: Math.round(d.avg_demand),
  })), [sorted])

  // Filtered product monthly data
  const filteredMonthly = useMemo(() => {
    if (!prodMonthly?.length) return []
    const data = selected
      ? prodMonthly.filter(d => d.Product === selected)
      : prodMonthly
    const byMonth = {}
    data.forEach(d => {
      if (!byMonth[d.month]) byMonth[d.month] = { month: d.month, demand: 0, predicted: 0, n: 0 }
      byMonth[d.month].demand += d.demand
      byMonth[d.month].predicted += d.predicted
      byMonth[d.month].n++
    })
    return Object.values(byMonth).sort((a, b) => a.month.localeCompare(b.month)).map(d => ({
      month: d.month,
      'Test Set': Math.round(d.demand / d.n),
      Forecast: Math.round(d.predicted / d.n),
    }))
  }, [prodMonthly, selected])

  const severeCount = drift?.filter(d => d.severity === 'severe').length ?? 0

  if (e1) return <ErrorBox msg={e1} />

  return (
    <>
      <div className="page-header">
        <div className="page-title">Product Demand Forecasting</div>
        <div className="page-sub">Store 1 · {sorted.length} products · forecast accuracy by product</div>
      </div>

      <div className="kpi-grid">
        {l1 || l2
          ? Array.from({ length: 6 }).map((_, i) => <div key={i} className="kpi"><Skel h={60} /></div>)
          : <>
            <KPI label="Forecast Accuracy" value={live ? live.accuracy + '%' : '—'} color="var(--green)" delta="Live · test set" />
            <KPI label="MAE" value={live ? live.mae + ' units' : '—'} delta="Live · test set" />
            <KPI label="MAPE" value={live ? live.mape + '%' : '—'} delta="Live · test set" />
            <KPI label="Products" value={sorted.length || '—'} delta="Store 1" />
            <KPI label="Test Months" value={live?.months ?? drift?.length ?? '—'} delta={`${severeCount} severe drift`} color={severeCount ? 'var(--red)' : undefined} />
            <KPI label="Best Product" value={sorted.length ? sorted.reduce((a, b) => a.accuracy > b.accuracy ? a : b).name : '—'} color="var(--green)" delta="Highest accuracy" />
          </>
        }
      </div>

      {/* Product filter pills */}
      {sorted.length > 0 && (
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 12px' }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginRight: 4 }}>Product</span>
          <button className={`btn ${!selected ? 'btn-primary' : 'btn-outline'}`}
            style={{ padding: '3px 10px', fontSize: 11 }} onClick={() => setSelected(null)}>All</button>
          {sorted.map((d, i) => (
            <button key={d.Product} className={`btn ${selected === d.Product ? 'btn-primary' : 'btn-outline'}`}
              style={{ padding: '3px 10px', fontSize: 11 }}
              onClick={() => setSelected(prev => prev === d.Product ? null : d.Product)}>
              {d.name}
            </button>
          ))}
        </div>
      )}

      {/* Forecast vs Test Set */}
      <SectionCard title={selected ? `${sorted.find(d => d.Product === selected)?.name} — Monthly Forecast vs Test Set` : 'Monthly Forecast vs Test Set (All Products Avg)'}>
        {l2 ? <Skel h={260} /> :
        <ResponsiveContainer width="100%" height={260}>
          <ComposedChart data={selected ? filteredMonthly : forecastData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="gFact" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip {...CHART_STYLE} formatter={v => [Number(v).toLocaleString() + ' units']} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Area type="monotone" dataKey="Test Set" stroke="var(--blue)" fill="url(#gFact)" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="Forecast" stroke="var(--green)" strokeWidth={2} dot={{ r: 3, fill: 'var(--green)' }} />
          </ComposedChart>
        </ResponsiveContainer>}
      </SectionCard>

      <div className="grid-2">
        {/* Product Accuracy */}
        <SectionCard title="Forecast Accuracy by Product">
          {l1 ? <Skel h={Math.max(230, sorted.length * 26)} /> :
          <ResponsiveContainer width="100%" height={Math.max(230, sorted.length * 26)}>
            <BarChart data={productMAE} layout="vertical" margin={{ top: 4, right: 40, bottom: 0, left: 120 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10 }} domain={[0, 100]} tickFormatter={v => v + '%'} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={120} />
              <Tooltip {...CHART_STYLE} formatter={v => [v + '%']} />
              <Bar dataKey="Accuracy" radius={[0, 4, 4, 0]} onClick={d => setSelected(prev => prev === d.product ? null : d.product)}>
                {productMAE.map((d, i) => (
                  <Cell key={i} fill={d.Accuracy >= 95 ? 'var(--green)' : d.Accuracy >= 90 ? 'var(--blue)' : 'var(--orange)'}
                    opacity={selected && selected !== d.product ? 0.25 : 1} style={{ cursor: 'pointer' }} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>}
        </SectionCard>

        {/* Accuracy by Month */}
        <SectionCard title="Forecast Accuracy by Month">
          {l2 ? <Skel h={230} /> :
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={accuracyData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} tickFormatter={v => v + '%'} />
              <Tooltip {...CHART_STYLE} formatter={(v, name) => [name === 'MAPE' ? v + '%' : v + '%']} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="Accuracy" radius={[4, 4, 0, 0]}>
                {accuracyData.map((d, i) => (
                  <Cell key={i} fill={d.Accuracy >= 95 ? 'var(--green)' : d.Accuracy >= 90 ? 'var(--blue)' : 'var(--orange)'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>}
        </SectionCard>
      </div>

      <div className="grid-2">
        {/* Product MAE */}
        <SectionCard title="MAE by Product (units)">
          {l1 ? <Skel h={230} /> :
          <ResponsiveContainer width="100%" height={Math.max(230, sorted.length * 26)}>
            <BarChart data={productMAE} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 120 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={120} />
              <Tooltip {...CHART_STYLE} formatter={v => [v + ' units']} />
              <Bar dataKey="MAE" radius={[0, 4, 4, 0]}>
                {productMAE.map((d, i) => <Cell key={i} fill={d.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>}
        </SectionCard>

        {/* Radar */}
        <SectionCard title="Product Accuracy Radar">
          {l1 ? <Skel h={280} /> :
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius={100}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="name" tick={{ fontSize: 9, fill: 'var(--text2)' }} />
              <PolarRadiusAxis tick={{ fontSize: 9 }} domain={[0, 100]} />
              <Radar name="Accuracy %" dataKey="Accuracy" stroke="var(--blue)" fill="var(--blue)" fillOpacity={0.15} strokeWidth={2} />
            </RadarChart>
          </ResponsiveContainer>}
        </SectionCard>
      </div>

      {/* Product detail table */}
      <SectionCard title="Product Forecast Performance — Store 1">
        {l1 ? <Skel h={200} /> :
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr><th>#</th><th>Product</th><th>Avg Demand</th><th>Avg Forecast</th><th>MAE</th><th>MAPE</th><th>Accuracy</th><th>Samples</th><th>Quality</th></tr>
            </thead>
            <tbody>
              {sorted.map((d, i) => {
                const q = d.accuracy >= 98 ? { l: 'Excellent', c: 'b-green' } : d.accuracy >= 95 ? { l: 'Good', c: 'b-blue' } : d.accuracy >= 90 ? { l: 'Fair', c: 'b-orange' } : { l: 'Poor', c: 'b-red' }
                return (
                  <tr key={d.Product} onClick={() => setSelected(prev => prev === d.Product ? null : d.Product)}
                    style={{ cursor: 'pointer', background: selected === d.Product ? 'rgba(59,130,246,0.06)' : undefined }}>
                    <td className="mono" style={{ color: 'var(--text3)' }}>{d.Product}</td>
                    <td style={{ color: 'var(--blue)', fontWeight: 600 }}>{d.name}</td>
                    <td className="mono">{Math.round(d.avg_demand).toLocaleString()} units</td>
                    <td className="mono">{Math.round(d.avg_predicted).toLocaleString()} units</td>
                    <td className="mono">{d.mae.toFixed(1)} units</td>
                    <td className="mono">{d.mape.toFixed(1)}%</td>
                    <td className="mono" style={{ color: q.c === 'b-green' ? 'var(--green)' : q.c === 'b-blue' ? 'var(--blue)' : 'var(--orange)', fontWeight: 600 }}>
                      {d.accuracy.toFixed(1)}%
                    </td>
                    <td style={{ color: 'var(--text3)' }}>{d.count}</td>
                    <td><span className={`badge ${q.c}`}>{q.l}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>}
      </SectionCard>
    </>
  )
}
