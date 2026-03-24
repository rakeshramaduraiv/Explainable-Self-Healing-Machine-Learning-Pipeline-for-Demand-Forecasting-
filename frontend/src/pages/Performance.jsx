import { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine, Legend, Brush } from 'recharts'
import { useFetch } from '../api.js'
import { Spinner, ErrorBox, KPI, SectionCard, fmtD, CHART_STYLE } from '../ui.jsx'
import { SlicerPanel, useSlicerStore, slicerActions } from '../slicer.jsx'

export default function Performance() {
  const { data: baseline, loading: lb, error: eb } = useFetch('/api/baseline',      { pollMs: 15000 })
  const { data: drift,    loading: ld, error: ed } = useFetch('/api/drift',          { pollMs: 15000 })
  const { data: summary,  loading: ls, error: es } = useFetch('/api/summary',        { pollMs: 15000 })
  const { data: testMetrics }                      = useFetch('/api/test-metrics',   { pollMs: 15000 })
  const slicer = useSlicerStore()

  const months = useMemo(() => (drift || []).map(d => d.month), [drift])

  const filtered = useMemo(() =>
    slicer.months.length ? (drift || []).filter(d => slicer.months.includes(d.month)) : (drift || []),
  [drift, slicer.months])

  if (eb || ed || es) return <ErrorBox msg={eb || ed || es} />

  const m = baseline?.train || summary?.train_metrics || {}
  const loading = (lb && !baseline) || (ld && !drift) || (ls && !summary)
  const live = testMetrics?.mae != null ? testMetrics : null

  // MAE trend: baseline_error vs current_error (raw units, e.g. 1.44 vs 6.56)
  const maeTrend = useMemo(() => filtered.map(d => ({
    month:          d.month,
    'Test MAE':     d.error_trend?.current_error  ?? null,
    'Baseline MAE': d.error_trend?.baseline_error ?? null,
  })), [filtered])

  // Error increase %: error_increase is a ratio (e.g. 3.55 = 355% increase)
  const errorPct = useMemo(() => filtered.map(d => ({
    month:     d.month,
    'Error %': d.error_trend?.error_increase != null
      ? +(d.error_trend.error_increase * 100).toFixed(1)
      : 0,
  })), [filtered])

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
        <div className="page-title">Baseline Performance</div>
        <div className="page-sub">{m.model || 'Ultra-Fast Ensemble'} model — baseline metrics vs {drift?.length} test set months</div>
      </div>

      <SlicerPanel months={months} slicer={slicer} />

      {/* Technical note */}
      <div className="alert alert-g" style={{ marginBottom: 16, fontSize: 11 }}>
        <strong>⚡ Training Optimizations:</strong> 2-fold CV (vs 5), 2 hyperparameter iterations (vs 10), 
        30 RF trees (vs 100), XGBoost hist method, minimal validation splits for 5x faster training
      </div>

      <div className="kpi-grid">
        {loading ? Array.from({length:5}).map((_,i)=><div key={i} className="kpi"><div className="skel" style={{height:60}}/></div>) : <>
        <KPI label="R² (Test 2023)"   value={live?.r2   != null ? live.r2.toFixed(1)   + '%' : (m.R2   != null ? Math.round(m.R2)   + '%' : '—')} delta={live?.n_rows ? `${live.n_rows.toLocaleString()} rows` : 'Train baseline'} />
        <KPI label="MAE (Test 2023)"  value={live?.mae  != null ? live.mae.toFixed(2)  + ' u' : (m.MAE  != null ? Math.round(m.MAE)  + ' u' : '—')} delta={live ? 'Live · test rows' : 'Baseline'} />
        <KPI label="RMSE (Test 2023)" value={live?.rmse != null ? live.rmse.toFixed(2) + ' u' : (m.RMSE != null ? Math.round(m.RMSE) + ' u' : '—')} delta={live ? 'Live · test rows' : 'Baseline'} />
        <KPI label="MAPE (Test 2023)" value={live?.mape != null ? live.mape.toFixed(2) + '%'  : (m.MAPE != null ? Math.round(m.MAPE) + '%'  : '—')} delta={live ? 'Live · test rows' : 'Baseline'} />
        <KPI label="WMAPE"            value={live?.wmape != null ? live.wmape.toFixed(2) + '%' : (m.WMAPE != null ? Math.round(m.WMAPE) + '%' : '—')} delta={live ? 'Live · test rows' : 'Baseline'} />
        </>}
      </div>

      <SectionCard title="Monthly MAE — Test Set 2023 (units)">
        {loading ? <div className="skel" style={{height:270}}/> :
        <ResponsiveContainer width="100%" height={270}>
          <LineChart data={maeTrend} margin={{ top: 4, right: 16, bottom: 24, left: 8 }} onClick={onLineClick}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" tick={{ fontSize: 10 }} tickFormatter={v => v.replace('-', '-')} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={v => v.toFixed(2)} domain={[0, 'auto']} />
            <Tooltip {...CHART_STYLE} formatter={(v, name) => [Number(v).toFixed(2) + ' units', name]} />
            <Legend />
            <Line type="monotone" dataKey="Baseline MAE" stroke="var(--green)" strokeWidth={2} dot={false} strokeDasharray="5 3" />
            <Line type="monotone" dataKey="Test MAE"     stroke="var(--red)"   strokeWidth={2}
              dot={({ cx, cy, payload }) => <circle key={cx+cy} cx={cx} cy={cy} {...dotProps(payload, slicer)} />} />
            <Brush dataKey="month" height={22} stroke="var(--border2)" fill="var(--card2)" travellerWidth={6} />
          </LineChart>
        </ResponsiveContainer>}
      </SectionCard>

      <SectionCard title="Error Increase % — Test Set vs Baseline (2023)">
        {loading ? <div className="skel" style={{height:230}}/> :
        <ResponsiveContainer width="100%" height={230}>
          <LineChart data={errorPct} margin={{ top: 4, right: 16, bottom: 0, left: 8 }} onClick={onLineClick}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="month" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={v => v.toFixed(0) + '%'} domain={[0, 'auto']} />
            <Tooltip {...CHART_STYLE} formatter={(v, name) => [v.toFixed(1) + '%', name]} />
            <ReferenceLine y={10} stroke="var(--orange)" strokeDasharray="4 2"
              label={{ value: 'Mild threshold (10%)', fill: 'var(--orange)', fontSize: 10, position: 'insideTopRight' }} />
            <Line type="monotone" dataKey="Error %" stroke="var(--red)" strokeWidth={2}
              dot={({ cx, cy, payload }) => <circle key={cx+cy} cx={cx} cy={cy} {...dotProps(payload, slicer)} />} />
          </LineChart>
        </ResponsiveContainer>}
      </SectionCard>

      <SectionCard title="Metrics Glossary">
        <div className="grid-2" style={{ gap: 0 }}>
          <div style={{ padding: '4px 16px 4px 0', borderRight: '1px solid var(--border)' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginBottom: 12 }}>Model Performance — Regression</div>
            {[
              ['R²',    'How well the model explains variance in demand. 1.0 = perfect fit.'],
              ['MAE',   'Mean Absolute Error — average prediction error in demand units.'],
              ['RMSE',  'Root Mean Squared Error — penalises large errors more heavily.'],
              ['MAPE',  'Mean Absolute Percentage Error — average % error per prediction.'],
              ['WMAPE', 'Weighted MAPE — volume-weighted percentage error across all store×product combos.'],
            ].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', gap: 12, marginBottom: 10, alignItems: 'flex-start' }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, color: 'var(--blue)', minWidth: 52, paddingTop: 1 }}>{k}</span>
                <span style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.5 }}>{v}</span>
              </div>
            ))}
          </div>
          <div style={{ padding: '4px 0 4px 16px' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginBottom: 12 }}>Drift Detection</div>
            {[
              ['KS Test',     'Kolmogorov-Smirnov — detects if feature distributions have shifted.'],
              ['PSI',         'Population Stability Index — measures magnitude of distribution shift.'],
              ['Wasserstein', 'Earth mover\'s distance — how much effort to transform one distribution to another.'],
              ['JS Div.',     'Jensen-Shannon divergence — symmetric measure of distribution difference.'],
              ['Error Trend', 'Tracks MAE increase over time. Drift triggered when increase > 10%.'],
            ].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', gap: 12, marginBottom: 10, alignItems: 'flex-start' }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, color: 'var(--purple)', minWidth: 80, paddingTop: 1 }}>{k}</span>
                <span style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.5 }}>{v}</span>
              </div>
            ))}
            <div style={{ marginTop: 14, padding: '10px 12px', background: 'var(--card3)', borderRadius: 8, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', marginBottom: 6 }}>NOT APPLICABLE HERE</div>
              <div style={{ fontSize: 12, color: 'var(--text3)', lineHeight: 1.6 }}>
                Precision, Recall, F1, Accuracy — these are <strong style={{ color: 'var(--text2)' }}>classification metrics</strong> for yes/no predictions. Demand forecasting is a <strong style={{ color: 'var(--text2)' }}>regression problem</strong> — use the metrics above.
              </div>
            </div>
          </div>
        </div>
      </SectionCard>

      {summary?.confidence_intervals && (
        <SectionCard title="Confidence Intervals">
          <table className="tbl">
            <tbody>
              {[
                ['Coverage',  summary.confidence_intervals.coverage != null ? (summary.confidence_intervals.coverage * 100).toFixed(0) + '%' : '—'],
                ['Avg Width', summary.confidence_intervals.avg_width != null ? summary.confidence_intervals.avg_width.toLocaleString(undefined, { maximumFractionDigits: 0 }) + ' units' : '—'],
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
