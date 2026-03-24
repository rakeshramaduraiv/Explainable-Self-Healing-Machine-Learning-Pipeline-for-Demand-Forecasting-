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
  const { data: storeForecast, loading: lsf, error: esf } = useFetch('/api/store-forecast', { pollMs: 120000 })
  const { data: storeMonthly, loading: lsm }              = useFetch('/api/store-monthly',  { pollMs: 120000 })
  const { data: storeNames }                               = useFetch('/api/store-names',    { pollMs: 300000 })
  const { data: monthly, loading: l2 }                    = useFetch('/api/monthly-sales',   { pollMs: 60000 })
  const { data: drift }                                    = useFetch('/api/drift',           { pollMs: 60000 })

  const [selectedStore,   setStore]   = useState(null)
  const [selectedProduct, setProduct] = useState(null)

  // All unique stores sorted
  const stores = useMemo(() => {
    if (!storeForecast?.length) return []
    return [...new Set(storeForecast.map(d => d.Store))].sort((a, b) => a - b)
  }, [storeForecast])

  // Filter by selected store, then aggregate by product
  const filtered = useMemo(() => {
    if (!storeForecast?.length) return []
    const rows = selectedStore != null
      ? storeForecast.filter(d => d.Store === selectedStore)
      : storeForecast
    // Aggregate across stores per product
    const byProduct = {}
    rows.forEach(d => {
      if (!byProduct[d.Product]) byProduct[d.Product] = { Product: d.Product, name: d.name, mae: [], mape: [], avg_demand: [], avg_predicted: [], count: 0 }
      byProduct[d.Product].mae.push(d.mae)
      byProduct[d.Product].mape.push(d.mape)
      byProduct[d.Product].avg_demand.push(d.avg_demand)
      byProduct[d.Product].avg_predicted.push(d.avg_predicted)
      byProduct[d.Product].count += d.count
    })
    return Object.values(byProduct).map(d => ({
      Product: d.Product,
      name: d.name,
      mae: +(d.mae.reduce((s, v) => s + v, 0) / d.mae.length).toFixed(2),
      mape: +(d.mape.reduce((s, v) => s + v, 0) / d.mape.length).toFixed(2),
      avg_demand: +(d.avg_demand.reduce((s, v) => s + v, 0) / d.avg_demand.length).toFixed(2),
      avg_predicted: +(d.avg_predicted.reduce((s, v) => s + v, 0) / d.avg_predicted.length).toFixed(2),
      accuracy: +(100 - d.mape.reduce((s, v) => s + v, 0) / d.mape.length).toFixed(2),
      count: d.count,
    })).sort((a, b) => b.avg_demand - a.avg_demand)
  }, [storeForecast, selectedStore])

  // Monthly chart — filter by store if selected
  const forecastData = useMemo(() => {
    if (selectedStore != null && storeMonthly?.length) {
      const rows = storeMonthly.filter(d => d.Store === selectedStore)
      return rows.sort((a, b) => a.month.localeCompare(b.month)).map(d => ({
        month: d.month,
        'Test Set': Math.round(d.demand),
        'Forecast': Math.round(d.predicted),
      }))
    }
    return (monthly || []).map(d => ({
      month: d.month,
      'Test Set': d.actual    != null ? Math.round(d.actual)    : null,
      'Forecast': d.predicted != null ? Math.round(d.predicted) : null,
    }))
  }, [selectedStore, storeMonthly, monthly])

  // Live KPI metrics from filtered products
  const live = useMemo(() => {
    if (!filtered.length) return null
    const mae  = filtered.reduce((s, d) => s + d.mae,  0) / filtered.length
    const mape = filtered.reduce((s, d) => s + d.mape, 0) / filtered.length
    return { mae: Math.round(mae), mape: Math.round(mape), accuracy: Math.round(100 - mape) }
  }, [filtered])

  const productMAE = useMemo(() => filtered.map((d, i) => ({
    name: d.name, product: d.Product,
    MAE: Math.round(d.mae),
    Accuracy: Math.round(d.accuracy),
    fill: PALETTE[i % PALETTE.length],
  })), [filtered])

  const radarData = useMemo(() => filtered.slice(0, 8).map(d => ({
    name: d.name.length > 14 ? d.name.slice(0, 12) + '…' : d.name,
    Accuracy: Math.round(d.accuracy),
  })), [filtered])

  const severeCount = drift?.filter(d => d.severity === 'severe').length ?? 0

  if (esf) return <ErrorBox msg={esf} />

  const storeLabel = selectedStore != null
    ? (storeNames?.[String(selectedStore)] || `Store ${selectedStore}`)
    : 'All Stores'

  return (
    <>
      <div className="page-header">
        <div className="page-title">Product Demand Forecasting</div>
        <div className="page-sub">{stores.length} stores · {filtered.length} products · {storeLabel}</div>
      </div>

      <div className="kpi-grid">
        {lsf || l2
          ? Array.from({ length: 6 }).map((_, i) => <div key={i} className="kpi"><Skel h={60} /></div>)
          : <>
            <KPI label="Forecast Accuracy" value={live ? live.accuracy + '%' : '—'} color="var(--green)" delta={storeLabel} />
            <KPI label="MAE"               value={live ? live.mae + ' units' : '—'} delta={storeLabel} />
            <KPI label="MAPE"              value={live ? live.mape + '%' : '—'}     delta={storeLabel} />
            <KPI label="Stores"            value={stores.length || '—'} delta={selectedStore != null ? `Viewing ${storeLabel}` : 'All stores'} />
            <KPI label="Products"          value={filtered.length || '—'} />
            <KPI label="Severe Drift"      value={severeCount} color={severeCount ? 'var(--red)' : undefined} delta="test months" />
          </>
        }
      </div>

      {/* ── Store selector ── */}
      {stores.length > 0 && (
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 12, alignItems: 'center', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 12px' }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginRight: 4 }}>Store</span>
          <button
            className={`btn ${selectedStore == null ? 'btn-primary' : 'btn-outline'}`}
            style={{ padding: '3px 10px', fontSize: 11 }}
            onClick={() => { setStore(null); setProduct(null) }}>
            All
          </button>
          {stores.map(s => (
            <button key={s}
              className={`btn ${selectedStore === s ? 'btn-primary' : 'btn-outline'}`}
              style={{ padding: '3px 10px', fontSize: 11 }}
              onClick={() => { setStore(prev => prev === s ? null : s); setProduct(null) }}>
              {storeNames?.[String(s)] || `Store ${s}`}
            </button>
          ))}
        </div>
      )}

      {/* ── Product filter pills ── */}
      {filtered.length > 0 && (
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 12px' }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginRight: 4 }}>Product</span>
          <button className={`btn ${!selectedProduct ? 'btn-primary' : 'btn-outline'}`}
            style={{ padding: '3px 10px', fontSize: 11 }} onClick={() => setProduct(null)}>All</button>
          {filtered.map(d => (
            <button key={d.Product}
              className={`btn ${selectedProduct === d.Product ? 'btn-primary' : 'btn-outline'}`}
              style={{ padding: '3px 10px', fontSize: 11 }}
              onClick={() => setProduct(prev => prev === d.Product ? null : d.Product)}>
              {d.name}
            </button>
          ))}
        </div>
      )}

      {/* ── Monthly Forecast vs Test Set ── */}
      <SectionCard title={`Monthly Forecast vs Test Set — ${storeLabel}`}>
        {l2 || lsm ? <Skel h={260} /> :
        <ResponsiveContainer width="100%" height={260}>
          <ComposedChart data={forecastData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="gFact" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip {...CHART_STYLE} formatter={v => [Number(v).toLocaleString() + ' units']} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Area type="monotone" dataKey="Test Set" stroke="var(--blue)"  fill="url(#gFact)" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="Forecast"  stroke="var(--green)" strokeWidth={2} dot={{ r: 3, fill: 'var(--green)' }} />
          </ComposedChart>
        </ResponsiveContainer>}
      </SectionCard>

      <div className="grid-2">
        {/* Product Accuracy */}
        <SectionCard title={`Forecast Accuracy by Product — ${storeLabel}`}>
          {lsf ? <Skel h={Math.max(230, filtered.length * 26)} /> :
          <ResponsiveContainer width="100%" height={Math.max(230, filtered.length * 26)}>
            <BarChart data={productMAE} layout="vertical" margin={{ top: 4, right: 40, bottom: 0, left: 120 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10 }} domain={[0, 100]} tickFormatter={v => v + '%'} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={120} />
              <Tooltip {...CHART_STYLE} formatter={v => [v + '%']} />
              <Bar dataKey="Accuracy" radius={[0, 4, 4, 0]}
                onClick={d => setProduct(prev => prev === d.product ? null : d.product)}>
                {productMAE.map((d, i) => (
                  <Cell key={i}
                    fill={d.Accuracy >= 95 ? 'var(--green)' : d.Accuracy >= 90 ? 'var(--blue)' : 'var(--orange)'}
                    opacity={selectedProduct && selectedProduct !== d.product ? 0.25 : 1}
                    style={{ cursor: 'pointer' }} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>}
        </SectionCard>

        {/* Product MAE */}
        <SectionCard title={`MAE by Product — ${storeLabel}`}>
          {lsf ? <Skel h={230} /> :
          <ResponsiveContainer width="100%" height={Math.max(230, filtered.length * 26)}>
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
      </div>

      {/* Radar */}
      <SectionCard title={`Product Accuracy Radar — ${storeLabel}`}>
        {lsf ? <Skel h={280} /> :
        <ResponsiveContainer width="100%" height={280}>
          <RadarChart data={radarData} cx="50%" cy="50%" outerRadius={100}>
            <PolarGrid stroke="var(--border)" />
            <PolarAngleAxis dataKey="name" tick={{ fontSize: 9, fill: 'var(--text2)' }} />
            <PolarRadiusAxis tick={{ fontSize: 9 }} domain={[0, 100]} tickFormatter={v => v + '%'} />
            <Radar name="Accuracy %" dataKey="Accuracy" stroke="var(--blue)" fill="var(--blue)" fillOpacity={0.15} strokeWidth={2} />
          </RadarChart>
        </ResponsiveContainer>}
      </SectionCard>

      {/* Product detail table */}
      <SectionCard title={`Product Forecast Performance — ${storeLabel}`}>
        {lsf ? <Skel h={200} /> :
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr><th>#</th><th>Product</th><th>Avg Demand</th><th>Avg Forecast</th><th>MAE</th><th>MAPE</th><th>Accuracy</th><th>Quality</th></tr>
            </thead>
            <tbody>
              {filtered.map((d, i) => {
                const q = d.accuracy >= 98 ? { l: 'Excellent', c: 'b-green' }
                        : d.accuracy >= 95 ? { l: 'Good',      c: 'b-blue'  }
                        : d.accuracy >= 90 ? { l: 'Fair',      c: 'b-orange'}
                        :                    { l: 'Poor',       c: 'b-red'   }
                return (
                  <tr key={d.Product}
                    onClick={() => setProduct(prev => prev === d.Product ? null : d.Product)}
                    style={{ cursor: 'pointer', background: selectedProduct === d.Product ? 'rgba(59,130,246,0.06)' : undefined }}>
                    <td className="mono" style={{ color: 'var(--text3)' }}>{d.Product}</td>
                    <td style={{ color: 'var(--blue)', fontWeight: 600 }}>{d.name}</td>
                    <td className="mono">{Math.round(d.avg_demand).toLocaleString()} units</td>
                    <td className="mono">{Math.round(d.avg_predicted).toLocaleString()} units</td>
                    <td className="mono">{d.mae.toFixed(1)} units</td>
                    <td className="mono">{d.mape.toFixed(1)}%</td>
                    <td className="mono" style={{ color: q.c === 'b-green' ? 'var(--green)' : q.c === 'b-blue' ? 'var(--blue)' : 'var(--orange)', fontWeight: 600 }}>
                      {d.accuracy.toFixed(1)}%
                    </td>
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
