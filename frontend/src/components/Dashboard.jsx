import React, { useState, useEffect } from 'react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api';

function Spinner() { return <span className="spinner" />; }
const C = ['#3b82f6','#10b981','#f59e0b','#8b5cf6','#ef4444','#06b6d4'];

function Card({ title, sub, children }) {
  return (<div style={{ background:'#fff', border:'1px solid #e5e7eb', borderRadius:12, padding:20, marginBottom:20, boxShadow:'0 1px 3px rgba(0,0,0,0.1)' }}>
    {title && <h3 style={{ color:'#1f2937', margin:0, marginBottom:4, fontSize:16, fontWeight:600 }}>{title}</h3>}
    {sub && <p style={{ color:'#6b7280', margin:'0 0 16px', fontSize:12 }}>{sub}</p>}
    {!sub && title && <div style={{ borderBottom:'1px solid #e5e7eb', marginBottom:16 }} />}
    {children}
  </div>);
}

function KPI({ label, value, sub, color='#3b82f6' }) {
  return (<div style={{ background:'#fff', border:'1px solid #e5e7eb', borderRadius:12, padding:14, boxShadow:'0 1px 3px rgba(0,0,0,0.1)' }}>
    <div style={{ color:'#6b7280', fontSize:11, marginBottom:4 }}>{label}</div>
    <div style={{ color, fontSize:20, fontWeight:700 }}>{value}</div>
    {sub && <div style={{ color:'#9ca3af', fontSize:10, marginTop:2 }}>{sub}</div>}
  </div>);
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [fi, setFi] = useState(null);
  const [loading, setLoading] = useState(true);
  const [product, setProduct] = useState('__ALL__');
  const [onDemand, setOnDemand] = useState(null);
  const [loadingProduct, setLoadingProduct] = useState(false);

  useEffect(() => {
    const load = () => {
      Promise.all([api.status(), api.metrics(), api.fi()])
        .then(([s,m,f]) => { setData(s.data); setMetrics(m.data); setFi(f.data); setLoading(false); })
        .catch(() => { setLoading(false); setTimeout(load, 2000); });
    };
    load();
  }, []);

  useEffect(() => {
    if (product === '__ALL__' || !data) { setOnDemand(null); return; }
    const cached = (data.dataset?.product_details || {})[product];
    if (cached) { setOnDemand(null); return; }
    setLoadingProduct(true);
    api.product(product).then(r => { setOnDemand(r.data); setLoadingProduct(false); }).catch(() => setLoadingProduct(false));
  }, [product, data]);

  if (loading) return <div style={{ display:'flex', justifyContent:'center', alignItems:'center', height:'60vh', gap:8 }}><Spinner /><span style={{ color:'#6b7280' }}>Connecting...</span></div>;
  if (!data) return <div style={{ padding:24 }}><div style={{ background:'#fef2f2', border:'1px solid #ef4444', borderRadius:12, padding:20, textAlign:'center' }}><div style={{ color:'#ef4444', fontSize:18, fontWeight:600 }}>Backend Not Connected</div></div></div>;

  const ds = data.dataset || {};
  const fb = data.feature_breakdown || {};
  const pred = data.prediction || {};
  const acc = metrics ? (100 - metrics.mape).toFixed(1) : '0';
  const pList = ds.product_list || [];
  const filtered = product !== '__ALL__';
  const pDet = filtered ? (onDemand ? onDemand.details : (ds.product_details || {})[product] || {}) : {};
  const pMonth = filtered ? (onDemand ? onDemand.monthly : (ds.product_monthly || {})[product] || []) : ds.monthly_sales || [];

  return (
    <div style={{ padding:24 }}>
      <div style={{ marginBottom:24 }}>
        <h1 style={{ color:'#1f2937', fontSize:28, fontWeight:700, margin:0, marginBottom:4 }}>Demand Forecasting Dashboard</h1>
        <p style={{ color:'#6b7280', margin:0, fontSize:14 }}>Select a product below to filter all charts for that product</p>
      </div>

      {/* ===== GLOBAL PRODUCT SLICER ===== */}
      <div style={{ background:'#fff', border:'2px solid #3b82f6', borderRadius:12, padding:20, marginBottom:24, boxShadow:'0 2px 8px rgba(59,130,246,0.15)' }}>
        <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:12 }}>
          <span style={{ color:'#3b82f6', fontWeight:700, fontSize:16 }}>Product Filter</span>
          <span style={{ color:'#6b7280', fontSize:12 }}>Select a product to filter all charts below</span>
        </div>
        <select value={product} onChange={e => setProduct(e.target.value)} style={{ padding:'10px 16px', borderRadius:10, border:'2px solid #3b82f6', fontSize:14, color:'#1f2937', width:'100%', maxWidth:500, background:'#f0f9ff', fontWeight:500, cursor:'pointer' }}>
          <option value="__ALL__">All Products (Overview)</option>
          {pList.map(p => <option key={p} value={p}>{p}</option>)}
        </select>

        {filtered && loadingProduct && (
          <div style={{ marginTop:12, color:'#3b82f6', fontSize:13 }}>Loading product data...</div>
        )}
        {filtered && !loadingProduct && (
          <div style={{ marginTop:12, display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(130px, 1fr))', gap:10 }}>
            <KPI label="Product" value={product.length > 20 ? product.substring(0,20)+'...' : product} color="#1f2937" />
            <KPI label="Category" value={pDet.category || 'N/A'} color="#3b82f6" />
            <KPI label="Sub-Category" value={pDet.sub_category || 'N/A'} color="#f59e0b" />
            <KPI label="Total Orders" value={pDet.total_orders || 0} color="#10b981" />
            <KPI label="Total Sales" value={'$'+(pDet.total_sales || 0).toLocaleString()} color="#8b5cf6" />
          </div>
        )}
      </div>

      {/* ===== MODEL INFO ===== */}
      <Card title="Model Information" sub={'Predicting demand for '+(ds.products||0).toLocaleString()+' products using '+(fb.total||27)+' features'}>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(130px, 1fr))', gap:10 }}>
          <KPI label="Model" value="LightGBM" sub="200 trees" color="#3b82f6" />
          <KPI label="Accuracy" value={acc+'%'} sub={'MAPE: '+(metrics?.mape||0)+'%'} color="#10b981" />
          <KPI label="MAE" value={'$'+(metrics?.mae||0)} sub="Prediction error" color="#ef4444" />
          <KPI label="Products" value={(ds.products||0).toLocaleString()} sub={(ds.sub_categories||0)+' types'} color="#8b5cf6" />
          <KPI label="Orders" value={(ds.total_orders||0).toLocaleString()} color="#f59e0b" />
          <KPI label="Features" value={fb.total||27} sub={(fb.engineered||11)+' engineered'} color="#06b6d4" />
        </div>
      </Card>

      {/* ===== MONTHLY TREND (filtered) ===== */}
      <Card title={filtered ? 'Monthly Demand: '+(product.length>35 ? product.substring(0,35)+'...' : product) : 'Monthly Sales Trend (All Products)'} sub={filtered ? 'Orders per month for this product (all '+pMonth.length+' months)' : 'Total sales across all products over time'}>
        {pMonth.length > 0 ? (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={pMonth}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="month" stroke="#6b7280" fontSize={7} angle={-45} textAnchor="end" height={60} interval={1} label={{ value:'Month', position:'insideBottom', offset:-5, style:{fill:'#6b7280',fontSize:10} }} />
              <YAxis stroke="#6b7280" fontSize={10} tickFormatter={filtered ? (v=>v) : (v=>'$'+(v/1000).toFixed(0)+'K')} label={{ value:filtered?'Orders':'Monthly Sales ($)', angle:-90, position:'insideLeft', style:{fill:'#6b7280',fontSize:10} }} />
              <Tooltip formatter={v => filtered ? v+' orders' : '$'+v.toLocaleString()} />
              <Line type="monotone" dataKey={filtered?'orders':'total'} stroke={filtered?'#10b981':'#3b82f6'} strokeWidth={2} dot={{r:filtered?2:1}} name={filtered?'Orders':'Sales'} />
            </LineChart>
          </ResponsiveContainer>
        ) : <div style={{ color:'#6b7280', textAlign:'center', padding:40 }}>No data available</div>}
        {filtered && pMonth.length > 0 && (
          <div style={{ marginTop:8, fontSize:12, color:'#6b7280' }}>
            Active in <strong>{pMonth.filter(d=>d.orders>0).length} of {pMonth.length} months</strong> | Total: <strong>{pMonth.reduce((s,d)=>s+d.orders,0)} orders</strong> | Peak: <strong>{pMonth.reduce((m,d)=>d.orders>m.orders?d:m,pMonth[0]).month} ({pMonth.reduce((m,d)=>d.orders>m.orders?d:m,pMonth[0]).orders} orders)</strong>
          </div>
        )}
      </Card>

      {/* ===== REGION ===== */}
      <Card title={filtered ? 'Regional Demand: '+(product.length>30?product.substring(0,30)+'...':product) : 'Product Demand by Region'} sub={filtered ? 'Orders for this product in each region' : 'Total orders and sales by region'}>
        {filtered && pDet.regions ? (
          <div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={Object.entries(pDet.regions).map(([r,o])=>({region:r,orders:o})).sort((a,b)=>b.orders-a.orders)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="region" stroke="#6b7280" fontSize={11} label={{ value:'Region', position:'insideBottom', offset:-5, style:{fill:'#6b7280',fontSize:10} }} />
                <YAxis stroke="#6b7280" fontSize={10} label={{ value:'Orders', angle:-90, position:'insideLeft', style:{fill:'#6b7280',fontSize:10} }} />
                <Tooltip formatter={v=>v+' orders'} />
                <Bar dataKey="orders" name="Orders" radius={[4,4,0,0]}>{Object.keys(pDet.regions).map((_,i)=><Cell key={i} fill={C[(i+1)%C.length]} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : !filtered && (ds.region_sales||[]).length > 0 ? (
          <div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={(ds.region_sales||[]).slice().sort((a,b)=>b.total_orders-a.total_orders)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="region" stroke="#6b7280" fontSize={11} label={{ value:'Region', position:'insideBottom', offset:-5, style:{fill:'#6b7280',fontSize:10} }} />
                <YAxis stroke="#6b7280" fontSize={10} label={{ value:'Orders', angle:-90, position:'insideLeft', style:{fill:'#6b7280',fontSize:10} }} />
                <Tooltip content={({active,payload})=>active&&payload?.length?(
                  <div style={{ background:'#fff', border:'1px solid #e5e7eb', borderRadius:8, padding:10, boxShadow:'0 2px 8px rgba(0,0,0,0.1)', fontSize:12 }}>
                    <div style={{ color:'#1f2937', fontWeight:600 }}>{payload[0].payload.region}</div>
                    <div style={{ color:'#3b82f6' }}>{payload[0].payload.total_orders.toLocaleString()} orders</div>
                    <div style={{ color:'#10b981' }}>${payload[0].payload.total_sales.toLocaleString()} sales</div>
                  </div>
                ):null} />
                <Bar dataKey="total_orders" name="Orders" radius={[4,4,0,0]}>
                  {(ds.region_sales||[]).slice().sort((a,b)=>b.total_orders-a.total_orders).map((_,i)=><Cell key={i} fill={C[(i+1)%C.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, marginTop:12 }}>
              {(ds.region_sales||[]).slice().sort((a,b)=>b.total_orders-a.total_orders).map((reg,ri) => (
                <div key={reg.region}>
                  <div style={{ display:'flex', justifyContent:'space-between', marginBottom:4 }}>
                    <span style={{ color:C[(ri+1)%C.length], fontWeight:700, fontSize:13 }}>{reg.region}</span>
                    <span style={{ color:'#1f2937', fontWeight:600, fontSize:12 }}>{reg.total_orders.toLocaleString()} orders</span>
                  </div>
                  {((ds.products_by_region||{})[reg.region]||[]).map((p,i) => (
                    <div key={i} style={{ display:'flex', justifyContent:'space-between', padding:'2px 0', fontSize:11, borderBottom:'1px solid #f3f4f6' }}>
                      <span style={{ color:'#1f2937', cursor:'pointer', textDecoration:'underline' }} onClick={()=>setProduct(p.product)}>{p.product.length>30?p.product.substring(0,30)+'...':p.product}</span>
                      <span style={{ color:C[(ri+1)%C.length], fontWeight:600 }}>{p.orders}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        ) : <div style={{ color:'#6b7280' }}>No region data</div>}
      </Card>

      {/* ===== SEGMENTS (only when filtered) ===== */}
      {filtered && pDet.segments && (
        <Card title={'Customer Segments: '+(product.length>30?product.substring(0,30)+'...':product)} sub="Which customer types buy this product">
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={Object.entries(pDet.segments).map(([s,o])=>({name:s,value:o}))} cx="50%" cy="50%" outerRadius={65} dataKey="value" label={({name,value})=>name+': '+value}>
                {Object.keys(pDet.segments).map((_,i)=><Cell key={i} fill={C[i]} />)}
              </Pie>
              <Tooltip formatter={v=>v+' orders'} />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* ===== CATEGORY (only all view) ===== */}
      {!filtered && (
        <Card title="Product Demand by Category" sub="Total orders by category - click a product name to filter">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={(ds.cat_sales||[]).slice().sort((a,b)=>b.total_orders-a.total_orders)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="category" stroke="#6b7280" fontSize={11} label={{ value:'Category', position:'insideBottom', offset:-5, style:{fill:'#6b7280',fontSize:10} }} />
              <YAxis stroke="#6b7280" fontSize={10} label={{ value:'Orders', angle:-90, position:'insideLeft', style:{fill:'#6b7280',fontSize:10} }} />
              <Tooltip content={({active,payload})=>active&&payload?.length?(
                <div style={{ background:'#fff', border:'1px solid #e5e7eb', borderRadius:8, padding:10, boxShadow:'0 2px 8px rgba(0,0,0,0.1)', fontSize:12 }}>
                  <div style={{ color:'#1f2937', fontWeight:600 }}>{payload[0].payload.category}</div>
                  <div style={{ color:'#3b82f6' }}>{payload[0].payload.total_orders.toLocaleString()} orders</div>
                  <div style={{ color:'#10b981' }}>${payload[0].payload.total_sales.toLocaleString()} sales</div>
                </div>
              ):null} />
              <Bar dataKey="total_orders" name="Orders" radius={[4,4,0,0]}>
                {(ds.cat_sales||[]).slice().sort((a,b)=>b.total_orders-a.total_orders).map((_,i)=><Cell key={i} fill={C[i]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:16, marginTop:12 }}>
            {(ds.cat_sales||[]).slice().sort((a,b)=>b.total_orders-a.total_orders).map((cat,ci) => (
              <div key={cat.category}>
                <div style={{ display:'flex', justifyContent:'space-between', marginBottom:4 }}>
                  <span style={{ color:C[ci], fontWeight:700, fontSize:13 }}>{cat.category}</span>
                  <span style={{ color:'#1f2937', fontWeight:600, fontSize:12 }}>{cat.total_orders.toLocaleString()}</span>
                </div>
                {((ds.products_by_category||{})[cat.category]||[]).map((p,i) => (
                  <div key={i} style={{ display:'flex', justifyContent:'space-between', padding:'2px 0', fontSize:11, borderBottom:'1px solid #f3f4f6' }}>
                    <span style={{ color:'#1f2937', cursor:'pointer', textDecoration:'underline' }} onClick={()=>setProduct(p.product)}>{p.product.length>25?p.product.substring(0,25)+'...':p.product}</span>
                    <span style={{ color:C[ci], fontWeight:600 }}>{p.orders}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ===== TOP 10 (only all view) ===== */}
      {!filtered && (ds.top_products||[]).length > 0 && (
        <Card title="Top 10 Most Sold Products" sub="Click any product name to filter all charts">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={(ds.top_products||[]).map((p,i)=>({...p,label:'#'+(i+1)+' '+(p.product.length>25?p.product.substring(0,25)+'...':p.product)})).slice().reverse()} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis type="number" stroke="#6b7280" fontSize={10} label={{ value:'Number of Orders', position:'insideBottom', offset:-5, style:{fill:'#6b7280',fontSize:10} }} />
              <YAxis type="category" dataKey="label" stroke="#6b7280" fontSize={9} width={200} label={{ value:'Product', angle:-90, position:'insideLeft', offset:25, style:{fill:'#6b7280',fontSize:10} }} />
              <Tooltip content={({active,payload})=>active&&payload?.length?(
                <div style={{ background:'#fff', border:'1px solid #e5e7eb', borderRadius:8, padding:10, boxShadow:'0 2px 8px rgba(0,0,0,0.1)', fontSize:12 }}>
                  <div style={{ color:'#1f2937', fontWeight:600 }}>{payload[0].payload.product}</div>
                  <div style={{ color:'#6b7280' }}>{payload[0].payload.category} | {payload[0].payload.sub_category}</div>
                  <div style={{ color:'#3b82f6', fontWeight:600 }}>{payload[0].payload.total_orders} orders</div>
                </div>
              ):null} />
              <Bar dataKey="total_orders" name="Orders" radius={[0,4,4,0]}>
                {(ds.top_products||[]).slice().reverse().map((p,i)=><Cell key={i} fill={p.category==='Technology'?'#3b82f6':p.category==='Furniture'?'#f59e0b':'#10b981'} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={{ marginTop:8 }}>
            {(ds.top_products||[]).map((p,i) => (
              <div key={i} style={{ display:'flex', justifyContent:'space-between', padding:'5px 0', fontSize:12, borderBottom:'1px solid #f3f4f6', cursor:'pointer' }} onClick={()=>setProduct(p.product)}>
                <span style={{ color:'#3b82f6', textDecoration:'underline' }}>#{i+1} {p.product.length>45?p.product.substring(0,45)+'...':p.product}</span>
                <span style={{ color:'#10b981', fontWeight:600 }}>{p.total_orders} orders</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ===== PREDICTION ===== */}
      {pred.predicting_month && (() => {
        const pp = filtered ? (pred.product_predictions||{})[product] : null;
        const chartData = pp ? pp.daily_chart||[] : pred.daily_chart||[];
        const totalPred = pp ? pp.total_predicted||0 : pred.total_predicted||0;
        const totalOrders = pp ? pp.total_predicted_orders||0 : 0;
        const prodCount = pred.product_count || ds.products || 0;
        // For filtered product: compute cumulative orders for the chart
        let displayChart = chartData;
        if (filtered && chartData.length > 0) {
          let cum = 0;
          displayChart = chartData.map(d => { cum += (d.orders||0); return {...d, cumOrders: Math.round(cum)}; });
        }
        return (
          <Card title={'Demand Prediction: '+pred.predicting_month} sub={filtered ? 'Predicted orders for: '+(product.length>50?product.substring(0,50)+'...':product) : 'Forecasting for all '+prodCount.toLocaleString()+' products'}>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(140px, 1fr))', gap:10, marginBottom:16 }}>
              {filtered ? (
                <>
                  <KPI label="Predicted Orders/Month" value={totalOrders < 1 ? totalOrders.toFixed(2) : Math.round(totalOrders).toLocaleString()} sub={pred.date_min+' to '+pred.date_max} color="#8b5cf6" />
                  <KPI label="Predicted Sales" value={'$'+totalPred.toLocaleString()} color="#10b981" />
                  <KPI label="Avg Daily Orders" value={totalOrders < 1 ? (totalOrders/30).toFixed(3) : (totalOrders/30).toFixed(2)} color="#3b82f6" />
                </>
              ) : (
                <>
                  <KPI label="Total Predicted" value={'$'+totalPred.toLocaleString()} sub={pred.date_min+' to '+pred.date_max} color="#10b981" />
                  <KPI label="Avg Daily" value={'$'+(pred.mean_daily||0)} color="#3b82f6" />
                  <KPI label="Categories" value={pred.total_categories||0} color="#f59e0b" />
                  <KPI label="Regions" value={pred.total_regions||0} color="#8b5cf6" />
                </>
              )}
            </div>
            {displayChart.length > 0 && (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={displayChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="date" stroke="#6b7280" fontSize={9} angle={-45} textAnchor="end" height={60} interval={2} />
                  {filtered ? (
                    <YAxis stroke="#6b7280" fontSize={10} label={{ value:'Cumulative Orders', angle:-90, position:'insideLeft', style:{fill:'#6b7280',fontSize:10} }} />
                  ) : (
                    <YAxis stroke="#6b7280" fontSize={10} domain={['dataMin * 0.95','dataMax * 1.05']} allowDataOverflow label={{ value:'Predicted Sales ($)', angle:-90, position:'insideLeft', style:{fill:'#6b7280',fontSize:10} }} />
                  )}
                  <Tooltip formatter={(v)=> filtered ? Math.round(v)+' orders' : '$'+Number(v).toFixed(0)} labelFormatter={v=>v} />
                  <Line type="monotone" dataKey={filtered?'cumOrders':'predicted'} stroke={filtered?'#8b5cf6':'#10b981'} strokeWidth={2} dot={{r:2}} name={filtered?'Orders':'Sales'} />
                </LineChart>
              </ResponsiveContainer>
            )}
            <div style={{ marginTop:12, padding:12, background:'#fffbeb', borderRadius:8, border:'1px solid #f59e0b', fontSize:13, color:'#92400e' }}>
              Go to <strong>Pipeline</strong> to upload actual {pred.predicting_month} data.
            </div>
          </Card>
        );
      })()}

      {/* ===== FEATURES ===== */}
      {(fi?.features||[]).length > 0 && (
        <Card title="Features Driving Demand Predictions" sub="Which features predict product demand">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={fi.features.slice(0,10)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis type="number" stroke="#6b7280" fontSize={10} label={{ value:'Importance', position:'insideBottom', offset:-5, style:{fill:'#6b7280',fontSize:10} }} />
              <YAxis type="category" dataKey="feature" stroke="#6b7280" fontSize={10} width={120} label={{ value:'Feature', angle:-90, position:'insideLeft', offset:10, style:{fill:'#6b7280',fontSize:10} }} />
              <Tooltip formatter={v=>v.toFixed(4)} />
              <Bar dataKey="importance" radius={[0,4,4,0]}>
                {fi.features.slice(0,10).map((f,i)=><Cell key={i} fill={f.type==='engineered'?'#10b981':f.type==='aggregated'?'#f59e0b':'#3b82f6'} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={{ display:'flex', gap:12, justifyContent:'center', fontSize:11, marginTop:4 }}>
            {[['Raw','#3b82f6'],['Aggregated','#f59e0b'],['Engineered','#10b981']].map(([l,c])=>(
              <div key={l} style={{ display:'flex', alignItems:'center', gap:4 }}><div style={{ width:10, height:10, borderRadius:3, background:c }} />{l}</div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
