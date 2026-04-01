import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { api } from '../api';

function Spinner() { return <span className="spinner" />; }

const FEATURES = [
  // Raw (7)
  { feature: 'dayofweek', name: 'Day of Week', type: 'RAW', source: 'Order Date', how: 'Monday=0, Sunday=6', why: 'Weekend vs weekday shopping patterns' },
  { feature: 'month', name: 'Month', type: 'RAW', source: 'Order Date', how: 'January=1, December=12', why: 'Seasonal demand patterns' },
  { feature: 'year', name: 'Year', type: 'RAW', source: 'Order Date', how: '2015-2018', why: 'Long-term growth trends' },
  { feature: 'order_count', name: 'Daily Order Count', type: 'RAW', source: 'Order ID', how: 'Unique orders per day per segment', why: 'Demand volume signal' },
  { feature: 'avg_order_value', name: 'Avg Order Value', type: 'RAW', source: 'Sales', how: 'Mean sales per order that day', why: 'High-value vs low-value buying behavior' },
  { feature: 'ship_speed', name: 'Shipping Speed', type: 'RAW', source: 'Ship Mode', how: 'Same Day=4, First=3, Second=2, Standard=1', why: 'Urgency of orders indicates demand type' },
  { feature: 'segment_encoded', name: 'Customer Segment', type: 'RAW', source: 'Segment', how: 'Consumer=0, Corporate=1, Home Office=2', why: 'Different segments have different buying patterns' },
  // Aggregated (9)
  { feature: 'lag_1', name: "Yesterday's Sales", type: 'AGGREGATED', source: 'Sales history', how: 'Sales 1 day ago', why: 'Immediate momentum signal' },
  { feature: 'lag_7', name: 'Same Day Last Week', type: 'AGGREGATED', source: 'Sales history', how: 'Sales 7 days ago', why: 'Weekly cycle pattern' },
  { feature: 'lag_14', name: 'Two Weeks Ago', type: 'AGGREGATED', source: 'Sales history', how: 'Sales 14 days ago', why: 'Bi-weekly pattern capture' },
  { feature: 'lag_28', name: 'Same Day Last Month', type: 'AGGREGATED', source: 'Sales history', how: 'Sales 28 days ago', why: 'Monthly cycle pattern' },
  { feature: 'rmean_3', name: '3-Day Average', type: 'AGGREGATED', source: 'Sales history', how: 'Mean of last 3 days', why: 'Very short-term trend' },
  { feature: 'rmean_7', name: '7-Day Average', type: 'AGGREGATED', source: 'Sales history', how: 'Mean of last 7 days', why: 'Short-term trend direction' },
  { feature: 'rmean_14', name: '14-Day Average', type: 'AGGREGATED', source: 'Sales history', how: 'Mean of last 14 days', why: 'Medium-term trend' },
  { feature: 'rmean_28', name: '28-Day Average', type: 'AGGREGATED', source: 'Sales history', how: 'Mean of last 28 days', why: 'Long-term baseline demand' },
  { feature: 'rstd_7', name: '7-Day Std Dev', type: 'AGGREGATED', source: 'Sales history', how: 'Std deviation of last 7 days', why: 'Sales volatility measure' },
  // Engineered (11)
  { feature: 'sales_momentum', name: 'Sales Momentum', type: 'ENGINEERED', source: 'rmean_7 - rmean_28', how: 'Short avg minus long avg', why: 'Positive=rising demand, Negative=falling' },
  { feature: 'sales_volatility', name: 'Sales Volatility', type: 'ENGINEERED', source: 'rstd_7 / (rmean_7+1)', how: 'Std dev divided by mean', why: 'High=unpredictable, Low=stable demand' },
  { feature: 'region_strength', name: 'Region Strength', type: 'ENGINEERED', source: 'groupby(Region).mean()', how: 'Avg sales per region', why: 'Some regions consistently sell more' },
  { feature: 'category_popularity', name: 'Category Popularity', type: 'ENGINEERED', source: 'groupby(Category).mean()', how: 'Avg sales per category', why: 'Technology vs Office Supplies demand level' },
  { feature: 'relative_demand', name: 'Relative Demand', type: 'ENGINEERED', source: 'sales / (region_strength+1)', how: 'Sales vs region average', why: 'Above or below regional norm' },
  { feature: 'weekly_pattern', name: 'Weekly Pattern', type: 'ENGINEERED', source: 'groupby(dayofweek).mean()', how: 'Avg sales per weekday', why: 'Recurring weekly behavior' },
  { feature: 'trend_slope', name: 'Trend Slope', type: 'ENGINEERED', source: 'polyfit(last 7 days)', how: 'Linear slope of recent sales', why: 'Upward or downward trend direction' },
  { feature: 'subcategory_avg_sales', name: 'Sub-Category Avg', type: 'ENGINEERED', source: 'Sub-Category median', how: 'Median sale per sub-category per day', why: 'Product-level demand context' },
  { feature: 'shipping_days', name: 'Shipping Duration', type: 'ENGINEERED', source: 'Ship Date - Order Date', how: 'Days between order and ship', why: 'Urgency correlates with demand type' },
  { feature: 'sales_acceleration', name: 'Sales Acceleration', type: 'ENGINEERED', source: 'momentum - momentum_7d_ago', how: 'Change in momentum over time', why: 'Is the trend speeding up or slowing down?' },
  { feature: 'weekend_flag', name: 'Weekend Flag', type: 'ENGINEERED', source: 'dayofweek >= 5', how: '1 if Saturday/Sunday, 0 otherwise', why: 'Weekend shopping is fundamentally different' },
];

const TYPE_META = {
  RAW: { color: '#3b82f6', bg: '#f0f9ff', count: 7 },
  AGGREGATED: { color: '#f59e0b', bg: '#fffbeb', count: 9 },
  ENGINEERED: { color: '#10b981', bg: '#f0fdf4', count: 11 },
};

const PIE_DATA = [
  { name: 'Raw (7)', value: 7, color: '#3b82f6' },
  { name: 'Aggregated (9)', value: 9, color: '#f59e0b' },
  { name: 'Engineered (11)', value: 11, color: '#10b981' },
];

export default function FeatureExtractionSlide() {
  const [expanded, setExpanded] = useState(null);
  const [filter, setFilter] = useState('all');
  const [realFI, setRealFI] = useState(null);

  useEffect(() => {
    const load = () => api.fi().then(r => setRealFI(r.data.features)).catch(() => {});
    load();
    const iv = setInterval(load, 5000);
    return () => clearInterval(iv);
  }, []);

  const filtered = filter === 'all' ? FEATURES : FEATURES.filter(f => f.type === filter);

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ color: '#1f2937', fontSize: 28, fontWeight: 700, margin: 0, marginBottom: 4 }}>How Features Work</h1>
        <p style={{ color: '#6b7280', margin: 0, fontSize: 14 }}>27 features (7 raw + 9 aggregated + 11 engineered) built from 18 dataset columns</p>
      </div>

      {/* Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Dataset Columns', value: '18', color: '#6b7280' },
          { label: 'Total Features', value: '27', color: '#1f2937' },
          { label: 'Raw', value: '7', color: '#3b82f6' },
          { label: 'Aggregated', value: '9', color: '#f59e0b' },
          { label: 'Engineered', value: '11', color: '#10b981' },
        ].map(c => (
          <div key={c.label} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 14, textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <div style={{ color: c.color, fontSize: 22, fontWeight: 700 }}>{c.value}</div>
            <div style={{ color: '#6b7280', fontSize: 11 }}>{c.label}</div>
          </div>
        ))}
      </div>

      {/* Pie + Types */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <h3 style={{ color: '#1f2937', margin: '0 0 12px', fontSize: 16 }}>Feature Type Distribution</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart><Pie data={PIE_DATA} cx="50%" cy="50%" outerRadius={75} dataKey="value" label={({ name }) => name}>{PIE_DATA.map((e, i) => <Cell key={i} fill={e.color} />)}</Pie><Tooltip /></PieChart>
          </ResponsiveContainer>
        </div>
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <h3 style={{ color: '#1f2937', margin: '0 0 12px', fontSize: 16 }}>Feature Types</h3>
          {Object.entries(TYPE_META).map(([type, meta]) => (
            <div key={type} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: 10, background: meta.bg, borderRadius: 8, marginBottom: 8 }}>
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: meta.color, flexShrink: 0, marginTop: 3 }} />
              <div>
                <div style={{ color: meta.color, fontWeight: 600, fontSize: 14 }}>{type} ({meta.count})</div>
                <div style={{ color: '#6b7280', fontSize: 12 }}>
                  {type === 'RAW' && 'Direct from dataset columns (date, sales, ship mode, segment)'}
                  {type === 'AGGREGATED' && 'Computed from sales history (lags, rolling averages, std dev)'}
                  {type === 'ENGINEERED' && 'New information by combining features (momentum, volatility, patterns)'}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Real-time Feature Importance */}
      {realFI && (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, marginBottom: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <h3 style={{ color: '#1f2937', margin: '0 0 12px', fontSize: 16 }}>Feature Importance (Real-Time from Model)</h3>
          <ResponsiveContainer width="100%" height={500}>
            <BarChart data={realFI.map(f => ({ ...f, name: FEATURES.find(x => x.feature === f.feature)?.name || f.feature }))} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis type="number" stroke="#6b7280" fontSize={11} label={{ value: 'Importance Score (how much each feature matters)', position: 'insideBottom', offset: -5, style: { fill: '#6b7280', fontSize: 10 } }} />
              <YAxis type="category" dataKey="name" stroke="#6b7280" fontSize={9} width={130} label={{ value: 'Feature Name', angle: -90, position: 'insideLeft', offset: 15, style: { fill: '#6b7280', fontSize: 10 } }} />
              <Tooltip formatter={v => v.toFixed(4)} />
              <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
                {realFI.map((f, i) => <Cell key={i} fill={f.type === 'engineered' ? '#10b981' : f.type === 'aggregated' ? '#f59e0b' : '#3b82f6'} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', gap: 12, justifyContent: 'center', fontSize: 11, marginTop: 4 }}>
            {[['Raw', '#3b82f6'], ['Aggregated', '#f59e0b'], ['Engineered', '#10b981']].map(([l, c]) => (
              <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 4 }}><div style={{ width: 10, height: 10, borderRadius: 3, background: c }} />{l}</div>
            ))}
          </div>
        </div>
      )}

      {/* Filter */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {[{ key: 'all', label: 'All (27)', color: '#1f2937' }, { key: 'RAW', label: 'Raw (7)', color: '#3b82f6' }, { key: 'AGGREGATED', label: 'Aggregated (9)', color: '#f59e0b' }, { key: 'ENGINEERED', label: 'Engineered (11)', color: '#10b981' }].map(b => (
          <button key={b.key} onClick={() => setFilter(b.key)} style={{ background: filter === b.key ? b.color : '#fff', border: '1px solid #e5e7eb', color: filter === b.key ? '#fff' : '#6b7280', padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>{b.label}</button>
        ))}
      </div>

      {/* Feature Cards */}
      {filtered.map(f => {
        const meta = TYPE_META[f.type];
        const open = expanded === f.feature;
        const ri = realFI?.find(x => x.feature === f.feature);
        return (
          <div key={f.feature} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, marginBottom: 10, overflow: 'hidden', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
            <div onClick={() => setExpanded(open ? null : f.feature)} style={{ padding: 14, cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ background: meta.bg, border: `1px solid ${meta.color}`, color: meta.color, padding: '2px 8px', borderRadius: 6, fontSize: 10, fontWeight: 600 }}>{f.type}</span>
                <div>
                  <div style={{ color: '#1f2937', fontWeight: 600, fontSize: 14 }}>{f.name}</div>
                  <div style={{ color: '#6b7280', fontSize: 11, fontFamily: 'monospace' }}>{f.feature}</div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {ri && <span style={{ color: meta.color, fontWeight: 600, fontSize: 12 }}>{ri.importance.toFixed(4)}</span>}
                <span style={{ color: '#6b7280', transform: open ? 'rotate(180deg)' : '', transition: 'transform 0.2s' }}>▼</span>
              </div>
            </div>
            {open && (
              <div style={{ padding: 14, background: '#f9fafb', borderTop: '1px solid #e5e7eb' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                  <div><div style={{ color: '#1f2937', fontWeight: 600, fontSize: 13, marginBottom: 4 }}>How it works</div><div style={{ color: '#6b7280', fontSize: 13 }}>Source: {f.source} | {f.how}</div></div>
                  <div><div style={{ color: '#1f2937', fontWeight: 600, fontSize: 13, marginBottom: 4 }}>Why it matters</div><div style={{ color: '#6b7280', fontSize: 13 }}>{f.why}</div></div>
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* Flow */}
      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, marginTop: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <h3 style={{ color: '#1f2937', margin: '0 0 12px', fontSize: 16 }}>Pipeline Flow</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr auto 1fr auto 1fr', gap: 10, alignItems: 'center' }}>
          {[
            { val: '18', label: 'Dataset Columns', bg: '#f0f9ff', bc: '#3b82f6', color: '#3b82f6' },
            null,
            { val: '27', label: '7R + 9A + 11E', bg: '#f9fafb', bc: '#e5e7eb', color: '#1f2937' },
            null,
            { val: '27', label: 'Model Features', bg: '#f0fdf4', bc: '#10b981', color: '#10b981' },
            null,
            { val: '1', label: 'Sales Prediction', bg: '#faf5ff', bc: '#8b5cf6', color: '#8b5cf6' },
          ].map((item, i) => item ? (
            <div key={i} style={{ background: item.bg, border: `1px solid ${item.bc}`, borderRadius: 10, padding: 14, textAlign: 'center' }}>
              <div style={{ color: item.color, fontWeight: 700, fontSize: 18 }}>{item.val}</div>
              <div style={{ color: item.color, fontWeight: 600, fontSize: 11 }}>{item.label}</div>
            </div>
          ) : <div key={i} style={{ color: '#6b7280', fontSize: 20, textAlign: 'center' }}>→</div>)}
        </div>
      </div>
    </div>
  );
}
