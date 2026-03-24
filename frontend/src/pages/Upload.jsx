import { useState, useRef, useCallback, useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  LineChart, Line, Legend, ReferenceLine, ComposedChart, Area, AreaChart, Cell,
} from 'recharts'
import { API, useFetch } from '../api.js'
import { KPI, SectionCard, SevBadge, fmtD, toast } from '../ui.jsx'
import { HealingStatusDisplay } from './HealingStatus.jsx'

const MAX_MB = 50

const CSV_COLS = [
  ['Date',    'date (DD-MM-YYYY)', '05-01-2024', true],
  ['Product', 'str/int (item)',    'item_1',     true], 
  ['Demand',  'integer (units)',   '152',        true],
  ['Store',   'str/int (optional)','store_1',    false],
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

  // ── Optimized data fetching with conditional loading ─────────────────────────
  const { data: baseline } = useFetch('/api/baseline', { 
    enabled: tab === 'results' || result !== null 
  })
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
    const BASE = import.meta.env.VITE_API_URL || ''
    setRunning(true); setError(null); setResult(null); setProgress(15)
    try {
      const r = await API.uploadMonitor(file)
      setProgress(65)
      if (!r.ok) {
        const data = await r.json().catch(() => ({}))
        throw new Error(data.detail || data.message || `Monitor failed (HTTP ${r.status})`)
      }
      const data = await r.json()
      setProgress(85)
      const [drift, monthly, healing] = await Promise.all([
        API.drift(),
        fetch(BASE + '/api/monthly-sales').then(r => r.ok ? r.json() : []).catch(() => []),
        fetch(BASE + '/api/healing-history').then(r => r.ok ? r.json() : []).catch(() => []),
      ])
      setProgress(100)
      setResult({ summary: data.summary, drift, monthly, healing })
      setTab('results')
      toast.success('Monitor complete — drift analysis ready')
    } catch (e) {
      setError(e.message)
      toast.error(e.message)
    } finally {
      setRunning(false)
      setTimeout(() => setProgress(0), 800)
    }
  }, [file])

  // ── Memoized derived data for performance ─────────────────────────────────────
  const drift = useMemo(() => result?.drift || [], [result?.drift])
  const monthly = useMemo(() => result?.monthly || [], [result?.monthly])
  const healing = useMemo(() => result?.healing || [], [result?.healing])
  const healMap = useMemo(() => 
    Object.fromEntries(healing.map(h => [h.month, h])), [healing]
  )

  const stats = useMemo(() => {
    if (!drift.length) return { avgCurrentMAE: 0, avgBaselineMAE: 0, severeMonths: 0, mildMonths: 0 }
    return {
      avgCurrentMAE: drift.reduce((s, d) => s + (d.error_trend?.current_error || 0), 0) / drift.length,
      avgBaselineMAE: drift.reduce((s, d) => s + (d.error_trend?.baseline_error || 0), 0) / drift.length,
      severeMonths: drift.filter(d => d.severity === 'severe').length,
      mildMonths: drift.filter(d => d.severity === 'mild').length
    }
  }, [drift])

  // Memoized chart data
  const chartData = useMemo(() => {
    if (!drift.length) return { maeTrendData: [], featureData: [], errorIncreaseData: [], salesData: [] }
    
    return {
      maeTrendData: drift.map(d => ({
        month: d.month,
        'Test Set MAE': +(d.error_trend?.current_error || 0).toFixed(0),
        'Baseline': +(d.error_trend?.baseline_error || 0).toFixed(0),
      })),
      
      featureData: drift.map(d => ({
        month: d.month,
        Severe: d.severe_features || 0,
        Mild: d.mild_features || 0,
        Total: (d.severe_features || 0) + (d.mild_features || 0),
      })),
      
      errorIncreaseData: drift.map(d => ({
        month: d.month,
        'Error Increase %': +((d.error_trend?.error_increase || 0) * 100).toFixed(1),
        sev: d.severity,
      })),
      
      salesData: monthly.map(d => ({
        month: d.month,
        'Test Set': d.actual,
        Predicted: d.predicted,
        MAE: d.mae,
      }))
    }
  }, [drift, monthly])

  return (
    <>
      <div className="page-header">
        <div className="page-title">Upload & Monitor</div>
        <div className="page-sub">Upload new CSV data — scored against existing model, full drift analysis per month, no retraining</div>
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
                  {progress < 30 ? 'Running feature engineering...' :
                   progress < 65 ? 'Scoring against existing model...' :
                   progress < 90 ? 'Fetching drift results...' : 'Finalising...'}
                </span>
                <span>{progress}%</span>
              </div>
              <div className="progress-bar" style={{ height: 5 }}>
                <div className="progress-fill" style={{ width: `${progress}%`, background: 'linear-gradient(90deg, var(--green), var(--blue))' }} />
              </div>
              {progress < 65 && (
                <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>
                  Monitor mode: scoring against existing trained model — no retraining
                </div>
              )}
            </div>
          )}

          {running && <HealingStatusDisplay running={running} />}

          {file && (
            <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
              <button className="btn btn-primary" onClick={run} disabled={running}>
                {running ? 'Monitoring…' : 'Run Monitor'}
              </button>
              <button className="btn btn-outline" onClick={() => { setFile(null); setError(null) }} disabled={running}>Clear</button>
            </div>
          )}

          <SectionCard title="Required CSV Format" style={{ marginTop: 20 }}>
            <div className="alert alert-r" style={{ marginBottom: 12, fontSize: 12 }}>
              <strong>REQUIRED: Date, Product, and Demand columns.</strong> The model needs all three to work properly. Store and other columns are optional features.
            </div>
            <table className="tbl">
              <thead><tr><th>Column</th><th>Type</th><th>Example</th><th>Required</th></tr></thead>
              <tbody>
                {CSV_COLS.map(([col, type, ex, req]) => (
                  <tr key={col}>
                    <td className="mono" style={{ color: req ? 'var(--red)' : 'var(--text3)', fontWeight: 600 }}>{col}</td>
                    <td style={{ color: 'var(--text3)' }}>{type}</td>
                    <td className="mono">{ex}</td>
                    <td>{req ? <span className="badge b-red">Required</span> : <span className="badge b-green">Optional</span>}</td>
                  </tr>
                ))}
                <tr>
                  <td className="mono" style={{ color: 'var(--text3)' }}>+ any columns</td>
                  <td style={{ color: 'var(--text3)' }}>numeric / text</td>
                  <td className="mono">—</td>
                  <td><span className="badge b-green">Auto-detected</span></td>
                </tr>
              </tbody>
            </table>
            <div className="alert alert-b" style={{ marginTop: 12, fontSize: 12 }}>
              <strong>Column aliases work:</strong> Sales→Demand, Item→Product, etc. Supports DD-MM-YYYY, YYYY-MM-DD, MM/DD/YYYY date formats.
            </div>
            <div className="alert alert-g" style={{ marginTop: 8, fontSize: 11 }}>
              <strong>Monitor mode:</strong> Scores your data against the existing trained model. No retraining — full dataset used for drift detection.
            </div>
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
                <KPI label="Months Analysed"  value={drift.length} delta="Test set" />
                <KPI label="Severe Months"    value={stats.severeMonths} color="var(--red)"    delta={drift.length ? `${((stats.severeMonths/drift.length)*100).toFixed(0)}% of months` : '—'} />
                <KPI label="Mild Months"      value={stats.mildMonths}   color="var(--orange)" delta={drift.length ? `${((stats.mildMonths/drift.length)*100).toFixed(0)}% of months` : '—'} />
                <KPI label="Avg Test MAE"     value={Number(stats.avgCurrentMAE.toFixed(0)).toLocaleString() + ' units'}  color="var(--red)"   delta="Test set" />
                <KPI label="Healing Actions"  value={healing.filter(h => h.action !== 'monitor').length} color="var(--purple)" delta="fine-tune / rollback" />
              </div>

              {/* ── Metric Comparison Table ── */}
              <SectionCard title="Baseline vs Test Set — Metrics Comparison">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th style={{ color: 'var(--green)' }}>Baseline</th>
                      <th style={{ color: 'var(--red)' }}>Test Set (Avg)</th>
                      <th>Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    <StatRow label="MAE"          train={trainMetrics.MAE}  test={stats.avgCurrentMAE} />
                    <StatRow label="Baseline MAE" train={stats.avgBaselineMAE}    test={stats.avgCurrentMAE} />
                    <StatRow label="RMSE"         train={trainMetrics.RMSE} test={null} />
                    <StatRow label="MAPE"         train={trainMetrics.MAPE} test={null} unit="%" />
                    <StatRow label="R²"           train={trainMetrics.R2}   test={null} />
                    <tr>
                      <td style={{ color: 'var(--text3)', fontWeight: 500, fontSize: 12 }}>Severe Drift Months</td>
                      <td className="mono" style={{ color: 'var(--green)', fontWeight: 600 }}>0</td>
                      <td className="mono" style={{ color: 'var(--red)', fontWeight: 600 }}>{stats.severeMonths}</td>
                      <td className="mono" style={{ color: 'var(--red)', fontWeight: 700 }}>+{stats.severeMonths}</td>
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
                <SectionCard title="MAE — Baseline vs Test Set per Month">
                  <ResponsiveContainer width="100%" height={230}>
                    <LineChart data={chartData.maeTrendData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} tickFormatter={v => (v / 1000).toFixed(0) + 'K'} />
                      <Tooltip content={<Tip />} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <ReferenceLine y={trainMetrics.MAE} stroke="#94a3b8" strokeDasharray="4 2"
                        label={{ value: 'Train MAE', fontSize: 10, fill: '#94a3b8', position: 'insideTopRight' }} />
                      <Line type="monotone" dataKey="Baseline" stroke="#10b981" strokeWidth={2} dot={false} strokeDasharray="5 3" />
                      <Line type="monotone" dataKey="Test Set MAE"   stroke="#dc2626" strokeWidth={2.5} dot={{ r: 3, fill: '#dc2626' }} />
                    </LineChart>
                  </ResponsiveContainer>
                </SectionCard>

                <SectionCard title="Error Increase vs Baseline (%) — by month">
                  <ResponsiveContainer width="100%" height={230}>
                    <BarChart data={chartData.errorIncreaseData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} tickFormatter={v => v + '%'} />
                      <Tooltip content={<Tip />} />
                      <ReferenceLine y={10}  stroke="#d97706" strokeDasharray="4 2" label={{ value: 'Mild (10%)',   fontSize: 10, fill: '#d97706', position: 'insideTopRight' }} />
                      <ReferenceLine y={50}  stroke="#dc2626" strokeDasharray="4 2" label={{ value: 'Severe (50%)', fontSize: 10, fill: '#dc2626', position: 'insideTopRight' }} />
                      <Bar dataKey="Error Increase %" radius={[4, 4, 0, 0]}>
                        {chartData.errorIncreaseData.map((d, i) => (
                          <Cell key={i} fill={sevColor(d.sev)} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </SectionCard>
              </div>

              {/* ── Drift Severity + Healing Action Chart ── */}
              <SectionCard title="Drift Detection — Severity Level & Self-Healing Actions">
                {useMemo(() => {
                  const sevMap = { none: 0, mild: 1, severe: 2 }
                  const chartData = drift.map(d => {
                    const h = healMap[d.month]
                    return {
                      month: d.month,
                      'Drift Level': sevMap[d.severity] ?? 0,
                      severity: d.severity,
                      action: h?.action || 'monitor',
                      updated: h?.model_updated || false,
                      improvement: h ? +(h.improvement * 100).toFixed(1) : 0,
                    }
                  })
                  const DriftDot = (props) => {
                    const { cx, cy, payload } = props
                    if (!cx || !cy) return null
                    const c = sevColor(payload.severity)
                    const isHeal = payload.action === 'fine_tune'
                    const isRoll = payload.action === 'rollback'
                    return (
                      <g>
                        <circle cx={cx} cy={cy} r={6} fill={c} stroke="#fff" strokeWidth={2} />
                        {isHeal && <text x={cx} y={cy - 12} textAnchor="middle" fontSize={11} fill="#7c3aed" fontWeight={700}>✓</text>}
                        {isRoll && <text x={cx} y={cy - 12} textAnchor="middle" fontSize={11} fill="#94a3b8" fontWeight={700}>↩</text>}
                      </g>
                    )
                  }
                  const DriftTip = ({ active, payload, label }) => {
                    if (!active || !payload?.length) return null
                    const d = payload[0]?.payload
                    if (!d) return null
                    const actionLabel = d.action === 'fine_tune' ? '✓ Fine-tuned' : d.action === 'rollback' ? '↩ Rolled back' : '— Monitor'
                    return (
                      <div style={{ background: '#fff', border: '1px solid var(--border2)', borderRadius: 8, padding: '10px 14px', fontSize: 12, boxShadow: '0 4px 20px rgba(37,99,235,0.12)' }}>
                        <div style={{ fontWeight: 700, marginBottom: 4 }}>{d.month}</div>
                        <div>Drift: <strong style={{ color: sevColor(d.severity) }}>{d.severity.toUpperCase()}</strong></div>
                        <div>Action: <strong>{actionLabel}</strong></div>
                        {d.improvement > 0 && <div>Improvement: <strong style={{ color: '#7c3aed' }}>{d.improvement}%</strong></div>}
                      </div>
                    )
                  }
                  return (
                    <>
                      <ResponsiveContainer width="100%" height={220}>
                        <LineChart data={chartData} margin={{ top: 16, right: 12, bottom: 0, left: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                          <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                          <YAxis domain={[0, 2]} ticks={[0, 1, 2]} tick={{ fontSize: 10 }} tickFormatter={v => ['None', 'Mild', 'Severe'][v] || ''} />
                          <Tooltip content={<DriftTip />} />
                          <ReferenceLine y={1} stroke="#d97706" strokeDasharray="4 2" />
                          <ReferenceLine y={2} stroke="#dc2626" strokeDasharray="4 2" />
                          <Line type="stepAfter" dataKey="Drift Level" stroke="#6366f1" strokeWidth={2.5} dot={<DriftDot />} />
                        </LineChart>
                      </ResponsiveContainer>
                      <div style={{ display: 'flex', gap: 16, justifyContent: 'center', marginTop: 8, fontSize: 11, color: 'var(--text3)' }}>
                        <span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: '#059669', marginRight: 4 }} />None</span>
                        <span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: '#d97706', marginRight: 4 }} />Mild</span>
                        <span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: '#dc2626', marginRight: 4 }} />Severe</span>
                        <span style={{ color: '#7c3aed', fontWeight: 700 }}>✓ Fine-tuned</span>
                        <span style={{ color: '#94a3b8', fontWeight: 700 }}>↩ Rolled back</span>
                      </div>
                    </>
                  )
                }, [drift, healMap])}
              </SectionCard>

              {/* ── Row 2: Drifted Features + Test Set vs Predicted ── */}
              <div className="grid-2">
                <SectionCard title="Drifted Features per Test Month — Severe vs Mild">
                  <ResponsiveContainer width="100%" height={230}>
                    <ComposedChart data={chartData.featureData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
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

                <SectionCard title="Test Set vs Predicted Demand">
                  {chartData.salesData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={230}>
                      <AreaChart data={chartData.salesData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
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
                        <YAxis tick={{ fontSize: 10 }} tickFormatter={v => (v / 1000).toFixed(0) + 'K'} />
                        <Tooltip content={<Tip />} />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        <Area type="monotone" dataKey="Test Set"    stroke="#2563eb" fill="url(#gAct)" strokeWidth={2} dot={false} />
                        <Area type="monotone" dataKey="Predicted" stroke="#10b981" fill="url(#gPrd)" strokeWidth={2} dot={false} strokeDasharray="4 2" />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>No monthly demand data available</div>
                  )}
                </SectionCard>
              </div>

              {/* ── Full Drift Table ── */}
              <SectionCard title="Full Drift Report — Baseline vs Test Set">
                <div style={{ overflowX: 'auto' }}>
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th>Test Month</th>
                        <th>Severity</th>
                        <th>Severe Features</th>
                        <th>Mild Features</th>
                        <th>Baseline MAE</th>
                        <th>Test Set MAE</th>
                        <th>Error Increase</th>
                        <th>Healing Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {drift.map(d => {
                        const inc = (d.error_trend?.error_increase || 0) * 100
                        const h = healMap[d.month]
                        const act = h?.action || 'monitor'
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
                            <td style={{ fontWeight: 600, color: act === 'fine_tune' ? '#7c3aed' : act === 'rollback' ? '#94a3b8' : 'var(--text3)' }}>
                              {act === 'fine_tune' ? '✓ Fine-tuned' : act === 'rollback' ? '↩ Rollback' : '— Monitor'}
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
