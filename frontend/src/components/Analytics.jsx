import React, { useState, useEffect, useCallback } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { api } from '../api';

function Spinner() { return <span className="spinner" />; }
const C = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4'];

function Card({ title, children }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, marginBottom: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      {title && <h3 style={{ color: '#1f2937', margin: 0, marginBottom: 16, fontSize: 16, fontWeight: 600, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>{title}</h3>}
      {children}
    </div>
  );
}

function KPI({ label, value, sub, color = '#3b82f6' }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 14, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <div style={{ color: '#6b7280', fontSize: 11, marginBottom: 4 }}>{label}</div>
      <div style={{ color, fontSize: 20, fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ color: '#9ca3af', fontSize: 11, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

export default function Analytics() {
  const [status, setStatus] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [fi, setFi] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);

  const loadAll = useCallback(() => {
    Promise.all([api.status(), api.metrics(), api.fi()])
      .then(([s, m, f]) => {
        setStatus(s.data);
        setMetrics(m.data);
        setFi(f.data);
        setLastRefresh(new Date().toLocaleTimeString());
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Load on mount + auto-refresh every 5 seconds
  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 5000);
    return () => clearInterval(interval);
  }, [loadAll]);

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', gap: 8 }}><Spinner /><span style={{ color: '#6b7280' }}>Loading model analytics...</span></div>;

  const ds = status?.dataset || {};
  const fb = status?.feature_breakdown || {};
  const pred = status?.prediction || {};
  const acc = metrics ? (100 - metrics.mape).toFixed(1) : '0';
  const features = fi?.features || [];
  const engineered = features.filter(f => f.type === 'engineered');
  const aggregated = features.filter(f => f.type === 'aggregated');
  const raw = features.filter(f => f.type === 'raw');

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ color: '#1f2937', fontSize: 28, fontWeight: 700, margin: 0, marginBottom: 4 }}>Model Analytics</h1>
          <p style={{ color: '#6b7280', margin: 0, fontSize: 14 }}>Real-time model performance, features, and current state</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {lastRefresh && (
            <span style={{ color: '#9ca3af', fontSize: 11 }}>Updated: {lastRefresh}</span>
          )}
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', animation: 'pulse 2s infinite' }} />
          <span style={{ color: '#10b981', fontSize: 11, fontWeight: 600 }}>Live</span>
          <button onClick={loadAll} style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer', fontWeight: 600 }}>Refresh</button>
        </div>
      </div>

      {/* Current Model State */}
      <Card title="Current Model State">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
          <div style={{ background: '#f0f9ff', borderRadius: 8, padding: 12, border: '1px solid #3b82f6' }}>
            <div style={{ color: '#3b82f6', fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Model Type</div>
            <div style={{ color: '#1f2937', fontSize: 16, fontWeight: 700 }}>LightGBM</div>
            <div style={{ color: '#6b7280', fontSize: 11 }}>200 trees, depth 8, 31 leaves</div>
          </div>
          <div style={{ background: '#f0fdf4', borderRadius: 8, padding: 12, border: '1px solid #10b981' }}>
            <div style={{ color: '#10b981', fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Training Data</div>
            <div style={{ color: '#1f2937', fontSize: 16, fontWeight: 700 }}>{ds.train_date_range || 'N/A'}</div>
            <div style={{ color: '#6b7280', fontSize: 11 }}>{ds.total_orders?.toLocaleString() || 0} orders, {ds.daily_rows?.toLocaleString() || 0} daily rows</div>
          </div>
          <div style={{ background: '#fffbeb', borderRadius: 8, padding: 12, border: '1px solid #f59e0b' }}>
            <div style={{ color: '#f59e0b', fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Next Prediction</div>
            <div style={{ color: '#1f2937', fontSize: 16, fontWeight: 700 }}>{pred.predicting_month || ds.next_predict_month || 'N/A'}</div>
            <div style={{ color: '#6b7280', fontSize: 11 }}>{pred.total_predicted ? `$${pred.total_predicted.toLocaleString()} predicted` : 'Pending'}</div>
          </div>
          <div style={{ background: '#faf5ff', borderRadius: 8, padding: 12, border: '1px solid #8b5cf6' }}>
            <div style={{ color: '#8b5cf6', fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Last Action</div>
            <div style={{ color: '#1f2937', fontSize: 16, fontWeight: 700 }}>{status?.current_action || 'Ready'}</div>
            <div style={{ color: '#6b7280', fontSize: 11 }}>Current pipeline state</div>
          </div>
        </div>
      </Card>

      {/* Model Performance Metrics */}
      <Card title="Model Performance (Real-Time)">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, marginBottom: 16 }}>
          <KPI label="Accuracy" value={`${acc}%`} sub={`100% - ${metrics?.mape || 0}% MAPE`} color="#10b981" />
          <KPI label="MAE" value={`$${metrics?.mae || 0}`} sub="Mean Absolute Error" color="#ef4444" />
          <KPI label="RMSE" value={`$${metrics?.rmse || 0}`} sub="Root Mean Square Error" color="#f59e0b" />
          <KPI label="MAPE" value={`${metrics?.mape || 0}%`} sub="Mean Abs % Error" color="#3b82f6" />
          <KPI label="Total Features" value={fb.total || 19} sub={`${fb.raw || 5}R + ${fb.aggregated || 7}A + ${fb.engineered || 7}E`} color="#8b5cf6" />
          <KPI label="Training Size" value={ds.total_orders?.toLocaleString() || 0} sub="orders in training" color="#06b6d4" />
        </div>
        <div style={{ background: '#f9fafb', borderRadius: 8, padding: 12, border: '1px solid #e5e7eb', fontSize: 13, color: '#6b7280' }}>
          These metrics update in real-time. When you retrain or fine-tune the model in the Pipeline, the values here will reflect the new model performance immediately.
        </div>
      </Card>

      {/* Feature Importance */}
      <Card title={`Feature Importance (${features.length} Features)`}>
        {features.length > 0 ? (
          <>
            <ResponsiveContainer width="100%" height={450}>
              <BarChart data={features} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" stroke="#6b7280" fontSize={11} label={{ value: 'Importance Score', position: 'insideBottom', offset: -5, style: { fill: '#6b7280', fontSize: 10 } }} />
                <YAxis type="category" dataKey="feature" stroke="#6b7280" fontSize={10} width={130} label={{ value: 'Feature Name', angle: -90, position: 'insideLeft', offset: 15, style: { fill: '#6b7280', fontSize: 10 } }} />
                <Tooltip formatter={v => v.toFixed(4)} />
                <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
                  {features.map((f, i) => <Cell key={i} fill={f.type === 'engineered' ? '#10b981' : f.type === 'aggregated' ? '#f59e0b' : '#3b82f6'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center', fontSize: 12, marginTop: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}><div style={{ width: 12, height: 12, borderRadius: 3, background: '#3b82f6' }} /> Raw ({raw.length})</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}><div style={{ width: 12, height: 12, borderRadius: 3, background: '#f59e0b' }} /> Aggregated ({aggregated.length})</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}><div style={{ width: 12, height: 12, borderRadius: 3, background: '#10b981' }} /> Engineered ({engineered.length})</div>
            </div>
          </>
        ) : <div style={{ color: '#6b7280' }}>No feature data</div>}
      </Card>

      {/* Feature Breakdown + Errors side by side */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Feature Details Table */}
        <Card title="Feature Details">
          <div style={{ maxHeight: 400, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                  <th style={{ padding: '8px', textAlign: 'left', color: '#6b7280', fontSize: 11 }}>#</th>
                  <th style={{ padding: '8px', textAlign: 'left', color: '#6b7280', fontSize: 11 }}>Feature</th>
                  <th style={{ padding: '8px', textAlign: 'left', color: '#6b7280', fontSize: 11 }}>Type</th>
                  <th style={{ padding: '8px', textAlign: 'right', color: '#6b7280', fontSize: 11 }}>Importance</th>
                </tr>
              </thead>
              <tbody>
                {features.map((f, i) => (
                  <tr key={f.feature} style={{ borderBottom: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '6px 8px', color: '#6b7280' }}>{i + 1}</td>
                    <td style={{ padding: '6px 8px', color: '#1f2937', fontWeight: 500, fontFamily: 'monospace', fontSize: 11 }}>{f.feature}</td>
                    <td style={{ padding: '6px 8px' }}>
                      <span style={{
                        background: f.type === 'engineered' ? '#f0fdf4' : f.type === 'aggregated' ? '#fffbeb' : '#f0f9ff',
                        color: f.type === 'engineered' ? '#10b981' : f.type === 'aggregated' ? '#f59e0b' : '#3b82f6',
                        padding: '2px 6px', borderRadius: 4, fontSize: 10, fontWeight: 600
                      }}>{f.type}</span>
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', color: '#1f2937', fontWeight: 600 }}>{f.importance.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Error Segments + Insights */}
        <Card title="Model Insights">
          {/* Top Errors */}
          {metrics?.top_error_skus?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#1f2937', marginBottom: 8 }}>Highest Error Segments</div>
              {metrics.top_error_skus.map((s, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #f3f4f6', fontSize: 12 }}>
                  <span style={{ color: '#1f2937' }}>{i + 1}. {s.segment}</span>
                  <span style={{ color: '#ef4444', fontWeight: 600 }}>MAE: ${s.mae?.toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Insights */}
          <div style={{ fontSize: 13, fontWeight: 600, color: '#1f2937', marginBottom: 8 }}>Key Insights</div>
          {[
            { label: 'Top Feature', value: features[0] ? `${features[0].feature} (${features[0].type}) - ${(features[0].importance * 100).toFixed(1)}%` : 'N/A', color: '#10b981' },
            { label: 'Engineered Impact', value: `${engineered.length} features contribute ${(engineered.reduce((s, f) => s + f.importance, 0) * 100).toFixed(1)}% importance`, color: '#8b5cf6' },
            { label: 'Aggregated Impact', value: `${aggregated.length} features contribute ${(aggregated.reduce((s, f) => s + f.importance, 0) * 100).toFixed(1)}% importance`, color: '#f59e0b' },
            { label: 'Dataset Coverage', value: `${(ds.categories || []).join(', ')} across ${(ds.regions || []).join(', ')}`, color: '#3b82f6' },
            { label: 'Products Covered', value: `${ds.products?.toLocaleString() || 0} products, ${ds.sub_categories || 0} sub-categories`, color: '#06b6d4' },
          ].map(ins => (
            <div key={ins.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #f3f4f6', fontSize: 12 }}>
              <span style={{ color: ins.color, fontWeight: 600 }}>{ins.label}</span>
              <span style={{ color: '#6b7280', textAlign: 'right', maxWidth: '60%' }}>{ins.value}</span>
            </div>
          ))}
        </Card>
      </div>

      <style>{`@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }`}</style>
    </div>
  );
}
