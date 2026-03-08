import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ScatterChart, Scatter, ZAxis, Cell, Legend } from 'recharts'
import { useFetch } from '../api.js'
import { SkeletonCard, ErrorBox, KPI, SectionCard, fmtD, CHART_STYLE } from '../ui.jsx'
import { SlicerPanel, useSlicerStore, slicerActions } from '../slicer.jsx'

const PALETTE = ['#3b82f6','#6366f1','#8b5cf6','#10b981','#f59e0b','#ef4444','#60a5fa','#34d399']

export default function StoreStats() {
  const { data, loading, error, reload } = useFetch('/api/store-stats')
  const slicer = useSlicerStore()

  const sorted   = useMemo(() => (data||[]).slice().sort((a,b)=>a.mae-b.mae), [data])
  const storeIds = useMemo(() => sorted.map(d => d.Store), [sorted])

  const filtered = useMemo(() =>
    slicer.stores.length ? sorted.filter(d => slicer.stores.includes(d.Store)) : sorted,
  [sorted, slicer.stores])

  const isActive = d => !slicer.stores.length || slicer.stores.includes(d.Store)

  const top5   = filtered.slice(0, 5)
  const bot5   = [...filtered].reverse().slice(0, 5)
  const avgMAE = filtered.length ? (filtered.reduce((s,d)=>s+d.mae,0)/filtered.length).toFixed(0) : null

  if (error)   return <ErrorBox msg={error} onRetry={reload} />
  if (loading) return <><SkeletonCard rows={4} /><SkeletonCard rows={6} /></>

  const onBarClick = e => { if (e?.activePayload?.[0]) slicerActions.toggleStore(e.activePayload[0].payload.Store) }

  return (
    <>
      <div className="page-header">
        <div className="page-title">Store Analytics</div>
        <div className="page-sub">Per-store MAE and prediction accuracy — click any bar or scatter point to filter</div>
      </div>

      <SlicerPanel stores={storeIds} slicer={slicer} />

      <div className="kpi-grid" style={{ gridTemplateColumns:'repeat(4,1fr)' }}>
        <KPI label="Stores Shown"    value={filtered.length} delta={filtered.length!==sorted.length?`of ${sorted.length}`:'all'} />
        <KPI label="Avg Store MAE"   value={avgMAE ? '$'+Number(avgMAE).toLocaleString() : '—'} />
        <KPI label="Best Store MAE"  value={top5[0]?`Store ${top5[0].Store}`:'—'} color="var(--green)" delta={top5[0]?fmtD(top5[0].mae):''} />
        <KPI label="Worst Store MAE" value={bot5[0]?`Store ${bot5[0].Store}`:'—'} color="var(--red)"   delta={bot5[0]?fmtD(bot5[0].mae):''} />
      </div>

      <SectionCard title="MAE by Store — click bar to filter">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={sorted} margin={{ top:4, right:8, bottom:0, left:0 }} onClick={onBarClick}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="Store" tick={{ fontSize:9 }} />
            <YAxis tick={{ fontSize:10 }} tickFormatter={v => '$'+(v/1000).toFixed(0)+'K'} />
            <Tooltip {...CHART_STYLE} formatter={v => ['$'+Number(v).toLocaleString(),'MAE']} labelFormatter={l => `Store ${l}`} />
            <Bar dataKey="mae" name="MAE" radius={[3,3,0,0]}>
              {sorted.map((d,i) => (
                <Cell key={i}
                  fill={PALETTE[i % PALETTE.length]}
                  opacity={isActive(d) ? 1 : 0.15}
                  stroke={slicer.stores.includes(d.Store) ? '#fff' : 'none'}
                  strokeWidth={1.5}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </SectionCard>

      <div className="grid-2">
        <SectionCard title="Avg Sales vs MAE — click point to filter">
          <ResponsiveContainer width="100%" height={240}>
            <ScatterChart margin={{ top:4, right:16, bottom:16, left:0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="avg_sales" name="Avg Sales" tick={{ fontSize:10 }}
                tickFormatter={v => '$'+(v/1000).toFixed(0)+'K'}
                label={{ value:'Avg Weekly Sales', position:'insideBottom', offset:-8, fill:'var(--text3)', fontSize:10 }} />
              <YAxis dataKey="mae" name="MAE" tick={{ fontSize:10 }}
                tickFormatter={v => '$'+(v/1000).toFixed(0)+'K'} />
              <ZAxis range={[50,50]} />
              <Tooltip cursor={{ strokeDasharray:'3 3' }}
                content={({ payload }) => payload?.length ? (
                  <div style={{ background:'var(--card)', border:'1px solid var(--border)', padding:'8px 12px', borderRadius:6, fontSize:12 }}>
                    <div style={{ fontWeight:700, color:'var(--text)' }}>Store {payload[0]?.payload?.Store}</div>
                    <div style={{ color:'var(--text2)' }}>MAE: {fmtD(payload[0]?.payload?.mae)}</div>
                    <div style={{ color:'var(--text2)' }}>Avg Sales: {fmtD(payload[0]?.payload?.avg_sales)}</div>
                  </div>
                ) : null}
              />
              <Scatter data={sorted} onClick={d => slicerActions.toggleStore(d.Store)}>
                {sorted.map((d,i) => (
                  <Cell key={i}
                    fill={slicer.stores.includes(d.Store) ? 'var(--blue)' : PALETTE[i%PALETTE.length]}
                    fillOpacity={isActive(d) ? 0.85 : 0.15}
                    style={{ cursor:'pointer' }}
                  />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </SectionCard>

        <div>
          <SectionCard title={`Best Stores${slicer.stores.length?' (filtered)':''}`}>
            <table className="tbl">
              <thead><tr><th>Store</th><th>MAE</th><th>Avg Sales</th><th>Samples</th></tr></thead>
              <tbody>
                {top5.map(d => (
                  <tr key={d.Store} onClick={() => slicerActions.toggleStore(d.Store)}
                    style={{ cursor:'pointer', background: slicer.stores.includes(d.Store)?'rgba(59,130,246,.07)':undefined }}>
                    <td className="mono" style={{ color:'var(--blue)' }}>Store {d.Store}</td>
                    <td style={{ color:'var(--green)' }}>{fmtD(d.mae)}</td>
                    <td className="mono">{fmtD(d.avg_sales)}</td>
                    <td style={{ color:'var(--text3)' }}>{d.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </SectionCard>
          <SectionCard title={`Worst Stores${slicer.stores.length?' (filtered)':''}`}>
            <table className="tbl">
              <thead><tr><th>Store</th><th>MAE</th><th>Avg Sales</th><th>Samples</th></tr></thead>
              <tbody>
                {bot5.map(d => (
                  <tr key={d.Store} onClick={() => slicerActions.toggleStore(d.Store)}
                    style={{ cursor:'pointer', background: slicer.stores.includes(d.Store)?'rgba(59,130,246,.07)':undefined }}>
                    <td className="mono" style={{ color:'var(--blue)' }}>Store {d.Store}</td>
                    <td style={{ color:'var(--red)' }}>{fmtD(d.mae)}</td>
                    <td className="mono">{fmtD(d.avg_sales)}</td>
                    <td style={{ color:'var(--text3)' }}>{d.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </SectionCard>
        </div>
      </div>
    </>
  )
}
