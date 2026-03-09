import { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine, Legend, Brush } from 'recharts'
import { useFetch } from '../api.js'
import { Spinner, ErrorBox, KPI, SectionCard, fmtD, CHART_STYLE } from '../ui.jsx'
import { SlicerPanel, useSlicerStore, slicerActions } from '../slicer.jsx'

export default function Performance() {
  const { data: baseline, loading: lb, error: eb } = useFetch('/api/baseline')
  const { data: drift,    loading: ld, error: ed } = useFetch('/api/drift')
  const { data: summary,  loading: ls, error: es } = useFetch('/api/summary')
  const slicer = useSlicerStore()

  const months = useMemo(() => (drift || []).map(d => d.month), [drift])

  const filtered = useMemo(() =>
    slicer.months.length ? (drift || []).filter(d => slicer.months.includes(d.month)) : (drift || []),
  [drift, slicer.months])

  if (eb || ed || es) return <ErrorBox msg={eb || ed || es} />

  const m = baseline?.train || summary?.train_metrics || {}
  const loading = lb || ld || ls

  const maeTrend = filtered.map(d => ({
    month:          d.month,
    'Test MAE':     d.error_trend?.current_error,
    'Baseline MAE': d.error_trend?.baseline_error,
  }))

  const errorPct = filtered.map(d => ({
    month:     d.month,
    'Error %': d.error_trend?.error_increase ? +(d.error_trend.error_increase * 100).toFixed(1) : 0,
  }))

  const onLineClick = e => { if (e?.activeLabel) slicerActions.toggleMonth(e.activeLabel) }

  const dotProps = (payload, slicer) => ({
    r:           slicer.months.includes(payload.month) ? 5 : 3,
    fill:        slicer.months.includes(payload.month) ? 'var(--blue)' : 'var(--red)',
    stroke:      slicer.months.includes(payload.month) ? '#fff' : 'none',
    strokeWidth: 2,
    style:       { cursor: 'pointer' },
  })

  return (
    <>
      <div className="page-header">
        <div className="page-title">Model Performance</div>
        <div className="page-sub">{m.model || 'Ensemble'} model — evaluated across {drift?.length} test months</div>
      </div>

      <SlicerPanel months={months} slicer={slicer} />

      <div className="kpi-grid">
        {loading ? Array.from({length:5}).map((_,i)=><div key={i} className="kpi"><div className="skel" style={{height:60}}/></div>) : <>
        <KPI label="R²"    value={m.R2?.toFixed(4)}                        delta="Training" />
        <KPI label="MAE"   value={m.MAE   ? fmtD(m.MAE)   : '—'}          delta="Train MAE" />
        <KPI label="RMSE"  value={m.RMSE  ? fmtD(m.RMSE)  : '—'}          delta="Train RMSE" />
        <KPI label="MAPE"  value={m.MAPE  ? m.MAPE.toFixed(2)  + '%' : '—'} delta="Train MAPE" />
        <KPI label="WMAPE" value={m.WMAPE ? m.WMAPE.toFixed(2) + '%' : '—'} delta="Weighted MAPE" />
        </>}
      </div>

      <SectionCard title="MAE Trend — click point to filter month">
        {loading ? <div className="skel" style={{height:270}}/> :
        <ResponsiveContainer width="100%" height={270}>
          <LineChart data={maeTrend} margin={{ top: 4, right: 16, bottom: 24, left: 0 }} onClick={onLineClick}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v / 1000).toFixed(0) + 'K'} />
            <Tooltip {...CHART_STYLE} formatter={v => ['$' + Number(v).toLocaleString()]} />
            <Legend />
            <Line type="monotone" dataKey="Baseline MAE" stroke="var(--green)" strokeWidth={2} dot={false} strokeDasharray="5 3" />
            <Line type="monotone" dataKey="Test MAE"     stroke="var(--red)"   strokeWidth={2}
              dot={({ cx, cy, payload }) => <circle key={cx + cy} cx={cx} cy={cy} {...dotProps(payload, slicer)} />} />
            <Brush dataKey="month" height={22} stroke="var(--border2)" fill="var(--card2)" travellerWidth={6} />
          </LineChart>
        </ResponsiveContainer>}
      </SectionCard>

      <SectionCard title="Error Increase % vs Baseline — click point to filter">
        {loading ? <div className="skel" style={{height:230}}/> :
        <ResponsiveContainer width="100%" height={230}>
          <LineChart data={errorPct} margin={{ top: 4, right: 16, bottom: 0, left: 0 }} onClick={onLineClick}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={v => v + '%'} />
            <Tooltip {...CHART_STYLE} formatter={v => [v + '%', 'Error Increase']} />
            <ReferenceLine y={10} stroke="var(--orange)" strokeDasharray="4 2"
              label={{ value: 'Mild threshold', fill: 'var(--orange)', fontSize: 10, position: 'insideTopRight' }} />
            <Line type="monotone" dataKey="Error %" stroke="var(--red)" strokeWidth={2}
              dot={({ cx, cy, payload }) => <circle key={cx + cy} cx={cx} cy={cy} {...dotProps(payload, slicer)} />} />
          </LineChart>
        </ResponsiveContainer>}
      </SectionCard>

      {summary?.confidence_intervals && (
        <SectionCard title="Confidence Intervals">
          <table className="tbl">
            <tbody>
              {[
                ['Coverage',  summary.confidence_intervals.coverage != null ? (summary.confidence_intervals.coverage * 100).toFixed(0) + '%' : '—'],
                ['Avg Width', summary.confidence_intervals.avg_width != null ? '$' + summary.confidence_intervals.avg_width.toLocaleString(undefined, { maximumFractionDigits: 0 }) : '—'],
              ].map(([k, v]) => (
                <tr key={k}>
                  <td style={{ color: 'var(--text3)', width: 200, fontWeight: 500 }}>{k}</td>
                  <td className="mono">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      )}
    </>
  )
}
