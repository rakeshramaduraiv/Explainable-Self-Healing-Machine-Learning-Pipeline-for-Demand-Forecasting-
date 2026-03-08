import { useMemo } from 'react'
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts'
import { useFetch } from '../api.js'
import { Spinner, ErrorBox, KPI, SectionCard, fmtD, CHART_STYLE } from '../ui.jsx'

const fmtM = n => n >= 1e6 ? `$${(n/1e6).toFixed(1)}M` : n >= 1e3 ? `$${(n/1e3).toFixed(1)}K` : `$${n.toFixed(0)}`

export default function Demand() {
  const { data: metrics, loading: lm, error: em } = useFetch('/api/demand-metrics')
  const { data: trend,   loading: lt, error: et } = useFetch('/api/demand-trend')
  const { data: monthly, loading: lmo }           = useFetch('/api/monthly-demand')
  const { data: store,   loading: ls }            = useFetch('/api/store-demand')

  const trendData   = useMemo(() => (trend?.dates || []).map((d, i) => ({ date: d, sales: trend.demand[i] })), [trend])
  const monthlyData = useMemo(() => (monthly?.months || []).map((m, i) => ({ month: m, sales: monthly.demand[i] })), [monthly])
  const storeData   = useMemo(() => (store?.stores || []).map((s, i) => ({ store: s, sales: store.demand[i] })), [store])

  if (em || et) return <ErrorBox msg={em || et} />
  if (lm || lt) return <Spinner />

  const growth = metrics?.demand_growth_rate ?? 0

  return (
    <>
      <div className="page-header">
        <div className="page-title">Demand Insights</div>
        <div className="page-sub">Demand metrics · trends · store analysis</div>
      </div>

      <div className="kpi-grid">
        <KPI label="Avg Weekly Demand" value={fmtM(metrics?.avg_weekly_demand ?? 0)} />
        <KPI label="Growth Rate (MoM)"  value={`${growth >= 0 ? '+' : ''}${growth.toFixed(1)}%`}
          color={growth > 5 ? 'var(--green)' : growth < -5 ? 'var(--red)' : 'var(--text)'} />
        <KPI label="Peak Month"    value={metrics?.peak_demand_month ?? '—'} color="var(--green)" />
        <KPI label="Lowest Month"  value={metrics?.lowest_demand_month ?? '—'} color="var(--orange)" />
        <KPI label="Total Demand"  value={fmtM(metrics?.total_demand ?? 0)} />
      </div>

      <div className="grid-2">
        <SectionCard title="Demand Trend Over Time">
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={trendData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="gDemand" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="var(--blue)" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="var(--blue)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v/1000).toFixed(0) + 'K'} />
              <Tooltip {...CHART_STYLE} formatter={v => [fmtD(v), 'Weekly Sales']} />
              <Area type="monotone" dataKey="sales" stroke="var(--blue)" fill="url(#gDemand)" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </SectionCard>

        <SectionCard title="Monthly Demand Aggregation">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={monthlyData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v/1000).toFixed(0) + 'K'} />
              <Tooltip {...CHART_STYLE} formatter={v => [fmtD(v), 'Total Sales']} />
              <Bar dataKey="sales" fill="var(--orange)" radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>
      </div>

      {storeData.length > 0 && (
        <SectionCard title="Store-Level Demand">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={storeData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="store" tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v/1000).toFixed(0) + 'K'} />
              <Tooltip {...CHART_STYLE} formatter={v => [fmtD(v), 'Total Sales']} />
              <Bar dataKey="sales" fill="var(--green)" radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>
      )}

      <SectionCard title="Key Insights">
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <div className={`alert ${growth > 5 ? 'alert-g' : growth < -5 ? 'alert-r' : 'alert-b'}`} style={{ flex: 1, minWidth: 200 }}>
            {growth > 5 ? '📈 Strong growth' : growth < -5 ? '📉 Declining demand' : '📊 Stable demand'} — {growth >= 0 ? '+' : ''}{growth.toFixed(1)}% MoM
          </div>
          {storeData.length > 0 && (
            <div className="alert alert-g" style={{ flex: 1, minWidth: 200 }}>
              🏪 Top store: <strong>{storeData[0]?.store}</strong> — {fmtM(storeData[0]?.sales ?? 0)} total
            </div>
          )}
        </div>
      </SectionCard>
    </>
  )
}
