import { useState, useRef, useCallback, useEffect, useMemo, memo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  LineChart, Line, Legend, Cell, AreaChart, Area, ComposedChart, ReferenceLine,
} from 'recharts'
import { API, useFetch } from '../api.js'
import { KPI, SectionCard, Spinner, ErrorBox, toast, Badge } from '../ui.jsx'

const pName = (id, names) => names?.[id] || `Product ${id}`

// ── Constants ────────────────────────────────────────────────────────────────
const COLORS = {
  actual: '#2563eb',
  predicted: '#10b981',
  error: '#dc2626',
  warning: '#d97706',
  info: '#6366f1',
}

// ── Custom Tooltip ───────────────────────────────────────────────────────────
const ChartTooltip = memo(({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: '#fff', border: '1px solid var(--border2)', borderRadius: 10,
      padding: '12px 16px', fontSize: 12, boxShadow: '0 8px 32px rgba(37,99,235,0.15)',
      minWidth: 180,
    }}>
      <div style={{ fontWeight: 700, color: 'var(--text)', marginBottom: 8, borderBottom: '1px solid var(--border)', paddingBottom: 6 }}>
        {label}
      </div>
      {payload.map(p => (
        <div key={p.name} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, marginBottom: 3 }}>
          <span style={{ color: 'var(--text3)' }}>{p.name}</span>
          <span style={{ color: p.color, fontWeight: 600, fontFamily: 'var(--mono)' }}>
            {typeof p.value === 'number' ? p.value.toLocaleString(undefined, { maximumFractionDigits: 1 }) : p.value}
          </span>
        </div>
      ))}
    </div>
  )
})

// ── Status Badge ─────────────────────────────────────────────────────────────
const StatusBadge = memo(({ status }) => {
  const map = {
    ready: { color: 'green', label: 'Ready' },
    waiting: { color: 'orange', label: 'Waiting for Upload' },
    error: { color: 'red', label: 'Error' },
    no_model: { color: 'red', label: 'No Model' },
  }
  const { color, label } = map[status] || { color: 'blue', label: status }
  return <Badge text={label} type={color} />
})

// ── Timeline Step ────────────────────────────────────────────────────────────
const TimelineStep = memo(({ icon, title, subtitle, color, active, completed }) => (
  <div style={{
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
    opacity: active ? 1 : completed ? 0.7 : 0.4,
    transition: 'all 0.2s',
  }}>
    <div style={{
      width: 48, height: 48, borderRadius: 12,
      background: active ? `${color}15` : completed ? `${color}08` : 'var(--bg2)',
      border: `2px solid ${active ? color : completed ? `${color}50` : 'var(--border)'}`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 20, transition: 'all 0.2s',
    }}>
      {completed ? '✓' : icon}
    </div>
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 11, fontWeight: 600, color: active ? color : 'var(--text2)' }}>{title}</div>
      <div style={{ fontSize: 10, color: 'var(--text3)' }}>{subtitle}</div>
    </div>
  </div>
))

// ── Comparison Card ──────────────────────────────────────────────────────────
const ComparisonMetric = memo(({ label, value, color, sub }) => (
  <div style={{
    background: 'var(--card2)', borderRadius: 10, padding: '16px 20px',
    border: '1px solid var(--border)', flex: 1, minWidth: 120,
  }}>
    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginBottom: 8 }}>
      {label}
    </div>
    <div style={{ fontSize: 24, fontWeight: 800, color: color || 'var(--text)', fontFamily: 'var(--mono)' }}>
      {value}
    </div>
    {sub && <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>{sub}</div>}
  </div>
))

// ── Main Component ───────────────────────────────────────────────────────────
export default function Predict() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [selectedPred, setSelectedPred] = useState(null)
  const [predData, setPredData] = useState(null)
  const [drag, setDrag] = useState(false)
  const inputRef = useRef()
  const { data: productNames } = useFetch('/api/product-names')

  // Load status
  const loadStatus = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const s = await API.seqStatus()
      setStatus(s)
      if (s.available_predictions?.length) {
        setSelectedPred(p => p || s.available_predictions[s.available_predictions.length - 1])
      }
    } catch (e) {
      setError(e.message || 'Failed to connect to API. Make sure backend is running.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadStatus() }, [loadStatus])

  // Load prediction data
  useEffect(() => {
    if (!selectedPred) return
    API.seqPrediction(selectedPred)
      .then(setPredData)
      .catch(() => setPredData(null))
  }, [selectedPred])

  // File handlers
  const pickFile = useCallback(f => {
    if (!f) return
    if (!f.name.toLowerCase().endsWith('.csv')) {
      toast.error('Only CSV files are accepted')
      return
    }
    setFile(f)
    setError(null)
  }, [])

  const onDrop = useCallback(e => {
    e.preventDefault()
    setDrag(false)
    pickFile(e.dataTransfer.files[0])
  }, [pickFile])

  const onDragOver  = useCallback(e => { e.preventDefault(); setDrag(true) }, [])
  const onDragLeave = useCallback(() => setDrag(false), [])

  const uploadActuals = useCallback(async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    setResult(null)
    try {
      const resp = await API.seqUploadActuals(file)
      const r = await resp.json()
      if (!resp.ok) throw new Error(r.detail || r.error || `Upload failed (HTTP ${resp.status})`)
      if (r.error || r.detail) throw new Error(r.detail || r.error)
      setResult(r)
      setFile(null)
      toast.success(`Uploaded ${r.uploaded_month} → Predicted ${r.next_prediction?.prediction_month}`)
      loadStatus()
    } catch (e) {
      setError(e.message)
      toast.error(e.message)
    } finally {
      setUploading(false)
    }
  }, [file, loadStatus])

  // Chart data
  const comparisonData = useMemo(() => {
    const rows = result?.comparison?.products?.length
      ? result.comparison.products
      : (result?.comparison?.stores || [])
    return rows.map(s => ({
      product: pName(s.Product, productNames),
      'Actual': Math.round(s.Actual),
      Predicted: Math.round(s.Predicted),
      Error: Math.round(Math.abs(s.Actual - s.Predicted)),
    }))
  }, [result, productNames])

  const historyData = useMemo(() =>
    status?.comparisons?.map(c => ({
      month: c.month,
      MAE: c.mae,
      MAPE: c.mape,
    })) || [],
  [status])

  const predChartData = useMemo(() => {
    if (!predData?.predictions?.length) return []
    // Group by product, show avg predicted
    const map = {}
    predData.predictions.forEach(p => {
      const pid = p.Product
      if (!map[pid]) map[pid] = { product: pName(pid, productNames), Product: pid, sum: 0, n: 0, ci_l: 0, ci_u: 0 }
      map[pid].sum += p.Predicted_Demand
      map[pid].ci_l += p.CI_Lower
      map[pid].ci_u += p.CI_Upper
      map[pid].n++
    })
    return Object.values(map).sort((a, b) => b.sum / b.n - a.sum / a.n).map(d => ({
      product: d.product,
      Predicted: Math.round(d.sum / d.n),
      CI_Lower: Math.round(d.ci_l / d.n),
      CI_Upper: Math.round(d.ci_u / d.n),
    }))
  }, [predData, productNames])

  // Determine workflow step
  const workflowStep = useMemo(() => {
    if (!status) return 0
    if (status.waiting_for_upload) return 2 // waiting for actuals
    if (status.last_prediction_month) return 3 // has predictions
    return 1 // ready to predict
  }, [status])

  // Loading state
  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60vh', gap: 16 }}>
        <Spinner />
        <div style={{ fontSize: 13, color: 'var(--text3)' }}>Connecting to prediction service...</div>
      </div>
    )
  }

  // Error state (API not available)
  if (error && !status) {
    return (
      <>
        <div className="page-header">
          <div className="page-title">Monthly Prediction Cycle</div>
          <div className="page-sub">Rolling forecast workflow for demand prediction</div>
        </div>
        <ErrorBox msg={error} onRetry={loadStatus} />
        <SectionCard title="Troubleshooting" style={{ marginTop: 20 }}>
          <div style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 1.8 }}>
            <p><strong>1. Start the backend server:</strong></p>
            <pre style={{ background: 'var(--bg2)', padding: '12px 16px', borderRadius: 8, fontSize: 12, fontFamily: 'var(--mono)', marginBottom: 16 }}>
              cd backend{'\n'}uvicorn api:app --reload --port 8000
            </pre>
            <p><strong>2. Run the pipeline first</strong> (if no model exists):</p>
            <pre style={{ background: 'var(--bg2)', padding: '12px 16px', borderRadius: 8, fontSize: 12, fontFamily: 'var(--mono)', marginBottom: 16 }}>
              python main.py
            </pre>
            <p><strong>3. Then start the frontend:</strong></p>
            <pre style={{ background: 'var(--bg2)', padding: '12px 16px', borderRadius: 8, fontSize: 12, fontFamily: 'var(--mono)' }}>
              cd frontend{'\n'}npm run dev
            </pre>
          </div>
        </SectionCard>
      </>
    )
  }

  return (
    <>
      <div className="page-header">
        <div className="page-title">Monthly Prediction Cycle</div>
        <div className="page-sub">
          Predict next month's product demand &rarr; Upload actuals &rarr; Compare &rarr; Repeat
        </div>
      </div>

      {/* Status KPIs */}
      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))' }}>
        <KPI label="Data Range" value={status?.data_range || '—'} delta={`${status?.total_rows || 0} rows`} />
        <KPI label="Products" value={status?.products || 0} />
        <KPI label="Last Data" value={status?.last_data_month || '—'} color="var(--blue)" />
        <KPI label="Last Prediction" value={status?.last_prediction_month || '—'} color="var(--green)" />
        <KPI label="Status" value={<StatusBadge status={status?.waiting_for_upload ? 'waiting' : 'ready'} />} />
      </div>

      {/* Workflow Timeline */}
      <SectionCard title="Prediction Workflow" style={{ marginTop: 20 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', padding: '20px 10px', position: 'relative' }}>
          {/* Connection line */}
          <div style={{
            position: 'absolute', top: 44, left: 60, right: 60, height: 2,
            background: 'linear-gradient(90deg, var(--green) 0%, var(--blue) 50%, var(--purple) 100%)',
            opacity: 0.3, zIndex: 0,
          }} />
          
          <TimelineStep icon="📊" title="Train Model" subtitle={status?.train_end ? status.train_end.slice(0,4) + ' data' : 'Year 1'} color="var(--green)" completed={true} />
          <TimelineStep icon="🧪" title="Test Model" subtitle={status?.test_end ? status.test_end.slice(0,4) + ' data' : 'Year 2'} color="var(--green)" completed={true} />
          <TimelineStep icon="🔮" title="Predict" subtitle={status?.last_prediction_month || 'Next month'} color="var(--blue)" active={workflowStep === 1} completed={workflowStep > 1} />
          <TimelineStep icon="📤" title="Upload Actuals" subtitle={status?.waiting_for_upload || '—'} color="var(--orange)" active={workflowStep === 2} completed={workflowStep > 2} />
          <TimelineStep icon="📈" title="Compare" subtitle="Pred vs Actual" color="var(--purple)" active={workflowStep === 3} />
          <TimelineStep icon="🔄" title="Repeat" subtitle="Next cycle" color="var(--text3)" />
        </div>
        
        {status?.waiting_for_upload && (
          <div className="alert alert-b" style={{ marginTop: 12 }}>
            <strong>Action Required:</strong> Upload actual demand data for <strong>{status.waiting_for_upload}</strong> to continue the prediction cycle.
          </div>
        )}
      </SectionCard>

      <div className="grid-2" style={{ marginTop: 20 }}>
        {/* Upload Section */}
        <SectionCard title="📤 Upload Monthly Actuals">
          <div
            className={`upload-zone${drag ? ' drag' : ''}`}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            style={{
              cursor: 'pointer', padding: '32px 20px', textAlign: 'center',
              border: `2px dashed ${file ? 'var(--green)' : drag ? 'var(--blue)' : 'var(--border2)'}`,
              borderRadius: 12, background: file ? '#ecfdf5' : drag ? '#eff6ff' : 'var(--bg2)',
              transition: 'all 0.2s',
            }}
          >
            {file ? (
              <>
                <div style={{ fontSize: 32, marginBottom: 8 }}>✓</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--green)' }}>{file.name}</div>
                <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 4 }}>{(file.size / 1024).toFixed(1)} KB</div>
              </>
            ) : (
              <>
                <div style={{ fontSize: 32, marginBottom: 8 }}>📁</div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text2)' }}>Drop CSV here or click to browse</div>
                <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 6 }}>
                  Required: Date, Product, Demand (+ any extra columns)
                </div>
              </>
            )}
            <input ref={inputRef} type="file" accept=".csv" style={{ display: 'none' }} onChange={e => pickFile(e.target.files[0])} />
          </div>

          {error && <div className="alert alert-r" style={{ marginTop: 12, fontSize: 12 }}>{error}</div>}

          {file && (
            <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
              <button className="btn btn-primary" onClick={uploadActuals} disabled={uploading} style={{ flex: 1 }}>
                {uploading ? '⏳ Processing...' : '🚀 Upload & Predict Next'}
              </button>
              <button className="btn btn-outline" onClick={() => setFile(null)} disabled={uploading}>Clear</button>
            </div>
          )}

          {/* CSV Format Reference */}
          <div style={{ marginTop: 20, padding: '14px 16px', background: 'var(--bg2)', borderRadius: 10, border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginBottom: 10 }}>
              CSV Format (DD-MM-YYYY dates)
            </div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text2)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
Date,Product,Demand
02-01-2026,1,280
02-01-2026,2,510
02-01-2026,3,720
            </div>
          </div>
        </SectionCard>

        {/* Latest Comparison */}
        <SectionCard title="📊 Latest Comparison">
          {result?.comparison ? (
            <>
              <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
                <ComparisonMetric label="Month" value={result.comparison.month} color="var(--blue)" />
                <ComparisonMetric label="MAE" value={`${result.comparison.mae?.toLocaleString() || 0} units`} color="var(--red)" sub="Mean Absolute Error" />
                <ComparisonMetric label="MAPE" value={`${result.comparison.mape?.toFixed(1) || 0}%`} color="var(--orange)" sub="Mean Abs % Error" />
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={comparisonData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="product" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip content={<ChartTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="Actual" fill={COLORS.actual} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Predicted" fill={COLORS.predicted} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--text3)' }}>
              <div style={{ fontSize: 40, marginBottom: 12, opacity: 0.5 }}>📊</div>
              <div style={{ fontSize: 13, fontWeight: 500 }}>No comparison data yet</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>Upload test set data to see prediction accuracy</div>
            </div>
          )}
        </SectionCard>
      </div>

      {/* Next Prediction Result */}
      {result?.next_prediction && (
        <SectionCard title={`🔮 New Prediction: ${result.next_prediction.prediction_month}`} style={{ marginTop: 20 }}>
          <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', marginBottom: 16 }}>
            <KPI label="Month" value={result.next_prediction.prediction_month} color="var(--purple)" />
            <KPI label="Predictions" value={result.next_prediction.count} />
            <KPI label="Mean Predicted" value={(result.next_prediction.mean_predicted?.toLocaleString() || 0) + ' units'} color="var(--green)" />
            <KPI label="Data Through" value={result.next_prediction.based_on_data_through} />
          </div>
          {result.next_prediction.product_summary && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {Object.entries(result.next_prediction.product_summary).map(([pid, value]) => (
                <div key={pid} style={{
                  padding: '8px 14px', background: 'var(--bg2)', borderRadius: 8,
                  border: '1px solid var(--border)', fontSize: 12,
                }}>
                  <span style={{ color: 'var(--text3)' }}>{pName(Number(pid), productNames)}:</span>{' '}
                  <span style={{ fontWeight: 600, color: 'var(--green)', fontFamily: 'var(--mono)' }}>
                    {Math.round(value)} units
                  </span>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      )}

      {/* Historical Accuracy */}
      {historyData.length > 0 && (
        <SectionCard title="📈 Prediction Accuracy History" style={{ marginTop: 20 }}>
          <ResponsiveContainer width="100%" height={250}>
            <ComposedChart data={historyData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} />
              <YAxis yAxisId="mae" tick={{ fontSize: 10 }} />
              <YAxis yAxisId="mape" orientation="right" tick={{ fontSize: 10 }} tickFormatter={v => v + '%'} />
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar yAxisId="mae" dataKey="MAE" fill={COLORS.error} opacity={0.7} radius={[4, 4, 0, 0]} name="MAE (units)" />
              <Line yAxisId="mape" type="monotone" dataKey="MAPE" stroke={COLORS.warning} strokeWidth={2} dot={{ r: 4 }} name="MAPE (%)" />
            </ComposedChart>
          </ResponsiveContainer>
        </SectionCard>
      )}

      {/* Saved Predictions Browser */}
      {status?.available_predictions?.length > 0 && (
        <SectionCard title="📁 Saved Predictions" style={{ marginTop: 20 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
            {status.available_predictions.map(m => (
              <button
                key={m}
                className={`btn ${selectedPred === m ? 'btn-primary' : 'btn-outline'}`}
                style={{ fontSize: 12, padding: '6px 14px' }}
                onClick={() => setSelectedPred(m)}
              >
                {m}
              </button>
            ))}
          </div>

          {predData && (
            <>
              <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
                <ComparisonMetric label="Month" value={predData.month} color="var(--blue)" />
                <ComparisonMetric label="Predictions" value={predData.count} />
                <ComparisonMetric label="Mean" value={`${predData.mean_predicted?.toLocaleString() || 0} units`} color="var(--green)" />
              </div>
              <ResponsiveContainer width="100%" height={Math.max(220, predChartData.length * 22)}>
                <BarChart data={predChartData} layout="vertical" margin={{ top: 8, right: 16, bottom: 0, left: 110 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis type="number" tick={{ fontSize: 10 }} />
                  <YAxis type="category" dataKey="product" tick={{ fontSize: 10 }} width={110} />
                  <Tooltip content={<ChartTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="Predicted" fill={COLORS.predicted} radius={[0, 4, 4, 0]} name="Predicted Demand" />
                </BarChart>
              </ResponsiveContainer>
            </>
          )}
        </SectionCard>
      )}
    </>
  )
}
