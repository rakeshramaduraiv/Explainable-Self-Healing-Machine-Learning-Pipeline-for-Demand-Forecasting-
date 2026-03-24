import { useMemo, useState, useCallback } from 'react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend, Cell, PieChart, Pie,
  ComposedChart, Line, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts'
import { useFetch } from '../api.js'
import { ErrorBox, KPI, SectionCard, fmtD, CHART_STYLE } from '../ui.jsx'

const PALETTE = ['#3b82f6','#6366f1','#8b5cf6','#10b981','#f59e0b','#ef4444','#60a5fa','#34d399','#06b6d4','#a78bfa','#f472b6','#fb923c','#4ade80','#818cf8','#e879f9']

const toId = p => {
  if (typeof p === 'number') return p
  const n = parseInt(String(p).replace(/\D/g, ''), 10)
  return isNaN(n) ? p : n
}
const pName = (id, names) => names?.[String(id)] || `Product ${id}`

const Skel = ({ h }) => <div className="skel" style={{ height: h, borderRadius: 8 }} />

export default function Demand() {
  const { data: metrics, error: em }        = useFetch('/api/demand-metrics',  { pollMs: 120_000 })
  const { data: monthly,  loading: lmo }    = useFetch('/api/monthly-demand',   { pollMs: 120_000 })
  const { data: prodData, loading: lpd }    = useFetch('/api/product-demand',   { pollMs: 120_000 })
  const { data: prodForecast, loading: lpf }= useFetch('/api/product-forecast', { pollMs: 120_000 })
  const { data: prodMonthly }               = useFetch('/api/product-monthly',  { pollMs: 120_000 })
  const { data: datasets }                  = useFetch('/api/datasets',          { pollMs: 120_000 })
  const { data: productNames }              = useFetch('/api/product-names',     { pollMs: 300_000 })
  const { data: storeForecast }             = useFetch('/api/store-forecast',    { pollMs: 300_000 })
  const { data: storeMonthly }              = useFetch('/api/store-monthly',     { pollMs: 300_000 })
  const { data: storeNames }                = useFetch('/api/store-names',       { pollMs: 300_000 })

  const [selectedProduct, setProduct] = useState(null)
  const [selectedStore,   setStore]   = useState(null)
  const toggleProduct = useCallback(id => setProduct(prev => prev === id ? null : id), [])
  const toggleStore   = useCallback(id => { setStore(prev => prev === id ? null : id); setProduct(null) }, [])

  // All unique stores
  const stores = useMemo(() => {
    if (!storeForecast?.length) return []
    return [...new Set(storeForecast.map(d => d.Store))].sort((a, b) => a - b)
  }, [storeForecast])

  // Active forecast — store-filtered or global
  const activeForecast = useMemo(() => {
    if (selectedStore == null || !storeForecast?.length) return prodForecast || []
    const rows = storeForecast.filter(d => d.Store === selectedStore)
    const byProduct = {}
    rows.forEach(d => {
      if (!byProduct[d.Product]) byProduct[d.Product] = { ...d }
    })
    return Object.values(byProduct)
  }, [selectedStore, storeForecast, prodForecast])

  // Monthly chart — store-filtered or global
  const monthlyData = useMemo(() => {
    if (selectedStore != null && storeMonthly?.length) {
      return storeMonthly
        .filter(d => d.Store === selectedStore)
        .sort((a, b) => a.month.localeCompare(b.month))
        .map(d => ({ month: d.month, demand: Math.round(d.demand) }))
    }
    return (monthly?.months || []).map((m, i) => ({ month: m, demand: monthly.demand[i] }))
  }, [selectedStore, storeMonthly, monthly])

  // Product demand (global — /api/product-demand doesn't have store breakdown)
  const productData = useMemo(() => {
    if (!prodData?.products?.length) return []
    return prodData.products.map((p, i) => {
      const id = toId(p)
      return { id, name: pName(id, productNames), demand: prodData.demand[i] ?? 0 }
    }).sort((a, b) => b.demand - a.demand)
  }, [prodData, productNames])

  // Pie chart
  const pieData = useMemo(() => {
    const total = productData.reduce((s, d) => s + d.demand, 0) || 1
    return productData.map((d, i) => ({
      name: d.name, id: d.id, value: d.demand,
      pct: +((d.demand / total) * 100).toFixed(1),
      fill: PALETTE[i % PALETTE.length],
    }))
  }, [productData])

  // Demand vs Forecast — uses activeForecast (store-filtered if store selected)
  const demandVsForecast = useMemo(() => {
    if (!activeForecast?.length) return []
    return activeForecast
      .slice().sort((a, b) => b.avg_demand - a.avg_demand)
      .map((d, i) => ({
        name:           d.name || pName(d.Product, productNames),
        Product:        d.Product,
        'Avg Demand':   Math.round(d.avg_demand    ?? 0),
        'Avg Forecast': Math.round(d.avg_predicted ?? 0),
        Accuracy:       Math.round(d.accuracy      ?? 0),
        fill:           PALETTE[i % PALETTE.length],
      }))
  }, [activeForecast, productNames])

  // Radar — uses activeForecast
  const radarData = useMemo(() => {
    if (!activeForecast?.length) return []
    const sorted    = activeForecast.slice(0, 10).sort((a, b) => b.avg_demand - a.avg_demand)
    const maxDemand = Math.max(...sorted.map(d => d.avg_demand), 1)
    return sorted.map(d => ({
      name:     d.name || pName(d.Product, productNames),
      Demand:   +((d.avg_demand / maxDemand) * 100).toFixed(1),
      Accuracy: Math.round(d.accuracy ?? 0),
    }))
  }, [activeForecast, productNames])

  // Heatmap
  const heatmapData = useMemo(() => {
    if (!prodMonthly?.length) return { months: [], products: [], grid: [] }
    const months = [...new Set(prodMonthly.map(d => d.month))].sort()
    const prods  = [...new Set(prodMonthly.map(d => d.Product))].sort((a, b) => a - b)
    const grid   = prods.map(p => {
      const row = { product: pName(p, productNames), Product: p }
      prodMonthly.filter(d => d.Product === p).forEach(d => { row[d.month] = Math.round(d.demand ?? 0) })
      return row
    })
    return { months, products: prods, grid }
  }, [prodMonthly, productNames])

  // Selected product monthly trend
  const selectedTrend = useMemo(() => {
    if (selectedProduct == null || !prodMonthly?.length) return []
    return prodMonthly
      .filter(d => Number(d.Product) === Number(selectedProduct))
      .sort((a, b) => String(a.month).localeCompare(String(b.month)))
      .map(d => ({
        month:    d.month,
        Actual:   d.demand    != null ? Math.round(d.demand)    : null,
        Forecast: d.predicted != null ? Math.round(d.predicted) : null,
      }))
  }, [selectedProduct, prodMonthly])

  if (em) return <ErrorBox msg={em} />

  const lp         = lpd || lpf
  const inspection = datasets?.inspection
  const growth     = metrics?.demand_growth_rate ?? 0
  const topProduct = productData[0]
  const bottomProduct = productData[productData.length - 1]
  const storeLabel = selectedStore != null
    ? (storeNames?.[String(selectedStore)] || `Store ${selectedStore}`)
    : 'All Stores'

  return (
    <>
      <div className="page-header">
        <div className="page-title">Demand Insights</div>
        <div className="page-sub">
          {inspection?.stores ?? stores.length ?? '—'} stores · {inspection?.products ?? productData.length ?? '—'} products · {storeLabel}
        </div>
      </div>

      <div className="kpi-grid">
        <KPI label="Avg Weekly Demand" value={metrics ? Math.round(metrics.avg_weekly_demand ?? 0).toLocaleString() + ' units' : '—'} />
        <KPI label="Growth Rate"
          value={metrics ? `${growth >= 0 ? '+' : ''}${growth.toFixed(1)}%` : '—'}
          color={growth > 5 ? 'var(--green)' : growth < -5 ? 'var(--red)' : 'var(--text)'}
          trend={metrics ? growth : null} delta="Month over month" />
        <KPI label="Peak Month"   value={metrics?.peak_demand_month ?? '—'} color="var(--green)" />
        <KPI label="Top Product"  value={topProduct?.name ?? '—'} color="var(--blue)"
          delta={topProduct ? fmtD(topProduct.demand) + ' total units' : ''} />
        <KPI label="Stores"       value={inspection?.stores ?? stores.length ?? '—'} delta={storeLabel} />
        <KPI label="Total Demand" value={metrics ? Math.round(metrics.total_demand ?? 0).toLocaleString() + ' units' : '—'} />
      </div>

      {/* Store selector */}
      {stores.length > 0 && (
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 12, alignItems: 'center', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 12px' }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginRight: 4 }}>Store</span>
          <button className={`btn ${selectedStore == null ? 'btn-primary' : 'btn-outline'}`}
            style={{ padding: '3px 10px', fontSize: 11 }}
            onClick={() => { setStore(null); setProduct(null) }}>All</button>
          {stores.map(s => (
            <button key={s}
              className={`btn ${selectedStore === s ? 'btn-primary' : 'btn-outline'}`}
              style={{ padding: '3px 10px', fontSize: 11 }}
              onClick={() => toggleStore(s)}>
              {storeNames?.[String(s)] || `Store ${s}`}
            </button>
          ))}
        </div>
      )}

      {/* Product filter pills */}
      {productData.length > 0 && (
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 12px' }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginRight: 4 }}>Product</span>
          <button className={`btn ${!selectedProduct ? 'btn-primary' : 'btn-outline'}`}
            style={{ padding: '3px 10px', fontSize: 11 }} onClick={() => setProduct(null)}>All</button>
          {productData.map(d => (
            <button key={d.id}
              className={`btn ${selectedProduct === d.id ? 'btn-primary' : 'btn-outline'}`}
              style={{ padding: '3px 10px', fontSize: 11 }}
              onClick={() => toggleProduct(d.id)}>
              {d.name}
            </button>
          ))}
        </div>
      )}

      {/* Selected product monthly trend */}
      {selectedProduct != null && selectedTrend.length > 0 && (
        <SectionCard title={`${pName(selectedProduct, productNames)} — Monthly Actual vs Forecast`}>
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={selectedTrend} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="gSel" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => fmtD(v)} />
              <Tooltip {...CHART_STYLE} formatter={v => [fmtD(v) + ' units']} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="Actual"   stroke="var(--blue)"  fill="url(#gSel)" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="Forecast" stroke="var(--green)" strokeWidth={2} dot={{ r: 3, fill: 'var(--green)' }} strokeDasharray="4 2" />
            </ComposedChart>
          </ResponsiveContainer>
        </SectionCard>
      )}

      <div className="grid-2">
        {/* Avg Demand vs Forecast */}
        <SectionCard title={`Avg Demand vs Forecast by Product — ${storeLabel}`}>
          {lp ? <Skel h={350} /> : demandVsForecast.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>No forecast data available</div>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(280, demandVsForecast.length * 28)}>
              <BarChart data={demandVsForecast} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 110 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" />
                <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={v => fmtD(v)} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={110} />
                <Tooltip {...CHART_STYLE} formatter={v => [fmtD(v) + ' units']} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="Avg Demand"   fill="var(--blue)"  radius={[0, 4, 4, 0]} barSize={9}
                  onClick={d => toggleProduct(d.Product)} style={{ cursor: 'pointer' }} />
                <Bar dataKey="Avg Forecast" fill="var(--green)" radius={[0, 4, 4, 0]} barSize={9} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </SectionCard>

        {/* Demand Share Pie */}
        <SectionCard title="Product Demand Share">
          {lp ? <Skel h={280} /> : pieData.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>No data available</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                  outerRadius={100} innerRadius={45} paddingAngle={1} strokeWidth={2} stroke="#fff"
                  onClick={d => toggleProduct(d.id)} style={{ cursor: 'pointer' }}>
                  {pieData.map((d, i) => (
                    <Cell key={i} fill={d.fill}
                      opacity={selectedProduct != null && selectedProduct !== d.id ? 0.35 : 1} />
                  ))}
                </Pie>
                <Tooltip content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const d = payload[0].payload
                  return (
                    <div style={{ background: '#fff', border: '1px solid var(--border2)', borderRadius: 8, padding: '10px 14px', fontSize: 12, boxShadow: '0 4px 20px rgba(37,99,235,0.12)' }}>
                      <div style={{ fontWeight: 700, marginBottom: 4 }}>{d.name}</div>
                      <div style={{ color: 'var(--text2)' }}>{fmtD(d.value)} units · {d.pct}%</div>
                    </div>
                  )
                }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </SectionCard>
      </div>

      <div className="grid-2">
        {/* Monthly Demand */}
        <SectionCard title={`Monthly Demand — ${storeLabel}`}>
          {lmo ? <Skel h={230} /> : monthlyData.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>No monthly data available</div>
          ) : (
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={monthlyData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="month" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={v => fmtD(v)} />
                <Tooltip {...CHART_STYLE} formatter={v => [fmtD(v) + ' units', 'Total Demand']} />
                <Bar dataKey="demand" name="Monthly Demand" radius={[4, 4, 0, 0]}>
                  {monthlyData.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </SectionCard>

        {/* Radar */}
        <SectionCard title={`Product Demand & Accuracy Profile — ${storeLabel}`}>
          {!radarData.length ? <Skel h={260} /> : (
            <ResponsiveContainer width="100%" height={260}>
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius={95}>
                <PolarGrid stroke="var(--border)" />
                <PolarAngleAxis dataKey="name" tick={{ fontSize: 9, fill: 'var(--text2)' }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 8 }} tickFormatter={v => v + '%'} />
                <Radar name="Demand (norm %)" dataKey="Demand"   stroke="var(--blue)"  fill="var(--blue)"  fillOpacity={0.12} strokeWidth={2} />
                <Radar name="Accuracy %"      dataKey="Accuracy" stroke="var(--green)" fill="var(--green)" fillOpacity={0.12} strokeWidth={2} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Tooltip {...CHART_STYLE} formatter={v => [v + '%']} />
              </RadarChart>
            </ResponsiveContainer>
          )}
        </SectionCard>
      </div>

      {/* Product × Month Heatmap */}
      {heatmapData.months.length > 0 && (
        <SectionCard title="Product × Month Demand (Avg Weekly Units)">
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Product</th>
                  {heatmapData.months.map(m => <th key={m} style={{ fontSize: 10 }}>{m.slice(5)}</th>)}
                </tr>
              </thead>
              <tbody>
                {heatmapData.grid.map(row => {
                  const vals = heatmapData.months.map(m => row[m] || 0)
                  const max  = Math.max(...vals, 1)
                  return (
                    <tr key={row.Product}
                      onClick={() => toggleProduct(row.Product)}
                      style={{ cursor: 'pointer', background: selectedProduct === row.Product ? 'rgba(59,130,246,0.06)' : undefined }}>
                      <td style={{ color: 'var(--blue)', fontWeight: 600, fontSize: 11, whiteSpace: 'nowrap' }}>{row.product}</td>
                      {heatmapData.months.map(m => {
                        const v         = row[m] || 0
                        const intensity = v / max
                        return (
                          <td key={m} className="mono" style={{
                            fontSize: 10, textAlign: 'center',
                            background: `rgba(59,130,246,${(intensity * 0.28).toFixed(2)})`,
                            color:      intensity > 0.7 ? 'var(--blue)' : 'var(--text2)',
                            fontWeight: intensity > 0.7 ? 600 : 400,
                          }}>{v || '—'}</td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      {/* Key Insights */}
      <SectionCard title="Key Insights">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
          <div style={{ padding: '14px 18px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card2)' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginBottom: 6 }}>Demand Trend</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: growth > 5 ? 'var(--green)' : growth < -5 ? 'var(--red)' : 'var(--blue)' }}>
              {growth >= 0 ? '+' : ''}{growth.toFixed(1)}% MoM
            </div>
            <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>
              {growth > 5 ? 'Strong growth' : growth < -5 ? 'Declining demand' : 'Stable demand'}
            </div>
          </div>
          {topProduct && (
            <div style={{ padding: '14px 18px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card2)' }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginBottom: 6 }}>Highest Demand</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--blue)' }}>{topProduct.name}</div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>{fmtD(topProduct.demand)} total units</div>
            </div>
          )}
          {bottomProduct && bottomProduct !== topProduct && (
            <div style={{ padding: '14px 18px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card2)' }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginBottom: 6 }}>Lowest Demand</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--orange)' }}>{bottomProduct.name}</div>
              <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>{fmtD(bottomProduct.demand)} total units</div>
            </div>
          )}
          <div style={{ padding: '14px 18px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card2)' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginBottom: 6 }}>Dataset</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>{inspection?.rows?.toLocaleString() ?? '—'} rows</div>
            <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 4 }}>{inspection?.stores ?? stores.length} stores · {inspection?.products ?? productData.length} products</div>
          </div>
        </div>
      </SectionCard>
    </>
  )
}
