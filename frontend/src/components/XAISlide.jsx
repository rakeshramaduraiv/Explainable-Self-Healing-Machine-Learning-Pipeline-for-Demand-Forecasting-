import React, { useState, useEffect, useCallback } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { api } from '../api';

function Spinner() { return <span className="spinner" />; }
const C = { engineered: '#10b981', aggregated: '#f59e0b', raw: '#3b82f6' };

function Card({ title, children }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, marginBottom: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      {title && <h3 style={{ color: '#1f2937', margin: 0, marginBottom: 16, fontSize: 16, fontWeight: 600, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>{title}</h3>}
      {children}
    </div>
  );
}

export default function XAISlide() {
  const [fi, setFi] = useState(null);
  const [drift, setDrift] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [driftLoading, setDriftLoading] = useState(false);

  const load = useCallback(() => {
    Promise.all([api.fi(), api.metrics(), api.status()])
      .then(([f, m, s]) => { setFi(f.data.features); setMetrics(m.data); setStatus(s.data); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); const iv = setInterval(load, 5000); return () => clearInterval(iv); }, [load]);

  const runDrift = async () => {
    setDriftLoading(true);
    try { const r = await api.drift(); setDrift(r.data); } catch (e) {}
    finally { setDriftLoading(false); }
  };

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', gap: 8 }}><Spinner /><span style={{ color: '#6b7280' }}>Loading XAI...</span></div>;

  const top5 = fi?.slice(0, 5) || [];
  const eng = fi?.filter(f => f.type === 'engineered') || [];
  const engImp = eng.reduce((s, f) => s + f.importance, 0);
  const pred = status?.prediction || {};
  const sevColor = { HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#10b981' };

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ color: '#1f2937', fontSize: 28, fontWeight: 700, margin: 0, marginBottom: 4 }}>XAI: Explainable AI</h1>
        <p style={{ color: '#6b7280', margin: 0, fontSize: 14 }}>Why the model predicts what it predicts, why drift happens, and why actions are taken</p>
      </div>

      {/* 1. Why This Prediction */}
      <Card title={`Why the Model Predicts ${pred.predicting_month || 'Next Month'}: $${(pred.total_predicted || 0).toLocaleString()}`}>
        <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 16 }}>
          The model uses 27 features to make predictions. These are the top features driving the current forecast:
        </p>
        {fi && (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={top5} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis type="number" stroke="#6b7280" fontSize={11} label={{ value: 'Importance Score (how much this feature drives predictions)', position: 'insideBottom', offset: -5, style: { fill: '#6b7280', fontSize: 10 } }} />
              <YAxis type="category" dataKey="feature" stroke="#6b7280" fontSize={11} width={140} label={{ value: 'Feature Name', angle: -90, position: 'insideLeft', offset: 20, style: { fill: '#6b7280', fontSize: 10 } }} />
              <Tooltip formatter={v => `${(v * 100).toFixed(1)}% importance`} />
              <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
                {top5.map((f, i) => <Cell key={i} fill={C[f.type] || '#6b7280'} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
        <div style={{ marginTop: 12 }}>
          {top5.map((f, i) => (
            <div key={f.feature} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #f3f4f6', fontSize: 13 }}>
              <div>
                <span style={{ color: C[f.type], fontWeight: 600 }}>{f.feature}</span>
                <span style={{ color: '#9ca3af', fontSize: 11, marginLeft: 8 }}>({f.type})</span>
              </div>
              <span style={{ color: '#1f2937', fontWeight: 600 }}>{(f.importance * 100).toFixed(1)}%</span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, padding: 12, background: '#f0f9ff', borderRadius: 8, border: '1px solid #3b82f6', fontSize: 13, color: '#1f2937' }}>
          <strong>Insight:</strong> {top5[0]?.feature || 'N/A'} ({top5[0]?.type}) is the strongest driver at {((top5[0]?.importance || 0) * 100).toFixed(1)}%.
          Engineered features contribute {(engImp * 100).toFixed(1)}% of total prediction power.
        </div>
      </Card>

      {/* 2. Drift Analysis - Why Performance Changes */}
      <Card title="Why Performance Changes (Drift Analysis)">
        <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 12 }}>
          Run drift detection to see which features have shifted between training data and recent data.
        </p>
        <button className="btn btn-primary" onClick={runDrift} disabled={driftLoading} style={{ marginBottom: 16 }}>
          {driftLoading ? <><Spinner /> Analyzing...</> : "Run Drift Analysis"}
        </button>

        {drift && (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 12, marginBottom: 16 }}>
              <div style={{ background: '#f9fafb', borderRadius: 8, padding: 12, textAlign: 'center', border: '1px solid #e5e7eb' }}>
                <div style={{ color: drift.level === 'low' ? '#10b981' : drift.level === 'medium' ? '#f59e0b' : '#ef4444', fontSize: 20, fontWeight: 700 }}>{drift.level?.toUpperCase()}</div>
                <div style={{ color: '#6b7280', fontSize: 11 }}>Drift Level</div>
              </div>
              <div style={{ background: '#f9fafb', borderRadius: 8, padding: 12, textAlign: 'center', border: '1px solid #e5e7eb' }}>
                <div style={{ color: '#3b82f6', fontSize: 20, fontWeight: 700 }}>{drift.drift_score}</div>
                <div style={{ color: '#6b7280', fontSize: 11 }}>Composite Score</div>
              </div>
              <div style={{ background: '#f9fafb', borderRadius: 8, padding: 12, textAlign: 'center', border: '1px solid #e5e7eb' }}>
                <div style={{ color: '#8b5cf6', fontSize: 20, fontWeight: 700 }}>{drift.action === 'monitor' ? 'Monitor' : drift.action === 'fine_tune' ? 'Fine-Tune' : 'Retrain'}</div>
                <div style={{ color: '#6b7280', fontSize: 11 }}>Recommended</div>
              </div>
              <div style={{ background: '#f9fafb', borderRadius: 8, padding: 12, textAlign: 'center', border: '1px solid #e5e7eb' }}>
                <div style={{ color: '#06b6d4', fontSize: 16, fontWeight: 700 }}>{drift.threshold_method === 'dynamic' ? 'Dynamic' : 'Static'}</div>
                <div style={{ color: '#6b7280', fontSize: 11 }}>Threshold (Run #{drift.drift_history_count || 1})</div>
              </div>
              {drift.thresholds && (
                <div style={{ background: '#f9fafb', borderRadius: 8, padding: 12, textAlign: 'center', border: '1px solid #e5e7eb' }}>
                  <div style={{ color: '#f59e0b', fontSize: 14, fontWeight: 700 }}>{drift.thresholds.medium} / {drift.thresholds.high}</div>
                  <div style={{ color: '#6b7280', fontSize: 11 }}>Med / High Thresholds</div>
                </div>
              )}
            </div>
            {drift.tests_used && (
              <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
                {drift.tests_used.map(t => (
                  <span key={t} style={{ background: '#f0f9ff', color: '#3b82f6', padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, border: '1px solid #3b82f6' }}>{t}</span>
                ))}
                <span style={{ color: '#6b7280', fontSize: 11, alignSelf: 'center' }}>Composite = max(KS, JS, PSI/0.25) per feature, Overall = max(features)</span>
              </div>
            )}

            {drift.accuracy_drop !== undefined && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 12 }}>
                <div style={{ background: '#f9fafb', borderRadius: 8, padding: 10, textAlign: 'center', border: '1px solid #e5e7eb' }}>
                  <div style={{ color: '#ef4444', fontSize: 16, fontWeight: 700 }}>{(drift.accuracy_drop * 100).toFixed(1)}%</div>
                  <div style={{ color: '#6b7280', fontSize: 11 }}>Accuracy Drop</div>
                </div>
                <div style={{ background: '#f9fafb', borderRadius: 8, padding: 10, textAlign: 'center', border: '1px solid #e5e7eb' }}>
                  <div style={{ color: '#3b82f6', fontSize: 16, fontWeight: 700 }}>${drift.baseline_mae}</div>
                  <div style={{ color: '#6b7280', fontSize: 11 }}>Baseline MAE</div>
                </div>
                <div style={{ background: '#f9fafb', borderRadius: 8, padding: 10, textAlign: 'center', border: '1px solid #e5e7eb' }}>
                  <div style={{ color: drift.high_feature_count >= 2 ? '#ef4444' : '#10b981', fontSize: 16, fontWeight: 700 }}>{drift.high_feature_count}</div>
                  <div style={{ color: '#6b7280', fontSize: 11 }}>Features HIGH</div>
                </div>
              </div>
            )}

            {(drift.top_drift_features || []).length > 0 && (
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#1f2937', marginBottom: 8 }}>Which Features Drifted and Why</div>
                {drift.top_drift_features.map(fd => (
                  <div key={fd.feature} style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 8, padding: 12, marginBottom: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{ color: '#1f2937', fontWeight: 600, fontSize: 14 }}>{fd.feature}</span>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span style={{ background: sevColor[fd.severity] + '20', color: sevColor[fd.severity], padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600 }}>{fd.severity}{drift.threshold_method === 'dynamic' ? ' (adaptive)' : ''}</span>
                        <span style={{ color: '#6b7280', fontSize: 11 }}>C: {fd.composite}</span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#6b7280', marginBottom: 4 }}>
                      <span>KS: {fd.ks_stat}</span>
                      <span>PSI: {fd.psi}</span>
                      <span>JS: {fd.js_divergence}</span>
                    </div>
                    <div style={{ color: '#6b7280', fontSize: 12 }}>
                      {fd.feature === 'dayofweek' && 'Day-of-week distribution shifted — different shopping day patterns'}
                      {fd.feature === 'month' && 'Monthly seasonality changed — different time of year patterns'}
                      {fd.feature === 'order_count' && 'Number of daily orders changed — demand volume shift'}
                      {fd.feature === 'avg_order_value' && 'Average order value shifted — buying behavior change'}
                      {fd.feature === 'ship_speed' && 'Shipping speed preferences changed — urgency shift'}
                      {fd.feature === 'segment_encoded' && 'Customer segment mix changed — different buyer types'}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div style={{ marginTop: 12, padding: 12, background: drift.level === 'low' ? '#f0fdf4' : drift.level === 'medium' ? '#fffbeb' : '#fef2f2', borderRadius: 8, border: `1px solid ${drift.level === 'low' ? '#10b981' : drift.level === 'medium' ? '#f59e0b' : '#ef4444'}`, fontSize: 13 }}>
              <strong>Action Explanation:</strong>{' '}
              {drift.level === 'low' && 'Feature drift minimal and accuracy stable (<5% drop). Model is still accurate — continue monitoring.'}
              {drift.level === 'medium' && 'Moderate drift or accuracy drop (<15%). Fine-tuning on last 9 months will adjust to recent patterns.'}
              {drift.level === 'high' && 'Significant drift or accuracy degradation. Full retrain on last 12 months (sliding window) to capture new patterns.'}
            </div>
            <div style={{ marginTop: 8, padding: 10, background: '#f0f9ff', borderRadius: 8, border: '1px solid #3b82f6', fontSize: 12, color: '#1f2937' }}>
              <strong>Threshold Method:</strong> {drift.threshold_method === 'dynamic' ? `Dynamic (μ+0.5σ/μ+1.5σ from last ${drift.drift_history_count} runs, σ≥0.03). Boundaries: medium ≥ ${drift.thresholds?.medium}, high ≥ ${drift.thresholds?.high}` : `Static (first runs — building history). Boundaries: medium ≥ 0.1, high ≥ 0.2. After 2 runs, switches to adaptive.`}
              {drift.accuracy_drop !== undefined && <><br/><strong>Decision Logic:</strong> drift={drift.drift_score} + accuracy_drop={(drift.accuracy_drop * 100).toFixed(1)}% + {drift.high_feature_count} features HIGH → {drift.action}</>}
            </div>
          </div>
        )}
      </Card>

      {/* 3. Full Feature Importance */}
      <Card title="Complete Feature Importance (Real-Time)">
        <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 12 }}>
          All 27 features ranked by their contribution to predictions. Updates after retrain/fine-tune.
        </p>
        {fi && (
          <>
            <ResponsiveContainer width="100%" height={500}>
              <BarChart data={fi} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" stroke="#6b7280" fontSize={11} label={{ value: 'Importance Score (contribution to prediction)', position: 'insideBottom', offset: -5, style: { fill: '#6b7280', fontSize: 10 } }} />
                <YAxis type="category" dataKey="feature" stroke="#6b7280" fontSize={9} width={140} label={{ value: 'Feature Name', angle: -90, position: 'insideLeft', offset: 20, style: { fill: '#6b7280', fontSize: 10 } }} />
                <Tooltip formatter={v => `${(v * 100).toFixed(1)}%`} />
                <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
                  {fi.map((f, i) => <Cell key={i} fill={C[f.type] || '#6b7280'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center', fontSize: 11, marginTop: 8 }}>
              {[['Raw (7)', '#3b82f6'], ['Aggregated (9)', '#f59e0b'], ['Engineered (11)', '#10b981']].map(([l, c]) => (
                <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 4 }}><div style={{ width: 10, height: 10, borderRadius: 3, background: c }} />{l}</div>
              ))}
            </div>
          </>
        )}
      </Card>

      {/* 4. Model Performance Context */}
      <Card title="Current Model Performance">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
          {[
            { label: 'Accuracy', value: `${(100 - (metrics?.mape || 0)).toFixed(1)}%`, color: '#10b981' },
            { label: 'MAE', value: `$${metrics?.mae || 0}`, color: '#ef4444' },
            { label: 'RMSE', value: `$${metrics?.rmse || 0}`, color: '#f59e0b' },
            { label: 'Features', value: '27', color: '#3b82f6' },
            { label: 'Engineered Impact', value: `${(engImp * 100).toFixed(1)}%`, color: '#10b981' },
          ].map(m => (
            <div key={m.label} style={{ background: '#f9fafb', borderRadius: 8, padding: 12, textAlign: 'center', border: '1px solid #e5e7eb' }}>
              <div style={{ color: m.color, fontSize: 20, fontWeight: 700 }}>{m.value}</div>
              <div style={{ color: '#6b7280', fontSize: 11 }}>{m.label}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
