import React, { useState, useEffect, useCallback } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { api } from '../api';

function Spinner() { return <span className="spinner" />; }
const actColor = { monitor: '#10b981', fine_tune: '#f59e0b', retrain: '#ef4444', baseline: '#3b82f6' };
const lvColor = { LOW: '#10b981', MEDIUM: '#f59e0b', HIGH: '#ef4444', 'N/A': '#6b7280' };

function Card({ title, children }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, marginBottom: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      {title && <h3 style={{ color: '#1f2937', margin: 0, marginBottom: 16, fontSize: 16, fontWeight: 600, paddingBottom: 12, borderBottom: '1px solid #e5e7eb' }}>{title}</h3>}
      {children}
    </div>
  );
}

export default function Logbook() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);

  const load = useCallback(() => {
    api.logbook().then(r => setEntries(r.data.entries || [])).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); const iv = setInterval(load, 5000); return () => clearInterval(iv); }, [load]);

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', gap: 8 }}><Spinner /><span style={{ color: '#6b7280' }}>Loading logbook...</span></div>;

  // Chart data from entries
  const maeData = entries.filter(e => e.mae_before).map((e, i) => ({ cycle: i + 1, mae: e.mae_before, label: e.timestamp }));
  const driftData = entries.filter(e => e.drift_score > 0).map((e, i) => ({ cycle: i + 1, drift: e.drift_score, label: e.timestamp }));
  const actionData = entries.map((e, i) => ({ cycle: i + 1, action: e.action_taken, label: e.timestamp, value: e.action_taken === 'retrain' ? 3 : e.action_taken === 'fine_tune' ? 2 : 1 }));

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ color: '#1f2937', fontSize: 28, fontWeight: 700, margin: 0, marginBottom: 4 }}>Pipeline Logbook</h1>
        <p style={{ color: '#6b7280', margin: 0, fontSize: 14 }}>Complete audit trail: what happened, when, why, and what action was taken</p>
      </div>

      {/* Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Total Cycles', value: entries.length, color: '#3b82f6' },
          { label: 'Monitor', value: entries.filter(e => e.action_taken === 'monitor').length, color: '#10b981' },
          { label: 'Fine-Tune', value: entries.filter(e => e.action_taken === 'fine_tune').length, color: '#f59e0b' },
          { label: 'Retrain', value: entries.filter(e => e.action_taken === 'retrain').length, color: '#ef4444' },
          { label: 'Baseline', value: entries.filter(e => e.action_taken === 'baseline').length, color: '#3b82f6' },
        ].map(s => (
          <div key={s.label} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 14, textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <div style={{ color: s.color, fontSize: 22, fontWeight: 700 }}>{s.value}</div>
            <div style={{ color: '#6b7280', fontSize: 11 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        {/* MAE Over Time */}
        {maeData.length > 1 && (
          <Card title="MAE Over Time">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={maeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="cycle" stroke="#6b7280" fontSize={11} label={{ value: 'Cycle', position: 'insideBottom', offset: -5, style: { fill: '#6b7280', fontSize: 11 } }} />
                <YAxis stroke="#6b7280" fontSize={11} label={{ value: 'MAE ($)', angle: -90, position: 'insideLeft', style: { fill: '#6b7280', fontSize: 11 } }} />
                <Tooltip formatter={v => `$${v}`} />
                <Line type="monotone" dataKey="mae" stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        )}

        {/* Drift Score Over Time */}
        {driftData.length > 1 && (
          <Card title="Drift Score Over Time">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={driftData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="cycle" stroke="#6b7280" fontSize={11} label={{ value: 'Pipeline Cycle', position: 'insideBottom', offset: -5, style: { fill: '#6b7280', fontSize: 10 } }} />
                <YAxis stroke="#6b7280" fontSize={11} label={{ value: 'Drift Score (0=no drift, 1=max drift)', angle: -90, position: 'insideLeft', style: { fill: '#6b7280', fontSize: 10 } }} />
                <Tooltip formatter={v => v.toFixed(4)} />
                <Line type="monotone" dataKey="drift" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        )}
      </div>

      {/* Action Timeline */}
      {actionData.length > 1 && (
        <Card title="Action Timeline">
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={actionData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="cycle" stroke="#6b7280" fontSize={11} label={{ value: 'Pipeline Cycle', position: 'insideBottom', offset: -5, style: { fill: '#6b7280', fontSize: 10 } }} />
              <YAxis stroke="#6b7280" fontSize={11} ticks={[1, 2, 3]} tickFormatter={v => v === 1 ? 'Monitor' : v === 2 ? 'Tune' : 'Retrain'} label={{ value: 'Action Taken', angle: -90, position: 'insideLeft', style: { fill: '#6b7280', fontSize: 10 } }} />
              <Tooltip formatter={(v, name, props) => props.payload.action} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {actionData.map((d, i) => <Cell key={i} fill={actColor[d.action] || '#6b7280'} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', fontSize: 11, marginTop: 4 }}>
            {[['Monitor', '#10b981'], ['Fine-Tune', '#f59e0b'], ['Retrain', '#ef4444']].map(([l, c]) => (
              <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 4 }}><div style={{ width: 10, height: 10, borderRadius: 3, background: c }} />{l}</div>
            ))}
          </div>
        </Card>
      )}

      {/* Log Entries */}
      <Card title={`Log Entries (${entries.length})`}>
        {entries.length === 0 ? (
          <div style={{ color: '#6b7280', textAlign: 'center', padding: 40 }}>No entries yet. Run the pipeline to generate logs.</div>
        ) : (
          entries.slice().reverse().map((e, i) => {
            const open = expanded === i;
            return (
              <div key={i} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 10, marginBottom: 10, overflow: 'hidden' }}>
                <div onClick={() => setExpanded(open ? null : i)} style={{ padding: 14, cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ color: '#6b7280', fontSize: 12 }}>{e.timestamp}</span>
                    <span style={{ background: (lvColor[e.drift_level] || '#6b7280') + '20', color: lvColor[e.drift_level] || '#6b7280', padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600 }}>{e.drift_level}</span>
                    <span style={{ background: (actColor[e.action_taken] || '#6b7280') + '20', color: actColor[e.action_taken] || '#6b7280', padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600 }}>{e.action_label}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    {e.mae_before > 0 && <span style={{ color: '#6b7280', fontSize: 12 }}>MAE: ${e.mae_before}</span>}
                    <span style={{ color: '#6b7280', transform: open ? 'rotate(180deg)' : '', transition: 'transform 0.2s' }}>▼</span>
                  </div>
                </div>

                {open && (
                  <div style={{ padding: 14, background: '#f9fafb', borderTop: '1px solid #e5e7eb' }}>
                    {e.drift_score > 0 && (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 12 }}>
                        <div><div style={{ color: '#3b82f6', fontSize: 16, fontWeight: 600 }}>{e.drift_score}</div><div style={{ color: '#6b7280', fontSize: 11 }}>Drift Score</div></div>
                        <div><div style={{ color: '#ef4444', fontSize: 16, fontWeight: 600 }}>${e.mae_before}</div><div style={{ color: '#6b7280', fontSize: 11 }}>MAE</div></div>
                        <div><div style={{ color: actColor[e.action_taken], fontSize: 16, fontWeight: 600 }}>{e.action_label}</div><div style={{ color: '#6b7280', fontSize: 11 }}>Action</div></div>
                      </div>
                    )}

                    {e.action_why && (
                      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: 12, marginBottom: 8 }}>
                        <div style={{ color: '#1f2937', fontWeight: 600, fontSize: 13, marginBottom: 4 }}>Why this action?</div>
                        <div style={{ color: '#6b7280', fontSize: 13 }}>{e.action_why}</div>
                      </div>
                    )}

                    {e.plain_english && (
                      <div style={{ background: '#f0f9ff', border: '1px solid #3b82f6', borderRadius: 8, padding: 12, marginBottom: 8 }}>
                        <div style={{ color: '#3b82f6', fontWeight: 600, fontSize: 13, marginBottom: 4 }}>Summary</div>
                        <div style={{ color: '#6b7280', fontSize: 13 }}>{e.plain_english}</div>
                      </div>
                    )}

                    {e.top_drift_features?.length > 0 && (
                      <div>
                        <div style={{ color: '#1f2937', fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Drifted Features</div>
                        {e.top_drift_features.map((f, j) => (
                          <div key={j} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12, borderBottom: '1px solid #f3f4f6' }}>
                            <span style={{ color: '#1f2937' }}>{f.feature}</span>
                            <div style={{ display: 'flex', gap: 8 }}>
                              <span style={{ color: lvColor[f.severity], fontWeight: 600 }}>{f.severity}</span>
                              <span style={{ color: '#6b7280' }}>KS: {f.ks_stat}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </Card>
    </div>
  );
}
