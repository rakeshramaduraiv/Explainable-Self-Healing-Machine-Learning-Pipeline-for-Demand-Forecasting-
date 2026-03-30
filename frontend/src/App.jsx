import React, { useState, useEffect, useRef, useCallback } from "react";
import { api } from "./api";
import Navbar from "./components/Navbar";
import Dashboard from "./components/Dashboard";
import Analytics from "./components/Analytics";
import FeatureExtractionSlide from "./components/FeatureExtractionSlide";
import Logbook from "./components/Logbook";
import XAISlide from "./components/XAISlide";

function Spinner() { return <span className="spinner" />; }

function MetricBox({ label, value, color = "#3b82f6" }) {
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

// ═══════════════════════════════════════════════════════════
//  PIPELINE PAGE
// ═══════════════════════════════════════════════════════════

function PipelinePage() {
  const [prediction, setPrediction] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);
  const [driftResult, setDriftResult] = useState(null);
  const [updateResult, setUpdateResult] = useState(null);
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef();

  // Step 1: Predict next month
  const handlePredict = async () => {
    setLoading(true);
    try {
      const res = await api.predict();
      setPrediction(res.data);
      setUploadResult(null);
      setDriftResult(null);
      setUpdateResult(null);
      setStep(1);
    } catch (e) {
      alert("Prediction failed: " + (e.response?.data?.detail || e.message));
    } finally { setLoading(false); }
  };

  // Step 2: Upload actual data
  const handleUpload = async (file) => {
    if (!file) return;
    setLoading(true);
    try {
      const res = await api.upload(file);
      setUploadResult(res.data);
      setStep(2);
    } catch (e) {
      alert("Upload failed: " + (e.response?.data?.detail || e.message));
    } finally { setLoading(false); }
  };

  // Step 3: Drift check
  const handleDrift = async () => {
    setLoading(true);
    try {
      const res = await api.drift();
      setDriftResult(res.data);
      setStep(3);
    } catch (e) {
      alert("Drift check failed");
    } finally { setLoading(false); }
  };

  // Step 4: Model update
  const handleUpdate = async (action) => {
    setLoading(true);
    try {
      const res = action === "finetune" ? await api.finetune() : await api.sliding();
      setUpdateResult(res.data);
      setStep(4);
    } catch (e) {
      alert("Update failed");
    } finally { setLoading(false); }
  };

  // Step 5: Predict next (reset cycle)
  const handleNextCycle = () => {
    setPrediction(null);
    setUploadResult(null);
    setDriftResult(null);
    setUpdateResult(null);
    setStep(0);
    handlePredict();
  };

  const stepNames = ["Predict Next Month", "Upload Actual Data", "Evaluate + Drift", "Model Update", "Predict Next"];
  const levelColor = { low: "#10b981", medium: "#f59e0b", high: "#ef4444" };

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ color: '#1f2937', fontSize: 28, fontWeight: 700, margin: 0, marginBottom: 8 }}>Self-Healing Pipeline</h1>
        <p style={{ color: '#6b7280', margin: 0, fontSize: 14 }}>
          Predict next month, upload actual data, evaluate accuracy, check drift, update model, repeat
        </p>
      </div>

      {/* Step Bar */}
      <div className="step-indicator">
        {stepNames.map((s, i) => (
          <div key={s} style={{ display: "contents" }}>
            <div className={`step ${i < step ? "done" : i === step ? "active" : ""}`}>
              <div className="step-num">{i < step ? "✓" : i + 1}</div>
              {s}
            </div>
            {i < stepNames.length - 1 && <div className="step-line" />}
          </div>
        ))}
      </div>

      {/* ── STEP 1: Predict Next Month ── */}
      <div className="card">
        <div className="card-title">Step 1 — Predict Next Month</div>
        {!prediction ? (
          <div>
            <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 12 }}>
              Click below to generate a sales forecast for the next month. The model uses features from the current training data to predict what will happen next.
            </p>
            <button className="btn btn-success" onClick={handlePredict} disabled={loading}>
              {loading && step === 0 ? <><Spinner /> Predicting...</> : "Predict Next Month"}
            </button>
          </div>
        ) : (
          <div>
            <div style={{ background: '#f0fdf4', border: '1px solid #10b981', borderRadius: 10, padding: 16, marginBottom: 12 }}>
              <div style={{ color: '#10b981', fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
                Prediction: {prediction.predicting_month}
              </div>
              <div style={{ color: '#6b7280', fontSize: 12, marginBottom: 12 }}>
                Period: {prediction.date_min} to {prediction.date_max}
              </div>
              <div className="metric-grid">
                <MetricBox label="Total Predicted" value={`$${(prediction.total_predicted || 0).toLocaleString()}`} color="#10b981" />
                <MetricBox label="Avg Daily" value={`$${prediction.mean_daily}`} color="#3b82f6" />
                <MetricBox label="Categories" value={prediction.total_categories} color="#f59e0b" />
                <MetricBox label="Regions" value={prediction.total_regions} color="#8b5cf6" />
              </div>
            </div>
            {prediction.cat_summary && (
              <div style={{ marginBottom: 16 }}>
                {/* Daily Prediction Line Chart */}
                {(prediction.daily_chart || []).length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#1f2937', marginBottom: 6 }}>Daily Predicted Sales</div>
                    <div style={{ background: '#f9fafb', borderRadius: 8, padding: '8px 4px', border: '1px solid #e5e7eb' }}>
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center' }}>
                        {prediction.daily_chart.map(d => (
                          <div key={d.day} style={{ textAlign: 'center', minWidth: 32 }}>
                            <div style={{ fontSize: 10, color: '#6b7280' }}>D{d.day}</div>
                            <div style={{ fontSize: 11, fontWeight: 600, color: '#10b981' }}>${(d.predicted/1000).toFixed(0)}K</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#1f2937', marginBottom: 6 }}>By Category</div>
                  {prediction.cat_summary.map(c => (
                    <div key={c.category} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12, borderBottom: '1px solid #f3f4f6' }}>
                      <span style={{ color: '#3b82f6', fontWeight: 600 }}>{c.category}</span>
                      <span style={{ color: '#6b7280' }}>${c.total_predicted?.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#1f2937', marginBottom: 6 }}>By Region</div>
                  {prediction.region_summary?.map(r => (
                    <div key={r.region} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12, borderBottom: '1px solid #f3f4f6' }}>
                      <span style={{ color: '#10b981', fontWeight: 600 }}>{r.region}</span>
                      <span style={{ color: '#6b7280' }}>${r.total_predicted?.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
                </div>
              </div>
            )}
            <Alert type="info">
              Now upload the actual {prediction.predicting_month} sales data below to evaluate this prediction.
            </Alert>
          </div>
        )}
      </div>

      {/* ── STEP 2: Upload Actual Data ── */}
      {prediction && (
        <div className="card">
          <div className="card-title">Step 2 — Upload Actual {prediction.predicting_month} Data</div>
          {!uploadResult ? (
            <div>
              <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 12 }}>
                Upload the real sales data for <strong>{prediction.predicting_month}</strong>. The system will compare your prediction against actual sales, update the training data, and prepare for the next month.
              </p>
              <div className="upload-zone" onClick={() => inputRef.current.click()}>
                <input ref={inputRef} type="file" accept=".csv" onChange={e => handleUpload(e.target.files[0])} />
                <div style={{ color: "#3b82f6", fontWeight: 600, marginBottom: 4 }}>
                  {loading && step === 1 ? <><Spinner /> Processing...</> : `Click to upload ${prediction.predicting_month} actual data`}
                </div>
                <div style={{ color: "#6b7280", fontSize: 12 }}>CSV file with actual sales</div>
              </div>
            </div>
          ) : (
            <div>
              {/* Evaluation: Predicted vs Actual */}
              {uploadResult.evaluation && (
                <div style={{ background: '#f0f9ff', border: '1px solid #3b82f6', borderRadius: 10, padding: 16, marginBottom: 16 }}>
                  <div style={{ fontSize: 15, fontWeight: 700, color: '#1f2937', marginBottom: 12 }}>
                    Evaluation: {prediction.predicting_month}
                  </div>
                  <div className="metric-grid">
                    <MetricBox label="We Predicted" value={`$${(uploadResult.evaluation.predicted_total || 0).toLocaleString()}`} color="#3b82f6" />
                    <MetricBox label="Actual Sales" value={`$${(uploadResult.evaluation.actual_total || 0).toLocaleString()}`} color="#10b981" />
                    <MetricBox label="Difference" value={`$${(uploadResult.evaluation.difference || 0).toLocaleString()}`} color={uploadResult.evaluation.difference > 0 ? '#f59e0b' : '#ef4444'} />
                    <MetricBox label="Accuracy" value={`${uploadResult.evaluation.accuracy_pct || 0}%`} color="#8b5cf6" />
                  </div>
                </div>
              )}

              {/* Upload Summary */}
              <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 12 }}>
                Uploaded: {uploadResult.analysis?.rows} rows, {uploadResult.analysis?.orders} orders, ${uploadResult.analysis?.total_sales?.toLocaleString()} total sales
              </div>

              {/* What changed */}
              <div style={{ background: '#f9fafb', borderRadius: 8, padding: 12, border: '1px solid #e5e7eb', fontSize: 13 }}>
                <strong style={{ color: '#1f2937' }}>Training data updated:</strong> Now includes {uploadResult.analysis?.upload_month} data ({uploadResult.analysis?.total_train_orders?.toLocaleString()} total orders)
                <br/>
                <strong style={{ color: '#10b981' }}>Next prediction ready:</strong> {uploadResult.analysis?.next_predict_month}
              </div>

              {/* Next prediction auto-generated */}
              {uploadResult.next_prediction && (
                <div style={{ marginTop: 12, background: '#f0fdf4', border: '1px solid #10b981', borderRadius: 8, padding: 12, fontSize: 13 }}>
                  <strong style={{ color: '#10b981' }}>Auto-predicted {uploadResult.next_prediction.predicting_month}:</strong> ${uploadResult.next_prediction.total_predicted?.toLocaleString()} total sales
                </div>
              )}

              <div style={{ marginTop: 12 }}>
                <Alert type="info">Now run drift check to see if the model needs updating.</Alert>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── STEP 3: Drift Check ── */}
      {uploadResult && (
        <div className="card">
          <div className="card-title">Step 3 — Drift Detection</div>
          {!driftResult ? (
            <div>
              <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 12 }}>
                Check if the new data has shifted significantly from what the model was trained on. This determines whether the model needs updating.
              </p>
              <button className="btn btn-primary" onClick={handleDrift} disabled={loading}>
                {loading && step === 2 ? <><Spinner /> Checking...</> : "Run Drift Check"}
              </button>
            </div>
          ) : (
            <div>
              <div className="metric-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)", maxWidth: 400, marginBottom: 12 }}>
                <MetricBox label="Drift Score" value={driftResult.drift_score} color={levelColor[driftResult.level] || "#6b7280"} />
                <div className="metric-box">
                  <div className="metric-value"><span style={{ color: levelColor[driftResult.level], fontWeight: 700 }}>{driftResult.level?.toUpperCase()}</span></div>
                  <div className="metric-label">Drift Level</div>
                </div>
                <div className="metric-box">
                  <div className="metric-value" style={{ color: '#3b82f6' }}>{driftResult.action === "monitor" ? "Monitor" : driftResult.action === "fine_tune" ? "Fine-Tune" : "Retrain"}</div>
                  <div className="metric-label">Recommended</div>
                </div>
              </div>

              {driftResult.feature_drift && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#1f2937', marginBottom: 6 }}>Per-Feature Drift:</div>
                  {Object.entries(driftResult.feature_drift).map(([feat, vals]) => (
                    <div key={feat} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12, borderBottom: '1px solid #f3f4f6' }}>
                      <span style={{ color: '#1f2937' }}>{feat}</span>
                      <span style={{ color: vals.ks_stat > 0.2 ? '#ef4444' : vals.ks_stat > 0.1 ? '#f59e0b' : '#10b981', fontWeight: 600 }}>KS: {vals.ks_stat}</span>
                    </div>
                  ))}
                </div>
              )}

              <Alert type={driftResult.level === "low" ? "success" : driftResult.level === "medium" ? "warning" : "danger"}>
                {driftResult.level === "low" && "Low drift. Model is still accurate. You can proceed to predict the next month."}
                {driftResult.level === "medium" && "Medium drift detected. Fine-tuning recommended to maintain accuracy."}
                {driftResult.level === "high" && "High drift detected. Full model retrain required."}
              </Alert>
            </div>
          )}
        </div>
      )}

      {/* ── STEP 4: Model Update ── */}
      {driftResult && (
        <div className="card">
          <div className="card-title">Step 4 — Model Update</div>
          {!updateResult ? (
            <div>
              {driftResult.level === "low" && (
                <div>
                  <Alert type="success">Model is stable. No update needed.</Alert>
                  <button className="btn btn-success" onClick={handleNextCycle} disabled={loading} style={{ marginTop: 12 }}>
                    {loading ? <><Spinner /> Predicting...</> : `Predict ${uploadResult?.next_prediction?.predicting_month || "Next Month"}`}
                  </button>
                </div>
              )}
              {driftResult.level === "medium" && (
                <div>
                  <Alert type="warning">Medium drift. Fine-tuning will adjust the model using recent data patterns.</Alert>
                  <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                    <button className="btn btn-warning" onClick={() => handleUpdate("finetune")} disabled={loading}>
                      {loading ? <><Spinner /> Fine-tuning...</> : "Fine-Tune Model"}
                    </button>
                    <button className="btn btn-success" onClick={handleNextCycle} disabled={loading} style={{ opacity: 0.7 }}>
                      Skip and Predict Next
                    </button>
                  </div>
                </div>
              )}
              {driftResult.level === "high" && (
                <div>
                  <Alert type="danger">High drift. Full retrain will rebuild the model with all available data.</Alert>
                  <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                    <button className="btn btn-danger" onClick={() => handleUpdate("sliding")} disabled={loading}>
                      {loading ? <><Spinner /> Retraining...</> : "Full Retrain (Sliding Window)"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div>
              <Alert type="success">Model updated! Method: {updateResult.method}</Alert>
              <div className="metric-grid" style={{ marginTop: 12, gridTemplateColumns: "repeat(3, 1fr)", maxWidth: 360 }}>
                <MetricBox label="New MAE" value={`$${updateResult.metrics.MAE}`} color="#10b981" />
                <MetricBox label="New RMSE" value={`$${updateResult.metrics.RMSE}`} color="#f59e0b" />
                <MetricBox label="New MAPE" value={`${updateResult.metrics.MAPE}%`} color="#ef4444" />
              </div>
              <button className="btn btn-success" onClick={handleNextCycle} disabled={loading} style={{ marginTop: 16 }}>
                {loading ? <><Spinner /> Predicting...</> : `Predict ${uploadResult?.next_prediction?.predicting_month || "Next Month"}`}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
//  MAIN APP
// ═══════════════════════════════════════════════════════════

export default function App() {
  const [status, setStatus] = useState(null);
  const [activeView, setActiveView] = useState('dashboard');

  useEffect(() => {
    api.status().then(r => setStatus(r.data)).catch(() => {});
  }, []);

  const views = {
    dashboard: <Dashboard />,
    pipeline: <PipelinePage />,
    analytics: <Analytics />,
    'feature-extraction': <FeatureExtractionSlide />,
    xai: <XAISlide />,
    logbook: <Logbook />,
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <Navbar activeView={activeView} setActiveView={setActiveView} status={status} />
      <main style={{ minHeight: 'calc(100vh - 64px)' }}>
        {views[activeView] || <Dashboard />}
      </main>
    </div>
  );
}
