import { useState, useRef, useCallback } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, LineChart, Line, Legend } from 'recharts'
import { API } from '../api.js'
import { KPI, SectionCard, SevBadge, fmtD, CHART_STYLE, toast } from '../ui.jsx'

const MAX_MB = 50

export default function Upload() {
  const [tab,     setTab]     = useState('upload')
  const [file,    setFile]    = useState(null)
  const [drag,    setDrag]    = useState(false)
  const [running, setRunning] = useState(false)
  const [result,  setResult]  = useState(null)
  const [error,   setError]   = useState(null)
  const inputRef = useRef()

  const pickFile = useCallback(f => {
    if (!f) return
    if (!f.name.toLowerCase().endsWith('.csv')) { setError('Only .csv files are accepted'); return }
    if (f.size > MAX_MB * 1024 * 1024) { setError(`File too large — max ${MAX_MB} MB`); return }
    setError(null); setFile(f)
  }, [])

  const onDrop = useCallback(e => {
    e.preventDefault(); setDrag(false)
    pickFile(e.dataTransfer.files[0])
  }, [pickFile])

  const onDragOver  = useCallback(e => { e.preventDefault(); setDrag(true)  }, [])
  const onDragLeave = useCallback(() => setDrag(false), [])
  const onInputChange = useCallback(e => pickFile(e.target.files[0]), [pickFile])
  const onZoneClick = useCallback(() => inputRef.current?.click(), [])

  const run = useCallback(async () => {
    if (!file) return
    setRunning(true); setError(null); setResult(null)
    try {
      const r = await API.uploadPredict(file)
      const data = await r.json()
      if (!r.ok) throw new Error(data.detail || data.message || 'Pipeline failed')
      const drift = await API.drift()
      setResult({ stdout: data.stdout, drift })
      setTab('results')
      toast.success('Pipeline complete — drift analysis updated')
    } catch (e) {
      setError(e.message)
      toast.error(e.message)
    } finally {
      setRunning(false)
    }
  }, [file])

  const drift   = result?.drift || []
  const latest  = drift[drift.length - 1]

  const errorData = drift.map(d => ({
    month:    d.month,
    Current:  d.error_trend?.current_error,
    Baseline: d.error_trend?.baseline_error,
  }))

  const featureData = drift.map(d => ({
    month:  d.month,
    Severe: d.severe_features || 0,
    Mild:   d.mild_features   || 0,
  }))

  return (
    <>
      <div className="page-header">
        <div className="page-title">Upload & Monitor</div>
        <div className="page-sub">Upload a CSV to run the full pipeline and get instant drift detection results</div>
      </div>

      <div className="tabs">
        <div className={`tab${tab === 'upload'  ? ' active' : ''}`} onClick={() => setTab('upload')}>Upload & Run</div>
        <div className={`tab${tab === 'results' ? ' active' : ''}`} onClick={() => setTab('results')}>Prediction Results</div>
      </div>

      {tab === 'upload' && (
        <>
          <div
            className={`upload-zone${drag ? ' drag' : ''}`}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            onClick={onZoneClick}
          >
            <div className="upload-zone-icon">⬆</div>
            <p style={{ fontWeight: 600, color: 'var(--text)' }}>
              {file ? file.name : 'Drop a CSV here or click to browse'}
            </p>
            {file
              ? <p>{(file.size / 1024).toFixed(1)} KB · ready to run</p>
              : <p className="hint">Max {MAX_MB} MB · .csv only</p>
            }
            <input ref={inputRef} type="file" accept=".csv" style={{ display: 'none' }} onChange={onInputChange} />
          </div>

          {error && <div className="alert alert-r" style={{ marginTop: 12 }}>⚠ {error}</div>}

          {file && (
            <div style={{ marginTop: 14, display: 'flex', gap: 10, alignItems: 'center' }}>
              <button className="btn btn-primary" onClick={run} disabled={running}>
                {running ? '⟳ Running pipeline…' : '▶ Run Pipeline'}
              </button>
              <button className="btn btn-outline" onClick={() => { setFile(null); setError(null) }} disabled={running}>
                Clear
              </button>
            </div>
          )}

          {running && (
            <div className="alert alert-b" style={{ marginTop: 14 }}>
              Pipeline running — feature engineering + model inference + drift detection. This may take 30–60 s…
            </div>
          )}

          <SectionCard title="Expected CSV Format" style={{ marginTop: 24 }}>
            <table className="tbl">
              <thead><tr><th>Column</th><th>Type</th><th>Example</th></tr></thead>
              <tbody>
                {[
                  ['Store',        'integer', '1'],
                  ['Date',         'date',    '2011-02-04'],
                  ['Weekly_Sales', 'float',   '1643690.90'],
                  ['Holiday_Flag', '0 or 1',  '0'],
                  ['Temperature',  'float',   '42.31'],
                  ['Fuel_Price',   'float',   '2.572'],
                  ['CPI',          'float',   '211.096'],
                  ['Unemployment', 'float',   '8.106'],
                ].map(([col, type, ex]) => (
                  <tr key={col}>
                    <td className="mono" style={{ color: 'var(--blue)' }}>{col}</td>
                    <td style={{ color: 'var(--text3)' }}>{type}</td>
                    <td className="mono">{ex}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </SectionCard>
        </>
      )}

      {tab === 'results' && (
        <>
          {!result ? (
            <div className="alert alert-b">No results yet — upload a CSV and run the pipeline first.</div>
          ) : (
            <>
              {latest && (
                <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
                  <KPI label="Latest Month"    value={latest.month} />
                  <KPI label="Severity"        value={latest.severity?.toUpperCase()}
                    color={latest.severity === 'severe' ? 'var(--red)' : 'var(--orange)'} />
                  <KPI label="Severe Features" value={latest.severe_features} color="var(--red)" />
                  <KPI label="Error Increase"  value={'+' + ((latest.error_trend?.error_increase || 0) * 100).toFixed(0) + '%'}
                    color="var(--orange)" />
                </div>
              )}

              <div className="grid-2">
                <SectionCard title="MAE Trend After Upload">
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={errorData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} tickFormatter={v => '$' + (v / 1000).toFixed(0) + 'K'} />
                      <Tooltip {...CHART_STYLE} formatter={v => ['$' + Number(v).toLocaleString()]} />
                      <Legend />
                      <Line type="monotone" dataKey="Baseline" stroke="var(--green)" strokeWidth={2} dot={false} strokeDasharray="5 3" />
                      <Line type="monotone" dataKey="Current"  stroke="var(--red)"   strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </SectionCard>

                <SectionCard title="Drifted Features per Month">
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={featureData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip {...CHART_STYLE} />
                      <Legend />
                      <Bar dataKey="Severe" fill="var(--red)"    stackId="a" />
                      <Bar dataKey="Mild"   fill="var(--orange)" stackId="a" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </SectionCard>
              </div>

              <SectionCard title="Drift Results Table">
                <div style={{ overflowX: 'auto' }}>
                  <table className="tbl">
                    <thead>
                      <tr><th>Month</th><th>Severity</th><th>Severe Feats</th><th>Mild Feats</th><th>Current MAE</th><th>Error Increase</th></tr>
                    </thead>
                    <tbody>
                      {drift.map(d => (
                        <tr key={d.month}>
                          <td className="mono">{d.month}</td>
                          <td><SevBadge severity={d.severity} /></td>
                          <td style={{ color: 'var(--red)' }}>{d.severe_features}</td>
                          <td style={{ color: 'var(--orange)' }}>{d.mild_features}</td>
                          <td className="mono">{fmtD(d.error_trend?.current_error)}</td>
                          <td className="mono" style={{ color: 'var(--red)' }}>
                            +{((d.error_trend?.error_increase || 0) * 100).toFixed(0)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </SectionCard>

              {result.stdout && (
                <SectionCard title="Pipeline Output">
                  <pre style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text2)', whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto' }}>
                    {result.stdout}
                  </pre>
                </SectionCard>
              )}
            </>
          )}
        </>
      )}
    </>
  )
}
