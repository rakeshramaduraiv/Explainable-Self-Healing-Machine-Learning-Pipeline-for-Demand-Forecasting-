import { useState, lazy, Suspense, useEffect, useCallback, memo, useTransition } from 'react'
import { ToastContainer } from './ui.jsx'
import { API, useFetch } from './api.js'

const Overview    = lazy(() => import('./pages/Overview.jsx'))
const Drift       = lazy(() => import('./pages/Drift.jsx'))
const Performance = lazy(() => import('./pages/Performance.jsx'))
const Features    = lazy(() => import('./pages/Features.jsx'))
const StoreStats  = lazy(() => import('./pages/StoreStats.jsx'))
const Predictions = lazy(() => import('./pages/Predictions.jsx'))
const Upload      = lazy(() => import('./pages/Upload.jsx'))
const Datasets    = lazy(() => import('./pages/Datasets.jsx'))
const Demand      = lazy(() => import('./pages/Demand.jsx'))
const Predict     = lazy(() => import('./pages/Predict.jsx'))

const prefetchAll = () => [
  import('./pages/Drift.jsx'), import('./pages/Performance.jsx'),
  import('./pages/Features.jsx'), import('./pages/StoreStats.jsx'),
  import('./pages/Predictions.jsx'), import('./pages/Upload.jsx'),
  import('./pages/Datasets.jsx'), import('./pages/Demand.jsx'),
  import('./pages/Predict.jsx'),
]

const PAGES = [
  { id: 'overview',    label: 'Training Overview',          icon: '◉', group: 'Baseline vs Test Set' },
  { id: 'drift',       label: 'Drift Detection',            icon: '◈', group: 'Baseline vs Test Set' },
  { id: 'performance', label: 'Baseline Performance',       icon: '◆', group: 'Baseline vs Test Set' },
  { id: 'features',    label: 'Feature Importance', icon: '▣', group: 'Analysis' },
  { id: 'storestats',  label: 'Forecasting',       icon: '▤', group: 'Analysis' },
  { id: 'predictions', label: 'Predictions',        icon: '▥', group: 'Analysis' },
  { id: 'demand',      label: 'Demand Insights',    icon: '▦', group: 'Analysis' },
  { id: 'datasets',    label: 'Datasets',           icon: '▧', group: 'Data' },
  { id: 'upload',      label: 'Upload & Monitor',   icon: '▨', group: 'Data' },
  { id: 'predict',     label: 'Predict Cycle',      icon: '⟳', group: 'Data' },
]

const MAP = {
  overview: Overview, drift: Drift, performance: Performance,
  features: Features, storestats: StoreStats, predictions: Predictions,
  upload: Upload, datasets: Datasets, demand: Demand, predict: Predict,
}

const groups = [...new Set(PAGES.map(p => p.group))]

const NavItem = memo(({ p, active, onClick }) => (
  <div className={`nav-item${active ? ' active' : ''}`} onClick={onClick} title={p.label}>
    <span style={{ fontSize: 11, marginRight: 10, opacity: 0.5, width: 14, textAlign: 'center' }}>{p.icon}</span>
    <span className="nav-label">{p.label}</span>
  </div>
))

export default function App() {
  const [page, setPage]   = useState('overview')
  const [apiOk, setApiOk] = useState(null)
  const [isPending, startTransition] = useTransition()
  const { data: health } = useFetch('/api/health', { pollMs: 20000 })
  const { data: summary } = useFetch('/api/summary', { pollMs: 60000 })
  const { data: datasets } = useFetch('/api/datasets', { pollMs: 60000 })

  const navigate = useCallback(id => { startTransition(() => setPage(id)) }, [])

  useEffect(() => {
    if ('requestIdleCallback' in window) requestIdleCallback(prefetchAll)
    else setTimeout(prefetchAll, 800)
  }, [])

  useEffect(() => {
    const check = () => API.health().then(() => setApiOk(true)).catch(() => setApiOk(false))
    check()
    const id = setInterval(check, 20000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const handler = e => {
      if (!e.altKey) return
      const idx = parseInt(e.key) - 1
      if (idx >= 0 && idx < PAGES.length) navigate(PAGES[idx].id)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [navigate])

  const Page = MAP[page]
  const currentPage = PAGES.find(p => p.id === page)
  const stores = datasets?.inspection?.stores ?? '—'
  const rows = datasets?.inspection?.rows ?? '—'
  const severity = summary?.final_severity

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon" />
          <div className="sidebar-logo-text">
            <div className="sidebar-logo-name">SH-DFS <span>Monitor</span></div>
            <div className="sidebar-logo-sub">Self-Healing ML Pipeline</div>
          </div>
        </div>

        {groups.map(g => (
          <div key={g}>
            <div className="sidebar-section">{g}</div>
            {PAGES.filter(p => p.group === g).map(p => (
              <NavItem key={p.id} p={p} active={page === p.id} onClick={() => navigate(p.id)} />
            ))}
          </div>
        ))}

        <div className="sidebar-footer">
          <div>
            <span className="status-dot"
              style={apiOk === false ? { background: 'var(--red)', animation: 'none' } : {}} />
            {apiOk === false ? 'API offline' : apiOk === null ? 'Connecting…' : 'API connected'}
          </div>
          <div style={{ marginTop: 3 }}>
            {datasets?.inspection?.columns?.length ?? '—'} columns · {typeof rows === 'number' ? rows.toLocaleString() : '—'} rows
          </div>
          {severity && (
            <div style={{ marginTop: 6 }}>
              <span className={`badge ${severity === 'severe' ? 'b-red' : severity === 'mild' ? 'b-orange' : 'b-green'}`}
                style={{ fontSize: 9, padding: '2px 8px' }}>
                {severity.toUpperCase()} DRIFT
              </span>
            </div>
          )}
        </div>
      </aside>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="topbar">
          <span className="topbar-breadcrumb">
            SH-DFS &rsaquo; <span>{currentPage?.group}</span> &rsaquo; <span>{currentPage?.label}</span>
          </span>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
            {health?.model_exists && (
              <span className="badge b-green" style={{ fontSize: 9, padding: '2px 8px' }}>Model Active</span>
            )}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6, fontSize: 11,
              color: apiOk === false ? 'var(--red)' : 'var(--green)',
              background: apiOk === false ? '#fef2f2' : '#ecfdf5',
              border: `1px solid ${apiOk === false ? '#fecaca' : '#a7f3d0'}`,
              padding: '5px 14px', borderRadius: 7, fontWeight: 600,
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: apiOk === false ? 'var(--red)' : 'var(--green)',
                display: 'inline-block',
              }} />
              {apiOk === false ? 'Offline' : 'Live'}
            </div>
          </div>
        </div>

        <main className="main" style={{ opacity: isPending ? 0.7 : 1, transition: 'opacity 0.12s' }}>
          <Suspense fallback={
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
              <div className="spinner" />
            </div>
          }>
            <div className="page-enter"><Page /></div>
          </Suspense>
        </main>
      </div>

      <ToastContainer />
    </div>
  )
}
