import { useState, useRef, useCallback, memo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  LineChart, Line, Legend, ReferenceLine, ComposedChart, Area, AreaChart,
  Cell,
} from 'recharts'
import { API, useFetch } from '../api.js'
import { KPI, SectionCard, SevBadge, fmtD, toast } from '../ui.jsx'

const MAX_MB = 50

const CSV_COLS = [
  ['Store',        'integer', '1'],
  ['Date',         'date',    '2011-02-04'],
  ['Weekly_Sales', 'float',   '1643690.90'],
  ['Holiday_Flag', '0 or 1',  '0'],
  ['Temperature',  'float',   '42.31'],
  ['Fuel_Price',   'float',   '2.572'],
  ['CPI',          'float',   '211.096'],
  ['Unemployment', 'float',   '8.106'],
]

// ── Tooltip ───────────────────────────────────────────────────────────────────
const Tip = ({ active, payload, label, dollar }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#fff', border: '1px solid var(--border2)', borderRadius: 8, padding: '10px 14px', fontSize: 12, boxShadow: '0 4px 20px rgba(37,99,235,0.12)' }}>
      <div style={{ fontWeight: 700, color: 'var(--text2)', marginBottom: 5 }}>{label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color, marginBottom: 2 }}>
          {p.name}: <strong>{dollar ? '$' + Number(p.value).toLocaleString() : p.value}</strong>
        </div>
      ))}
    </div>
  )
}

// ── Severity color ────────────────────────────────────────────────────────────
const sevColor = s => s === 'severe' ? '#dc2626' : s === 'mild' ? '#d97706' : '#059669'

// ── Stat row ──────────────────────────────────────────────────────────────────
const StatRow = ({ label, train, test, unit = '' }) => {
  const diff = test != null && train != null ? test - train : null
  const pct  = diff != null && train ? ((diff / train) * 100).toFixed(1) : null
  return (
    <tr>
      <td style={{ color: 'var(--text3)', fontWeight: 500, fontSize: 12 }}>{label}</td>
      <td className="mono" style={{ color: 'var(--green)', fontWeight: 600 }}>{train != null ? unit + Number(train).toLocaleString(undefined, { maximumFractionDigits: 2 }) : '—'}</td>
      <td className="mono" style={{ color: diff > 0 ? 'var(--red)' : 'var(--green)', fontWeight: 600 }}>{test != null ? unit + Number(test).toLocaleString(undefined, { maximumFractionDigits: 2 }) : '—'}</td>
      <td className="mono" style={{ color: diff > 0 ? 'var(--red)' : 'var(--green)', fontWeight: 700 }}>
        {pct != null ? (diff > 0 ? '+' : '') + pct + '%' : '—'}
      </td>
    </tr>
  )
}

export default function Upload() {
  const [tab,      setTab]      = useState('upload')
  const [file,     setFile]     = useState(null)
  const [drag,     setDrag]     = useState(false)
  const [running,  setRunning]  = useState(false)
  const [result,   setResult]   = useState(null)
  const [error,    setError]    = useState(null)
  const [progress, setProgress] = useState(0)
  const inputRef = useRef()

  const { data: baseline } = useFetch('/api/baseline')
  const trainMetrics = baseline?.train || {}

  const pickFile = useCallback(f => {
    if (!f) return
    if (!f.name.toLowerCase().endsWith('.csv')) { setError('Only .csv files are accepted'); return }
    if (f.size > MAX_MB * 1024 * 1024) { setError(`File too large — max ${MAX_MB} MB`); return }
    setError(null); setFile(f)
  }, [])

  const onDrop      = useCallback(e => { e.preventDefault(); setDrag(false); pickFile(e.dataTransfer.files[0]) }, [pickFile])
  const onDragOver  = useCallback(e => { e.preventDefault(); setDrag(true) }, [])
  const onDragLeave = useCallback(() => setDrag(false), [])
  const onZoneClick = useCallback(() => inputRef.current?.click(), [])

  const run = useCallback(async () => {
    if (!file) return
    setRunning(true); setError(null); setResult(null); setProgress(15)
    try {
      const r = await API.uploadPredict(file)
      setProgress(65)
      if (!r.ok) {
        const data = await r.json().catch(() => ({}))
        throw new Error(data.detail || data.message || `Pipeline failed (HTTP ${r.status})`)
      }
      const data = await r.json()
      setProgress(85)
      const [drift, monthly] = await Promise.all([
        API.drift(),
        fetch((import.meta.env.VITE_API_URL || '') + '/api/monthly-sales').then(r => r.json()),
      ])
      setProgress(100)
      setResult({ stdout: data.stdout, drift, monthly })
      setTab('results')
      toast.success('Pipeline complete — drift analysis ready')
    } catch (e) {
      setError(e.message)
      toast.error(e.message)
    } finally {
      setRunning(false)
      setTimeout(() => setProgress(0), 800)
    }
  }, [file])

  // ── Derived data ─────────────────────────────────────────────────────────────
  const drift   = result?.drift   || []
  const monthly = result?.monthly || []
  const latest  = drift[drift.length - 1]

  const avgCurrentMAE  = drift.length ? drift.reduce((s, d) => s + (d.error_trend?.current_error  || 0), 0) / drift.length : 0
  const avgBaselineMAE = drift.length ? drift.reduce((s, d) => s + (d.error_trend?.baseline_error || 0), 0) / drift.length : 0
  const severeMonths   = drift.filter(d => d.severity === 'severe').length
  const mildMonths     = drift.filter(d => d.severity === 'mild').length

  // Chart data
  const maeTrendData = drift.map(d => ({
    month:    d.month,
    'New Data MAE': +(d.error_trend?.current_error  || 0).toFixed(0),
    'Train Baseline': +(d.error_trend?.baseline_error || 0).toFixed(0),
  }))

  const featureData = drift.map(d => ({
    month:  d.month,
    Severe: d.severe_features || 0,
    Mild:   d.mild_features   || 0,
    Total:  (d.severe_features || 0) + (d.mild_features || 0),
  }))

  const errorIncreaseData = drift.map(d => ({
    month:    d.month,
    'Error Increase %': +((d.error_trend?.error_increase || 0) * 100).toFixed(1),
    sev:      d.severity,
  }))

  const salesData = monthly.map(d => ({
    month:     d.month,
    Actual:    d.actual,
    Predicted: d.predicted,
    MAE:       d.mae,
  }))

  return (
    <>
      <div className="page-header">
        <div className="page-title">Upload & Monitor</div>
        <div className="page-sub">Upload new CSV data — pipeline runs automatically and shows drift vs trained baseline</div>
      </div>

      <div className="tabs">
        <div className={`tab${tab === 'upload'  ? ' active' : ''}`} onClick={() => setTab('upload')}>Upload & Run</div>
        <div className={`tab${tab === 'results' ? ' active' : ''}`} onClick={() => setTab('results')}>
          Drift Analysis
          {result && <span style={{ marginLeft: 8, background: 'var(--green)', color: '#fff', borderRadius: 4, padding: '1px 8px', fontSize: 10, fontWeight: 700 }}>Done</span>}
        </div>
      </div>

      {/* ── Upload Tab ── */}
      {tab === 'upload' && (
        <>
          <div className={`upload-zone${drag ? ' drag' : ''}`}
            onDragOver={onDragOver} onDragLeave={onDragLeave}
            onDrop={onDrop} onClick={onZoneClick}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '2px', marginBottom: 10 }}>
              {file ? 'CSV Selected' : 'Drop CSV Here'}
            </div>
            <p style={{ fontWeight: 600, color: 'var(--text)', fontSize: 15 }}>
              {file ? file.name : 'or click to browse files'}
            </p>
            {file
              ? <p style={{ color: 'var(--green)', marginTop: 6, fontSize: 12 }}>{(file.size / 1024).toFixed(1)} KB — ready to run</p>
              : <p className="hint">Max {MAX_MB} MB · .csv format only</p>
            }
            <input ref={inputRef} type="file" accept=".csv" style={{ display: 'none' }} onChange={e => pickFile(e.target.files[0])} />
          </div>

          {error && <div className="alert alert-r" style={{ marginTop: 12 }}>{error}</div>}

          {running && progress > 0 && (
            <div style={{ marginTop: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text3)', marginBottom: 6 }}>
                <span style={{ fontWeight: 600 }}>
                  {progress < 65 ? 'Running pipeline…' : progress < 90 ? 'Fetching drift results…' : 'Finalising…'}
                </span>
                <span>{progress}%</span>
              </div>
              <div className="progress-bar" style={{ height: 5 }}>
                <div className="progress-fill" style={{ width: `${progress}%`, background: 'linear-gradient(90deg, var(--blue), var(--purple))' }} />
              </div>
            </div>
          )}

          {file && (
            <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
              <button className="btn btn-primary" onClick={run} disabled={running}>
                {running ? 'Running Pipeline…' : 'Run Pipeline'}
              </button>
              <button className="btn btn-outline" onClick={() => { setFile(null); setError(null) }} disabled={running}>Clear</button>
            </div>
          )}

          <SectionCard title="Expected CSV Format" style={{ marginTop: 20 }}>
            <table className="tbl">
              <thead><tr><th>Column</th><th>Type</th><th>Example</th></tr></thead>
              <tbody>
                {CSV_COLS.map(([col, type, ex]) => (
                  <tr key={col}>
                    <td className="mono" style={{ color: 'var(--blue)', fontWeight: 600 }}>{col}</td>
                    <td style={{ color: 'var(--text3)' }}>{type}</td>
                    <td className="mono">{ex}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </SectionCard>
        </>
      )}

      {/* ── Results Tab ── */}
      {tab === 'results' && (
        <>
          {!result ? (
            <div className="alert alert-b">No results yet — upload a CSV and run the pipeline first.</div>
          ) : (
            <>
              {/* ── KPI Summary ── */}
              <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(5,1fr)' }}>
                <KPI label="Months Analysed"  value={drift.length} delta="New data" />
                <KPI label="Severe Months"    value={severeMonths} color="var(--red)"    delta={`${((severeMonths/drift.length)*100).toFixed(0)}% of months`} />
                <KPI label="Mild Months"      value={mildMonths}   color="var(--orange)" delta={`${((mildMonths/drift.length)*100).toFixed(0)}% of months`} />
                <KPI label="Avg New MAE"      value={'$' + Number(avgCurrentMAE.toFixed(0)).toLocaleString()}  color="var(--red)"   delta="New data" />
                <KPI label="Train Baseline MAE" value={'$' + Number(avgBaselineMAE.toFixed(0)).toLocaleString()} color="var(--green)" delta="Trained model" />
              </div>

              {/* ── Metric Comparison Table ── */}
              <SectionCard title="New Data vs Trained Baseline — exact numbers">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th style={{ color: 'var(--green)' }}>Train Baseline</th>
                      <th style={{ color: 'var(--red)' }}>New Data (Avg)</th>
                      <th>Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    <StatRow label="MAE"            train={trainMetrics.MAE}   test={avgCurrentMAE}  unit="$" />
                    <StatRow label="Baseline MAE"   train={avgBaselineMAE}     test={avgCurrentMAE}  unit="$" />
                    <StatRow label="RMSE"           train={trainMetrics.RMSE}  test={null} />
                    <StatRow label="MAPE"           train={trainMetrics.MAPE}  test={null} unit="%" />
                    <StatRow label="R²"             train={trainMetrics.R2}    test={null} />
                    <tr>
                      <td style={{ color: 'var(--text3)', fontWeight: 500, fontSize: 12 }}>Severe Drift Months</td>
                      <td className="mono" style={{ color: 'var(--green)', fontWeight: 600 }}>0</td>
                      <td className="mono" style={{ color: 'var(--red)', fontWeight: 600 }}>{severeMonths}</td>
                      <td className="mono" style={{ color: 'var(--red)', fontWeight: 700 }}>+{severeMonths}</td>
                    </tr>
                    <tr>
                      <td style={{ color: 'var(--text3)', fontWeight: 500, fontSize: 12 }}>Avg Drifted Features</td>
                      <td className="mono" style={{ color: 'var(--green)', fontWeight: 600 }}>0</td>
                      <td className="mono" style={{ color: 'var(--red)', fontWeight: 600 }}>
                        {drift.length ? ((drift.reduce((s,d) => s + (d.severe_features||0) + (d.mild_features||0), 0)) / drift.length).toFixed(1) : '—'}
                      </td>
                      <td className="mono" style={{ color: 'var(--red)', fontWeight: 700 }}>
                        {drift.length ? '+' + ((drift.reduce((s,d) => s + (d.severe_features||0) + (d.mild_features||0), 0)) / drift.length).toFixed(1) : '—'}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </SectionCard>

              {/* ── Row 1: MAE Trend + Error Increase % ── */}
              <div className="grid-2">
                <SectionCard title="MAE — New Data vs Train Baseline per Month">
                  <ResponsiveContainer width="100%" height={230}>
                    <LineChart data={maeTrendData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v / 1000).toFixed(0) + 'K'} />
                      <Tooltip content={<Tip dollar />} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <ReferenceLine y={trainMetrics.MAE} stroke="#94a3b8" strokeDasharray="4 2"
                        label={{ value: 'Train MAE', fontSize: 10, fill: '#94a3b8', position: 'insideTopRight' }} />
                      <Line type="monotone" dataKey="Train Baseline" stroke="#10b981" strokeWidth={2} dot={false} strokeDasharray="5 3" />
                      <Line type="monotone" dataKey="New Data MAE"   stroke="#dc2626" strokeWidth={2.5} dot={{ r: 3, fill: '#dc2626' }} />
                    </LineChart>
                  </ResponsiveContainer>
                </SectionCard>

                <SectionCard title="Error Increase % vs Baseline — by month">
                  <ResponsiveContainer width="100%" height={230}>
                    <BarChart data={errorIncreaseData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} tickFormatter={v => v + '%'} />
                      <Tooltip content={<Tip />} />
                      <ReferenceLine y={10}  stroke="#d97706" strokeDasharray="4 2" label={{ value: 'Mild (10%)',   fontSize: 10, fill: '#d97706', position: 'insideTopRight' }} />
                      <ReferenceLine y={50}  stroke="#dc2626" strokeDasharray="4 2" label={{ value: 'Severe (50%)', fontSize: 10, fill: '#dc2626', position: 'insideTopRight' }} />
                      <Bar dataKey="Error Increase %" radius={[4, 4, 0, 0]}>
                        {errorIncreaseData.map((d, i) => (
                          <Cell key={i} fill={sevColor(d.sev)} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </SectionCard>
              </div>

              {/* ── Row 2: Drifted Features + Actual vs Predicted ── */}
              <div className="grid-2">
                <SectionCard title="Drifted Features per Month — Severe vs Mild">
                  <ResponsiveContainer width="100%" height={230}>
                    <ComposedChart data={featureData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip content={<Tip />} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="Severe" fill="#dc2626" stackId="a" />
                      <Bar dataKey="Mild"   fill="#d97706" stackId="a" radius={[3, 3, 0, 0]} />
                      <Line type="monotone" dataKey="Total" stroke="#2563eb" strokeWidth={2} dot={false} name="Total Drifted" />
                    </ComposedChart>
                  </ResponsiveContainer>
                </SectionCard>

                <SectionCard title="Actual vs Predicted Sales — new data">
                  {salesData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={230}>
                      <AreaChart data={salesData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                        <defs>
                          <linearGradient id="gAct" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%"  stopColor="#2563eb" stopOpacity={0.15} />
                            <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                          </linearGradient>
                          <linearGradient id="gPrd" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%"  stopColor="#10b981" stopOpacity={0.12} />
                            <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v / 1000).toFixed(0) + 'K'} />
                        <Tooltip content={<Tip dollar />} />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        <Area type="monotone" dataKey="Actual"    stroke="#2563eb" fill="url(#gAct)" strokeWidth={2} dot={false} />
                        <Area type="monotone" dataKey="Predicted" stroke="#10b981" fill="url(#gPrd)" strokeWidth={2} dot={false} strokeDasharray="4 2" />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>No monthly sales data available</div>
                  )}
                </SectionCard>
              </div>

              {/* ── Full Drift Table ── */}
              <SectionCard title="Full Drift Report — all months">
                <div style={{ overflowX: 'auto' }}>
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th>Month</th>
                        <th>Severity</th>
                        <th>Severe Features</th>
                        <th>Mild Features</th>
                        <th>Train Baseline MAE</th>
                        <th>New Data MAE</th>
                        <th>Error Increase</th>
                      </tr>
                    </thead>
                    <tbody>
                      {drift.map(d => {
                        const inc = (d.error_trend?.error_increase || 0) * 100
                        return (
                          <tr key={d.month}>
                            <td className="mono" style={{ fontWeight: 600 }}>{d.month}</td>
                            <td><SevBadge severity={d.severity} /></td>
                            <td style={{ color: 'var(--red)', fontWeight: 700 }}>{d.severe_features}</td>
                            <td style={{ color: 'var(--orange)', fontWeight: 600 }}>{d.mild_features}</td>
                            <td className="mono" style={{ color: 'var(--green)' }}>{fmtD(d.error_trend?.baseline_error)}</td>
                            <td className="mono" style={{ color: 'var(--red)', fontWeight: 600 }}>{fmtD(d.error_trend?.current_error)}</td>
                            <td className="mono" style={{ color: inc > 50 ? 'var(--red)' : 'var(--orange)', fontWeight: 700 }}>
                              +{inc.toFixed(1)}%
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </SectionCard>
            </>
          )}
        </>
      )}
    </>
  )
}
