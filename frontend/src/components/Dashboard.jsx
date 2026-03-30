import React, { useState, useEffect } from 'react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
         XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
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
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <div style={{ color: '#6b7280', fontSize: 12, marginBottom: 4 }}>{label}</div>
      <div style={{ color, fontSize: 22, fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ color: '#9ca3af', fontSize: 11, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [fi, setFi] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = () => {
      Promise.all([api.status(), api.metrics(), api.fi()])
        .then(([s, m, f]) => { setData(s.data); setMetrics(m.data); setFi(f.data); setLoading(false); })
        .catch(() => { setLoading(false); setTimeout(load, 2000); });
    };
    load();
  }, []);

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', gap: 8 }}><Spinner /><span style={{ color: '#6b7280' }}>Connecting to backend...</span></div>;
  if (!data) return <div style={{ padding: 24 }}><div style={{ background: '#fef2f2', border: '1px solid #ef4444', borderRadius: 12, padding: 20, textAlign: 'center' }}><div style={{ color: '#ef4444', fontSize: 18, fontWeight: 600 }}>Backend Not Connected</div><div style={{ color: '#6b7280', fontSize: 14, marginTop: 8 }}>Run: venv\Scripts\python backend_minimal.py</div></div></div>;

  const ds = data.dataset || {};
  const fb = data.feature_breakdown || {};
  const pred = data.prediction || {};
  const acc = metrics ? (100 - metrics.mape).toFixed(1) : '0';

  return (
    <div style={{ padding: 24 }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ color: '#1f2937', fontSize: 28, fontWeight: 700, margin: 0, marginBottom: 4 }}>Sales Forecasting Dashboard</h1>
        <p style={{ color: '#6b7280', margin: 0, fontSize: 14 }}>Baseline model info, training dataset, and next month prediction</p>
      </div>

      {/* ══════ SECTION 1: MODEL INFO ══════ */}
      <Card title="Model Information">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
          <KPI label="Model Type" value="LightGBM" sub="200 trees, depth 8" color="#3b82f6" />
          <KPI label="Accuracy" value={`${acc}%`} sub={`MAPE: ${metrics?.mape || 0}%`} color="#10b981" />
          <KPI label="MAE" value={`$${metrics?.mae || 0}`} sub="Mean Absolute Error" color="#ef4444" />
          <KPI label="RMSE" value={`$${metrics?.rmse || 0}`} sub="Root Mean Square Error" color="#f59e0b" />
          <KPI label="Total Features" value={fb.total || 19} sub={`${fb.raw || 5} raw + ${fb.aggregated || 7} agg + ${fb.engineered || 7} eng`} color="#8b5cf6" />
          <KPI label="Engineered" value={fb.engineered || 7} sub="Real feature engineering" color="#06b6d4" />
        </div>
      </Card>

      {/* ══════ SECTION 2: TRAINING DATASET INFO ══════ */}
      <Card title="Training Dataset (Baseline)">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 16 }}>
          <KPI label="Training Period" value={ds.train_date_range || 'N/A'} color="#1f2937" />
          <KPI label="Total Orders" value={(ds.total_orders || 0).toLocaleString()} color="#3b82f6" />
          <KPI label="Total Sales" value={`$${(ds.total_sales || 0).toLocaleString()}`} color="#10b981" />
          <KPI label="Products" value={(ds.products || 0).toLocaleString()} sub={`${ds.sub_categories || 0} sub-categories`} color="#f59e0b" />
          <KPI label="Customers" value={(ds.customers || 0).toLocaleString()} sub={`${ds.states || 0} states`} color="#8b5cf6" />
          <KPI label="Segments" value={(ds.segments || []).join(', ')} color="#6b7280" />
        </div>

        {/* Category + Region side by side */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* Category Sales */}
          <div>
            <h4 style={{ color: '#1f2937', margin: '0 0 8px', fontSize: 14 }}>Sales by Category</h4>
            {(ds.cat_sales || []).length > 0 && (
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={ds.cat_sales}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="category" stroke="#6b7280" fontSize={11} />
                  <YAxis stroke="#6b7280" fontSize={10} tickFormatter={v => `$${(v/1000).toFixed(0)}K`} />
                  <Tooltip formatter={v => `$${v.toLocaleString()}`} />
                  <Bar dataKey="total" radius={[4,4,0,0]}>{(ds.cat_sales||[]).map((_,i) => <Cell key={i} fill={C[i]} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
            {(ds.cat_sales || []).map((c, i) => (
              <div key={c.category} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12, borderBottom: '1px solid #f3f4f6' }}>
                <span style={{ color: C[i], fontWeight: 600 }}>{c.category}</span>
                <span style={{ color: '#6b7280' }}>${c.total.toLocaleString()} | {c.orders} orders</span>
              </div>
            ))}
          </div>

          {/* Region Sales */}
          <div>
            <h4 style={{ color: '#1f2937', margin: '0 0 8px', fontSize: 14 }}>Sales by Region</h4>
            {(ds.region_sales || []).length > 0 && (
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie data={(ds.region_sales||[]).map(r => ({name: r.region, value: r.total}))} cx="50%" cy="50%" outerRadius={65} dataKey="value" label={({name}) => name}>
                    {(ds.region_sales||[]).map((_,i) => <Cell key={i} fill={C[(i+1)%C.length]} />)}
                  </Pie>
                  <Tooltip formatter={v => `$${v.toLocaleString()}`} />
                </PieChart>
              </ResponsiveContainer>
            )}
            {(ds.region_sales || []).map((r, i) => (
              <div key={r.region} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12, borderBottom: '1px solid #f3f4f6' }}>
                <span style={{ color: C[(i+1)%C.length], fontWeight: 600 }}>{r.region}</span>
                <span style={{ color: '#6b7280' }}>${r.total.toLocaleString()} | {r.orders} orders</span>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {/* Monthly Trend + Top Sub-Categories */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        {(ds.monthly_sales || []).length > 0 && (
          <Card title="Monthly Sales Trend (Training Data)">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={ds.monthly_sales}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" stroke="#6b7280" fontSize={8} angle={-45} textAnchor="end" height={50} />
                <YAxis stroke="#6b7280" fontSize={10} tickFormatter={v => `$${(v/1000).toFixed(0)}K`} />
                <Tooltip formatter={v => `$${v.toLocaleString()}`} />
                <Line type="monotone" dataKey="total" stroke="#3b82f6" strokeWidth={2} dot={{r:1}} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        )}

        {(ds.top_sub_categories || []).length > 0 && (
          <Card title="Top 10 Sub-Categories (Training Data)">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={ds.top_sub_categories} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" stroke="#6b7280" fontSize={10} tickFormatter={v => `$${(v/1000).toFixed(0)}K`} />
                <YAxis type="category" dataKey="sub_category" stroke="#6b7280" fontSize={10} width={90} />
                <Tooltip formatter={v => `$${v.toLocaleString()}`} />
                <Bar dataKey="total" fill="#3b82f6" radius={[0,4,4,0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        )}
      </div>

      {/* ══════ SECTION 3: NEXT MONTH PREDICTION ══════ */}
      {pred.predicting_month && (
        <Card title={`Next Month Prediction: ${pred.predicting_month}`}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 16 }}>
            <KPI label="Total Predicted" value={`$${(pred.total_predicted||0).toLocaleString()}`} sub={`${pred.date_min} to ${pred.date_max}`} color="#10b981" />
            <KPI label="Avg Daily" value={`$${pred.mean_daily||0}`} color="#3b82f6" />
            <KPI label="Categories" value={pred.total_categories||0} color="#f59e0b" />
            <KPI label="Regions" value={pred.total_regions||0} color="#8b5cf6" />
          </div>

          {/* Daily Prediction Line Chart */}
          {(pred.daily_chart || []).length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <h4 style={{ color: '#1f2937', margin: '0 0 8px', fontSize: 14 }}>Daily Predicted Sales - {pred.predicting_month}</h4>
              <p style={{ color: '#6b7280', fontSize: 12, margin: '0 0 8px' }}>Total predicted sales per day across all categories and regions</p>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={pred.daily_chart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="day" stroke="#6b7280" fontSize={11} label={{ value: `Day of ${pred.predicting_month}`, position: 'insideBottom', offset: -5, style: { fill: '#6b7280', fontSize: 11 } }} />
                  <YAxis stroke="#6b7280" fontSize={10} tickFormatter={v => `$${(v/1000).toFixed(0)}K`} label={{ value: 'Predicted Sales ($)', angle: -90, position: 'insideLeft', style: { fill: '#6b7280', fontSize: 11 } }} />
                  <Tooltip formatter={v => `$${Number(v).toLocaleString()}`} labelFormatter={v => `Day ${v}`} />
                  <Line type="monotone" dataKey="predicted" stroke="#10b981" strokeWidth={2} dot={{ r: 3, fill: '#10b981' }} name="Predicted Sales" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Category Daily Trend Line Chart */}
          {(pred.cat_daily_chart || []).length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <h4 style={{ color: '#1f2937', margin: '0 0 8px', fontSize: 14 }}>Daily Prediction by Category - {pred.predicting_month}</h4>
              <p style={{ color: '#6b7280', fontSize: 12, margin: '0 0 8px' }}>How each product category is predicted to perform day by day</p>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={
                  // Pivot cat_daily_chart into {day, Furniture, Office Supplies, Technology}
                  Object.values((pred.cat_daily_chart || []).reduce((acc, r) => {
                    if (!acc[r.day]) acc[r.day] = { day: r.day };
                    acc[r.day][r.category] = r.predicted;
                    return acc;
                  }, {})).sort((a, b) => a.day - b.day)
                }>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="day" stroke="#6b7280" fontSize={11} label={{ value: `Day of ${pred.predicting_month}`, position: 'insideBottom', offset: -5, style: { fill: '#6b7280', fontSize: 11 } }} />
                  <YAxis stroke="#6b7280" fontSize={10} tickFormatter={v => `$${(v/1000).toFixed(0)}K`} label={{ value: 'Predicted Sales ($)', angle: -90, position: 'insideLeft', style: { fill: '#6b7280', fontSize: 11 } }} />
                  <Tooltip formatter={v => `$${Number(v).toLocaleString()}`} labelFormatter={v => `Day ${v}`} />
                  {(pred.cat_summary || []).map((c, i) => (
                    <Line key={c.category} type="monotone" dataKey={c.category} stroke={C[i]} strokeWidth={2} dot={{ r: 2 }} name={c.category} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
              <div style={{ display: 'flex', gap: 16, justifyContent: 'center', fontSize: 11, marginTop: 4 }}>
                {(pred.cat_summary || []).map((c, i) => (
                  <div key={c.category} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{ width: 10, height: 10, borderRadius: 3, background: C[i] }} />{c.category}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            {/* Prediction by Category */}
            <div>
              <h4 style={{ color: '#1f2937', margin: '0 0 8px', fontSize: 14 }}>Predicted by Category</h4>
              {(pred.cat_summary || []).length > 0 && (
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={pred.cat_summary}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="category" stroke="#6b7280" fontSize={11} />
                    <YAxis stroke="#6b7280" fontSize={10} tickFormatter={v => `$${(v/1000).toFixed(0)}K`} />
                    <Tooltip formatter={v => `$${v.toLocaleString()}`} />
                    <Bar dataKey="total_predicted" radius={[4,4,0,0]}>{(pred.cat_summary||[]).map((_,i) => <Cell key={i} fill={C[i]} />)}</Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
              {(pred.cat_summary || []).map((c, i) => (
                <div key={c.category} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12, borderBottom: '1px solid #f3f4f6' }}>
                  <span style={{ color: C[i], fontWeight: 600 }}>{c.category}</span>
                  <span style={{ color: '#6b7280' }}>${c.total_predicted?.toLocaleString()} (avg ${c.avg_daily}/day)</span>
                </div>
              ))}
            </div>

            {/* Prediction by Region */}
            <div>
              <h4 style={{ color: '#1f2937', margin: '0 0 8px', fontSize: 14 }}>Predicted by Region</h4>
              {(pred.region_summary || []).length > 0 && (
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={pred.region_summary}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="region" stroke="#6b7280" fontSize={11} />
                    <YAxis stroke="#6b7280" fontSize={10} tickFormatter={v => `$${(v/1000).toFixed(0)}K`} />
                    <Tooltip formatter={v => `$${v.toLocaleString()}`} />
                    <Bar dataKey="total_predicted" radius={[4,4,0,0]}>{(pred.region_summary||[]).map((_,i) => <Cell key={i} fill={C[(i+1)%C.length]} />)}</Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
              {(pred.region_summary || []).map((r, i) => (
                <div key={r.region} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12, borderBottom: '1px solid #f3f4f6' }}>
                  <span style={{ color: C[(i+1)%C.length], fontWeight: 600 }}>{r.region}</span>
                  <span style={{ color: '#6b7280' }}>${r.total_predicted?.toLocaleString()} (avg ${r.avg_daily}/day)</span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ marginTop: 16, padding: 12, background: '#fffbeb', borderRadius: 8, border: '1px solid #f59e0b', fontSize: 13, color: '#92400e' }}>
            Go to <strong>Pipeline</strong> tab to upload actual {pred.predicting_month} data and evaluate this prediction.
          </div>
        </Card>
      )}

      {/* ══════ SECTION 4: FEATURE IMPORTANCE + ERRORS ══════ */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {(fi?.features || []).length > 0 && (
          <Card title="Feature Importance (Trained Model)">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={fi.features.slice(0, 10)} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" stroke="#6b7280" fontSize={10} />
                <YAxis type="category" dataKey="feature" stroke="#6b7280" fontSize={10} width={120} />
                <Tooltip formatter={v => v.toFixed(4)} />
                <Bar dataKey="importance" radius={[0,4,4,0]}>
                  {fi.features.slice(0,10).map((f,i) => <Cell key={i} fill={f.type==='engineered'?'#10b981':f.type==='aggregated'?'#f59e0b':'#3b82f6'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center', fontSize: 11, marginTop: 4 }}>
              {[['Raw','#3b82f6'],['Aggregated','#f59e0b'],['Engineered','#10b981']].map(([l,c]) => (
                <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 4 }}><div style={{ width: 10, height: 10, borderRadius: 3, background: c }} />{l}</div>
              ))}
            </div>
          </Card>
        )}

        {metrics?.top_error_skus?.length > 0 && (
          <Card title="Highest Error Segments">
            {metrics.top_error_skus.map((r, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f3f4f6', fontSize: 13 }}>
                <span style={{ color: '#1f2937' }}>{i+1}. {r.segment}</span>
                <span style={{ color: '#ef4444', fontWeight: 600 }}>MAE: ${r.mae?.toFixed(2)}</span>
              </div>
            ))}
          </Card>
        )}
      </div>
    </div>
  );
}
