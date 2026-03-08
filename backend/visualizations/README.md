# Phase 1 Visualizations — Self-Healing Demand Forecasting

## Files
| File | Chart | Description |
|------|-------|-------------|
| chart1_actual_vs_predicted.html | Line chart | Actual vs predicted avg weekly sales Feb–Oct 2012 with CI band |
| chart2_error_trend.html | Bar chart | Monthly MAE vs baseline with drift severity zones |
| chart3_store_heatmap.html | Heatmap | 45 stores × 9 months error % grid |
| chart4_feature_importance.html | Bar + Radar | Top 10 features driving predictions |
| chart5_drift_dashboard.html | Gauges + Stacked bar | KS/PSI/error gauges + feature drift counts |
| chart6_performance_metrics.html | KPI indicators | R², RMSE, MAPE, WMAPE |
| chart7_prediction_distribution.html | Box plots | Sales distribution per month |
| chart8_time_decomposition.html | Area + Bar | Trend, seasonal, residual decomposition |
| chart9_confusion_matrix.html | Heatmap | Low/Medium/High demand category accuracy |
| chart10_executive_summary.html | Combined | KPIs + mini time-series + donut + MAE bars |
| dashboard_complete.html | All-in-one | Tabbed dashboard with all 10 charts |

## Color Guide
- Blue (#3b82f6) — Actual sales / predictions / normal
- Green (#10b981) — No drift / good accuracy
- Orange (#f59e0b) — Mild drift / warning
- Red (#ef4444) — Severe drift / high error
- Purple (#8b5cf6) — Feature importance / secondary metrics

## Key Insights from Phase 1
1. Model R²=0.9957 on training data — excellent fit
2. All 9 monitored months show SEVERE drift (expected: 2010-2011 train vs 2012 test)
3. Error ratio ranges from 1.07x to 2.79x baseline MAE
4. 36–49 of 58 combined KS+PSI checks flag severe per month
5. Lag features (Lag_1, Lag_52) are most important — time-series patterns dominate

## Phase 2 Recommendations
- Retrain on 2011–2012 data immediately
- Use rolling window retraining (12-month window, slide monthly)
- Monitor CPI and Unemployment most closely (economic drift drivers)
- Target retraining trigger: error ratio > 1.5x baseline
