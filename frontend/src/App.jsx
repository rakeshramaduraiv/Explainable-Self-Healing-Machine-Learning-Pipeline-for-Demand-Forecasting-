import { useState, useEffect, useRef } from "react";
import { api } from "./api";

// ─── Reusable Components ────────────────────────────────

function Spinner() { return <span className="spinner" />; }

function ChartImg({ title, src }) {
  if (!src) return null;
  return (
    <div style={{ marginBottom: 20 }}>
      {title && <div style={{ color: "#94a3b8", fontSize: 13, marginBottom: 8, fontWeight: 500 }}>{title}</div>}
      <img src={`data:image/png;base64,${src}`} alt={title} className="chart-img" />
    </div>
  );
}

function MetricBox({ label, value, color = "#a78bfa" }) {
  return (
    <div className="metric-box">
      <div className="metric-value" style={{ color }}>{value}</div>
      <div className="metric-label">{label}</div>
    </div>
  );
}

function Alert({ type = "info", children }) {
  return <div className={`alert alert-${type}`}>{children}</div>;
}

// ─── Sidebar ────────────────────────────────────────────

function Sidebar({ status, retrainLog, activeStep }) {
  const steps = ["Upload", "Analysis", "Performance", "Drift", "Update", "Predict"];
  return (
    <div className="sidebar">
      <div className="sidebar-logo">📦 Forecasting</div>

      <div className="sidebar-section">
        <div className="sidebar-section-title">Pipeline Status</div>
        {status?.files && Object.entries(status.files).map(([k, v]) => (
          <div key={k} className="status-row">
            <div className={`dot ${v ? "dot-green" : "dot-red"}`} />
            {k.replace(/_/g, " ")}
          </div>
        ))}
      </div>

      {status?.model?.type && (
        <div className="sidebar-section">
          <div className="sidebar-section-title">Model</div>
          <div className="status-row"><div className="dot dot-green" />{status.model.type}</div>
          <div style={{ fontSize: 11, color: "#475569", paddingLeft: 15 }}>
            Trees: {status.model.trees} | Features: {status.model.features}
          </div>
        </div>
      )}

      <div className="sidebar-section">
        <div className="sidebar-section-title">Workflow</div>
        {steps.map((s, i) => (
          <div key={s} className="status-row">
            <div className={`dot ${i < activeStep ? "dot-green" : i === activeStep ? "dot-green" : "dot-red"}`}
              style={{ background: i < activeStep ? "#34d399" : i === activeStep ? "#a78bfa" : "#2d2d4e" }} />
            <span style={{ color: i === activeStep ? "#a78bfa" : i < activeStep ? "#34d399" : "#475569" }}>{s}</span>
          </div>
        ))}
      </div>

      {retrainLog.length > 0 && (
        <div className="sidebar-section">
          <div className="sidebar-section-title">Retrain Log</div>
          {retrainLog.map((l, i) => <div key={i} className="log-item">{l}</div>)}
        </div>
      )}
    </div>
  );
}

// ─── Step Indicator ─────────────────────────────────────

function StepBar({ current }) {
  const steps = ["Upload", "Analysis", "Performance", "Drift Check", "Model Update", "Predict"];
  return (
    <div className="step-indicator">
      {steps.map((s, i) => (
        <>
          <div key={s} className={`step ${i < current ? "done" : i === current ? "active" : ""}`}>
            <div className="step-num">{i < current ? "✓" : i + 1}</div>
            {s}
          </div>
          {i < steps.length - 1 && <div key={`line-${i}`} className="step-line" />}
        </>
      ))}
    </div>
  );
}

// ─── Section 1: Upload ──────────────────────────────────

function UploadSection({ onDone }) {
  const [mode, setMode]       = useState("14col");
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const inputRef              = useRef();

  const handleFile = async (file) => {
    if (!file) return;
    setLoading(true); setError(null);
    try {
      const res = await api.upload(file);
      onDone(res.data);
    } catch (e) {
      setError(e.response?.data?.detail || "Upload failed");
    } finally { setLoading(false); }
  };

  return (
    <div className="card">
      <div className="card-title">📂 Step 1 — Upload Actual Month Data</div>

      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        {["3col", "14col"].map(m => (
          <button key={m} onClick={() => setMode(m)}
            style={{ padding: "8px 18px", borderRadius: 8, border: "1px solid",
              borderColor: mode === m ? "#a78bfa" : "#2d2d4e",
              background: mode === m ? "#2d2d4e" : "transparent",
              color: mode === m ? "#a78bfa" : "#64748b", fontWeight: 500 }}>
            {m === "3col" ? "3 Columns" : "14 Columns"}
          </button>
        ))}
      </div>

      <div style={{ background: "#0f0f17", borderRadius: 10, padding: 12, marginBottom: 16,
                    border: "1px solid #2d2d4e", fontSize: 12, color: "#64748b" }}>
        {mode === "3col"
          ? "Required: id (HOBBIES_1_001_CA_1_validation), date (YYYY-MM-DD), sales (integer)"
          : "Required: item_id, dept_id, cat_id, store_id, state_id, wm_yr_wk, snap_CA, snap_TX, snap_WI, sell_price, dayofweek, weekofyear, month, year, date, sales"}
      </div>

      <div className="upload-zone" onClick={() => inputRef.current.click()}>
        <input ref={inputRef} type="file" accept=".csv"
          onChange={e => handleFile(e.target.files[0])} />
        <div style={{ fontSize: 36, marginBottom: 10 }}>📄</div>
        <div style={{ color: "#a78bfa", fontWeight: 600, marginBottom: 4 }}>
          {loading ? <><Spinner />Uploading & Analysing...</> : "Click to upload CSV"}
        </div>
        <div style={{ color: "#475569", fontSize: 12 }}>Supports .csv files</div>
      </div>

      {error && <Alert type="danger">{error}</Alert>}
    </div>
  );
}

// ─── Section 2: Data Analysis ───────────────────────────

function AnalysisSection({ data }) {
  const [tab, setTab] = useState(0);
  if (!data) return null;
  const { analysis, charts } = data;
  const tabs = ["Distribution", "Day of Week", "Category", "Price", "SNAP"];

  return (
    <div className="card">
      <div className="card-title">📊 Step 2 — Uploaded Data Analysis</div>

      <div className="metric-grid">
        <MetricBox label="Total Rows"    value={analysis.rows.toLocaleString()} />
        <MetricBox label="Unique SKUs"   value={analysis.skus.toLocaleString()} color="#34d399" />
        <MetricBox label="Total Days"    value={analysis.total_days} color="#38bdf8" />
        <MetricBox label="Mean Sales"    value={analysis.mean_sales} color="#fbbf24" />
        <MetricBox label="Max Sales"     value={analysis.max_sales} color="#f87171" />
        <MetricBox label="Zero Sales %"  value={`${analysis.zero_pct}%`} color="#94a3b8" />
        <MetricBox label="Total Units"   value={analysis.total_units.toLocaleString()} color="#a78bfa" />
        <MetricBox label="Format"        value={analysis.format} color="#c084fc" />
      </div>

      <div style={{ color: "#475569", fontSize: 12, marginBottom: 16 }}>
        Date Range: {analysis.date_min} → {analysis.date_max}
      </div>

      <div className="tab-bar">
        {tabs.map((t, i) => (
          <button key={t} className={`tab ${tab === i ? "active" : ""}`} onClick={() => setTab(i)}>{t}</button>
        ))}
      </div>

      {tab === 0 && <ChartImg src={charts.distribution} />}
      {tab === 1 && <ChartImg src={charts.dow} />}
      {tab === 2 && (charts.category ? <ChartImg src={charts.category} /> : <Alert type="info">Category data not available in 3-column format</Alert>)}
      {tab === 3 && (charts.price    ? <ChartImg src={charts.price}    /> : <Alert type="info">Price data not available in 3-column format</Alert>)}
      {tab === 4 && (charts.snap     ? <ChartImg src={charts.snap}     /> : <Alert type="info">SNAP data not available in 3-column format</Alert>)}
    </div>
  );
}

// ─── Section 3: Model Performance ───────────────────────

function PerformanceSection() {
  const [data, setData]   = useState(null);
  const [fi, setFi]       = useState(null);
  const [tab, setTab]     = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.metrics(), api.fi()])
      .then(([m, f]) => { setData(m.data); setFi(f.data); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="card"><div style={{ color: "#64748b" }}><Spinner />Loading model performance...</div></div>;
  if (!data)   return <div className="card"><Alert type="warning">Run the base pipeline first to see metrics.</Alert></div>;

  return (
    <div className="card">
      <div className="card-title">🎯 Step 3 — Current Model Performance</div>

      <div className="metric-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)", maxWidth: 400 }}>
        <MetricBox label="MAE"  value={data.mae}          color="#34d399" />
        <MetricBox label="RMSE" value={data.rmse}         color="#fbbf24" />
        <MetricBox label="MAPE" value={`${data.mape}%`}   color="#f87171" />
      </div>

      <div className="tab-bar">
        {["Actual vs Predicted", "Top Error SKUs", "Feature Importance"].map((t, i) => (
          <button key={t} className={`tab ${tab === i ? "active" : ""}`} onClick={() => setTab(i)}>{t}</button>
        ))}
      </div>

      {tab === 0 && <ChartImg src={data.chart} />}

      {tab === 1 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>#</th><th>SKU</th><th>Mean Absolute Error</th></tr></thead>
            <tbody>
              {data.top_error_skus.map((r, i) => (
                <tr key={i}><td>{i+1}</td><td>{r.sku}</td><td>{r.mae.toFixed(4)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 2 && fi && <ChartImg src={fi.chart} />}
    </div>
  );
}

// ─── Section 4: Drift Detection ─────────────────────────

function DriftSection({ onDone }) {
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const run = async () => {
    setLoading(true); setError(null);
    try {
      const res = await api.drift();
      setResult(res.data);
      onDone(res.data.level);
    } catch (e) {
      setError(e.response?.data?.detail || "Drift check failed");
    } finally { setLoading(false); }
  };

  const levelColor = { low: "#34d399", medium: "#fbbf24", high: "#f87171", unknown: "#94a3b8" };
  const gaugeColor = { low: "#34d399", medium: "#fbbf24", high: "#f87171" };

  return (
    <div className="card">
      <div className="card-title">🔍 Step 4 — Drift Detection (KS Test)</div>

      <div style={{ background: "#0f0f17", borderRadius: 10, padding: 14, marginBottom: 16,
                    border: "1px solid #2d2d4e", fontSize: 12, color: "#64748b" }}>
        The KS (Kolmogorov-Smirnov) test compares the distribution of actual sales vs predicted sales.
        A higher KS statistic means more drift — the model needs updating.
      </div>

      <button className="btn btn-primary" onClick={run} disabled={loading}>
        {loading ? <><Spinner />Running KS Test...</> : "▶ Run Drift Check"}
      </button>

      {error && <Alert type="danger">{error}</Alert>}

      {result && (
        <div style={{ marginTop: 20 }}>
          <div className="metric-grid" style={{ gridTemplateColumns: "repeat(2, 1fr)", maxWidth: 300 }}>
            <MetricBox label="KS Statistic" value={result.ks_stat ?? "N/A"} color={levelColor[result.level]} />
            <div className="metric-box">
              <div className="metric-value">
                <span className={`badge badge-${result.level}`}>{result.level?.toUpperCase()}</span>
              </div>
              <div className="metric-label">Drift Level</div>
            </div>
          </div>

          {result.ks_stat !== null && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#475569", marginBottom: 4 }}>
                <span>No Drift (0)</span><span>Medium (0.1)</span><span>High (0.3)</span><span>Max (1.0)</span>
              </div>
              <div className="gauge-track">
                <div className="gauge-fill" style={{
                  width: `${result.ks_stat * 100}%`,
                  background: gaugeColor[result.level] || "#94a3b8"
                }} />
                <div style={{ position: "absolute", left: "10%", top: 0, bottom: 0, width: 1, background: "#fbbf24", opacity: 0.6 }} />
                <div style={{ position: "absolute", left: "30%", top: 0, bottom: 0, width: 1, background: "#f87171", opacity: 0.6 }} />
              </div>
            </div>
          )}

          <Alert type={result.level === "low" ? "success" : result.level === "medium" ? "warning" : "danger"}>
            {result.message}
          </Alert>

          {result.dist_chart && (
            <div style={{ marginTop: 16 }}>
              <div style={{ color: "#94a3b8", fontSize: 13, marginBottom: 8, fontWeight: 500 }}>
                Distribution Comparison — Actual vs Predicted
              </div>
              <ChartImg src={result.dist_chart} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Section 5: Model Update ─────────────────────────────

function UpdateSection({ driftLevel, onDone }) {
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  if (!driftLevel) return null;

  const run = async (action) => {
    setLoading(true); setError(null);
    try {
      const res = action === "finetune" ? await api.finetune() : await api.sliding();
      setResult(res.data);
      onDone(`${res.data.method} | MAE=${res.data.metrics.MAE.toFixed(3)} | RMSE=${res.data.metrics.RMSE.toFixed(3)}`);
    } catch (e) {
      setError(e.response?.data?.detail || "Retrain failed");
    } finally { setLoading(false); }
  };

  return (
    <div className="card">
      <div className="card-title">🔧 Step 5 — Model Update</div>

      {driftLevel === "low" && (
        <Alert type="success">Model is stable. No retraining needed. Proceed to prediction.</Alert>
      )}

      {driftLevel === "medium" && !result && (
        <div>
          <Alert type="warning">MEDIUM drift detected — fine-tuning recommended.</Alert>
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-warning" onClick={() => run("finetune")} disabled={loading}>
              {loading ? <><Spinner />Fine-tuning...</> : "🔧 Fine-Tune Model"}
            </button>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 8 }}>
              Adds 500 new trees on top of existing model with lower learning rate (0.01)
            </div>
          </div>
        </div>
      )}

      {driftLevel === "high" && !result && (
        <div>
          <Alert type="danger">HIGH drift detected — sliding window retrain required.</Alert>
          <div style={{ marginTop: 14 }}>
            <button className="btn btn-danger" onClick={() => run("sliding")} disabled={loading}>
              {loading ? <><Spinner />Retraining...</> : "🔁 Sliding Window Retrain"}
            </button>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 8 }}>
              Retrains on last 6 months of data. Rolls back if new model is worse.
            </div>
          </div>
        </div>
      )}

      {error && <Alert type="danger">{error}</Alert>}

      {result && (
        <div>
          <Alert type="success">Retrain complete! Method: {result.method}</Alert>
          <div className="metric-grid" style={{ marginTop: 14, gridTemplateColumns: "repeat(3, 1fr)", maxWidth: 360 }}>
            <MetricBox label="MAE"  value={result.metrics.MAE.toFixed(3)}  color="#34d399" />
            <MetricBox label="RMSE" value={result.metrics.RMSE.toFixed(3)} color="#fbbf24" />
            <MetricBox label="MAPE" value={`${result.metrics.MAPE.toFixed(1)}%`} color="#f87171" />
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Section 6: Predict ──────────────────────────────────

const CAT_INFO = {
  HOBBIES  : { emoji: "🎮", label: "Hobbies",   desc: "Toys, games, crafts & leisure items" },
  FOODS    : { emoji: "🍎", label: "Foods",     desc: "Groceries, food & beverages" },
  HOUSEHOLD: { emoji: "🏠", label: "Household", desc: "Cleaning, home & personal care" },
};

const STORE_INFO = (s) => {
  if (!s) return s;
  if (s.startsWith("CA")) return `🏪 ${s} — California, USA`;
  if (s.startsWith("TX")) return `🏪 ${s} — Texas, USA`;
  if (s.startsWith("WI")) return `🏪 ${s} — Wisconsin, USA`;
  return `🏪 ${s}`;
};

function PredictSection() {
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const [tab, setTab]         = useState(0);

  const run = async () => {
    setLoading(true); setError(null);
    try { const res = await api.predict(); setResult(res.data); }
    catch (e) { setError(e.response?.data?.detail || "Prediction failed"); }
    finally { setLoading(false); }
  };

  return (
    <div className="card">
      <div className="card-title">🔮 Step 6 — Predict Next Month</div>

      <button className="btn btn-success" onClick={run} disabled={loading}>
        {loading ? <><Spinner />Generating Forecast...</> : "🔮 Generate Next Month Forecast"}
      </button>

      {error && <Alert type="danger">{error}</Alert>}

      {result && (
        <div style={{ marginTop: 20 }}>

          {/* Summary banner */}
          <div style={{ background: "linear-gradient(135deg,#1a1a2e,#0f0f17)",
                        border: "1px solid #2d2d4e", borderRadius: 12,
                        padding: 16, marginBottom: 20 }}>
            <div style={{ color: "#64748b", fontSize: 11, fontWeight: 600,
                          textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
              📅 Forecast Period: {result.date_min} → {result.date_max}
            </div>
            <div className="metric-grid">
              <MetricBox label="Total Units Predicted" value={result.total_units.toLocaleString()} color="#34d399" />
              <MetricBox label="Avg Daily Sales"       value={result.mean_daily}                   color="#a78bfa" />
              <MetricBox label="Peak Sales Day"        value={result.peak_day}                     color="#fbbf24" />
              <MetricBox label="Products Forecasted"   value={result.total_skus?.toLocaleString()} color="#38bdf8" />
              <MetricBox label="Stores"                value={result.total_stores}                 color="#f87171" />
              <MetricBox label="Categories"            value={result.total_cats}                   color="#c084fc" />
            </div>
          </div>

          {/* Tabs */}
          <div className="tab-bar">
            {["📈 Overall Trend", "📦 By Category", "🏪 By Store", "🏆 Top Products"].map((t, i) => (
              <button key={t} className={`tab ${tab === i ? "active" : ""}`} onClick={() => setTab(i)}>{t}</button>
            ))}
          </div>

          {/* Tab 0 — Overall */}
          {tab === 0 && (
            <div>
              <div style={{ background: "#0f0f17", borderRadius: 10, padding: 12,
                            border: "1px solid #2d2d4e", marginBottom: 14, fontSize: 13, color: "#94a3b8" }}>
                📊 This chart shows the <strong style={{color:"#a78bfa"}}>total predicted daily sales</strong> across
                all <strong style={{color:"#38bdf8"}}>{result.total_skus} products</strong> in
                all <strong style={{color:"#f87171"}}>{result.total_stores} store(s)</strong> for next month.
              </div>
              <ChartImg src={result.charts?.overall} />
            </div>
          )}

          {/* Tab 1 — By Category */}
          {tab === 1 && (
            <div>
              <div style={{ background: "#0f0f17", borderRadius: 10, padding: 12,
                            border: "1px solid #2d2d4e", marginBottom: 14, fontSize: 13, color: "#94a3b8" }}>
                📦 How much each <strong style={{color:"#a78bfa"}}>product category</strong> is predicted to sell next month.
                Use this to plan stock orders per department.
              </div>
              <ChartImg src={result.charts?.category} />
              <div className="table-wrap" style={{ marginTop: 16 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Category</th>
                      <th>Products</th>
                      <th>Total Units</th>
                      <th>Avg Daily</th>
                      <th>Peak Day</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.cat_summary?.map((r, i) => {
                      const info = CAT_INFO[r.category] || { emoji: "📦", desc: r.category };
                      return (
                        <tr key={i}>
                          <td>
                            <strong style={{color:"#a78bfa"}}>{info.emoji} {r.category}</strong>
                          </td>
                          <td style={{color:"#64748b", fontSize:12}}>{info.desc}</td>
                          <td><strong style={{color:"#34d399"}}>{r.total_units.toLocaleString()}</strong></td>
                          <td style={{color:"#fbbf24"}}>{r.avg_daily}</td>
                          <td style={{color:"#f87171"}}>{r.peak_day_units}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Tab 2 — By Store */}
          {tab === 2 && (
            <div>
              <div style={{ background: "#0f0f17", borderRadius: 10, padding: 12,
                            border: "1px solid #2d2d4e", marginBottom: 14, fontSize: 13, color: "#94a3b8" }}>
                🏪 How much each <strong style={{color:"#38bdf8"}}>store location</strong> is predicted to sell.
                Use this to plan inventory distribution across stores.
              </div>
              <ChartImg src={result.charts?.store} />
              <div className="table-wrap" style={{ marginTop: 16 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Store</th>
                      <th>Location</th>
                      <th>Total Units</th>
                      <th>Avg Daily</th>
                      <th>Peak Day</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.store_summary?.map((r, i) => (
                      <tr key={i}>
                        <td><strong style={{color:"#38bdf8"}}>🏪 {r.store}</strong></td>
                        <td style={{color:"#64748b", fontSize:12}}>{STORE_INFO(r.store)}</td>
                        <td><strong style={{color:"#34d399"}}>{r.total_units.toLocaleString()}</strong></td>
                        <td style={{color:"#fbbf24"}}>{r.avg_daily}</td>
                        <td style={{color:"#f87171"}}>{r.peak_day_units}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Tab 3 — Top Products */}
          {tab === 3 && (
            <div>
              <div style={{ background: "#0f0f17", borderRadius: 10, padding: 12,
                            border: "1px solid #2d2d4e", marginBottom: 14, fontSize: 13, color: "#94a3b8" }}>
                🏆 Top 10 individual <strong style={{color:"#fbbf24"}}>products</strong> predicted to sell the most.
                Prioritise stocking these items before the month starts.
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>#</th><th>Product ID</th><th>Category</th><th>Store</th><th>Predicted Units</th></tr>
                  </thead>
                  <tbody>
                    {result.top_products?.map((r, i) => {
                      const info = CAT_INFO[r.category] || { emoji: "📦" };
                      return (
                        <tr key={i}>
                          <td style={{color:"#64748b"}}>{i+1}</td>
                          <td><strong style={{color:"#a78bfa"}}>📦 {r.product}</strong></td>
                          <td><span style={{ background:"#1a1a2e", border:"1px solid #2d2d4e",
                                             borderRadius:6, padding:"2px 8px", fontSize:12 }}>
                            {info.emoji} {r.category}
                          </span></td>
                          <td style={{color:"#38bdf8"}}>🏪 {r.store}</td>
                          <td><strong style={{color:"#34d399"}}>{r.total_predicted.toLocaleString()}</strong></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Download */}
          <div style={{ marginTop: 20, padding: 16, background: "#0f0f17",
                        borderRadius: 12, border: "1px solid #2d2d4e" }}>
            <div style={{ color: "#94a3b8", fontSize: 13, marginBottom: 10 }}>
              📥 Download the full predictions CSV —
              <strong style={{color:"#a78bfa"}}> {result.total_rows?.toLocaleString()} rows</strong>
              ({result.total_skus} products × {result.date_min} to {result.date_max})
            </div>
            <a href={api.downloadCSV()} download
              style={{ display:"inline-flex", alignItems:"center", gap:8,
                       background:"linear-gradient(135deg,#0369a1,#38bdf8)",
                       color:"#fff", padding:"10px 22px", borderRadius:10,
                       fontWeight:600, textDecoration:"none", fontSize:14 }}>
              ⬇ Download Predictions CSV
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main App ────────────────────────────────────────────

export default function App() {
  const [status,      setStatus]      = useState(null);
  const [uploadData,  setUploadData]  = useState(null);
  const [driftLevel,  setDriftLevel]  = useState(null);
  const [retrainLog,  setRetrainLog]  = useState([]);
  const [activeStep,  setActiveStep]  = useState(0);

  useEffect(() => {
    api.status().then(r => setStatus(r.data)).catch(() => {});
  }, []);

  const handleUpload = (data) => { setUploadData(data); setActiveStep(1); };
  const handleDrift  = (lvl)  => { setDriftLevel(lvl);  setActiveStep(4); };
  const handleRetrain= (log)  => { setRetrainLog(p => [...p, log]); setActiveStep(5); };

  return (
    <div style={{ display: "flex" }}>
      <Sidebar status={status} retrainLog={retrainLog} activeStep={activeStep} />

      <div className="main-content">
        <div className="page-title">Real-Time Demand Forecasting</div>
        <div className="page-sub">Upload actual month data → Detect drift → Update model → Predict next month</div>

        <StepBar current={activeStep} />

        <UploadSection     onDone={handleUpload} />
        {uploadData   && <AnalysisSection data={uploadData} />}
        <PerformanceSection />
        {uploadData   && <DriftSection onDone={handleDrift} />}
        {driftLevel   && <UpdateSection driftLevel={driftLevel} onDone={handleRetrain} />}
        {driftLevel   && <PredictSection />}
      </div>
    </div>
  );
}
