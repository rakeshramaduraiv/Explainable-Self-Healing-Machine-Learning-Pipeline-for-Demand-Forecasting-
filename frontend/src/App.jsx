import { useState, lazy, Suspense, useEffect, useCallback, memo, useTransition } from 'react'
import { ToastContainer } from './ui.jsx'
import { API } from './api.js'

const Overview    = lazy(() => import('./pages/Overview.jsx'))
const Drift       = lazy(() => import('./pages/Drift.jsx'))
const Performance = lazy(() => import('./pages/Performance.jsx'))
const Features    = lazy(() => import('./pages/Features.jsx'))
const StoreStats  = lazy(() => import('./pages/StoreStats.jsx'))
const Predictions = lazy(() => import('./pages/Predictions.jsx'))
const Upload      = lazy(() => import('./pages/Upload.jsx'))
const Datasets    = lazy(() => import('./pages/Datasets.jsx'))
const Demand      = lazy(() => import('./pages/Demand.jsx'))

const prefetchAll = () => [
  import('./pages/Drift.jsx'), import('./pages/Performance.jsx'),
  import('./pages/Features.jsx'), import('./pages/StoreStats.jsx'),
  import('./pages/Predictions.jsx'), import('./pages/Upload.jsx'),
  import('./pages/Datasets.jsx'), import('./pages/Demand.jsx'),
]

const PAGES = [
  { id: 'overview',    label: 'Overview',           group: 'Monitor' },
  { id: 'drift',       label: 'Drift Analysis',     group: 'Monitor' },
  { id: 'performance', label: 'Model Performance',  group: 'Monitor' },
  { id: 'features',    label: 'Feature Importance', group: 'Analysis' },
  { id: 'storestats',  label: 'Store Analytics',    group: 'Analysis' },
  { id: 'predictions', label: 'Predictions',        group: 'Analysis' },
  { id: 'demand',      label: 'Demand Insights',    group: 'Analysis' },
  { id: 'datasets',    label: 'Datasets',           group: 'Data' },
  { id: 'upload',      label: 'Upload & Monitor',   group: 'Data' },
]

const MAP = {
  overview: Overview, drift: Drift, performance: Performance,
  features: Features, storestats: StoreStats, predictions: Predictions,
  upload: Upload, datasets: Datasets, demand: Demand,
}

const groups = [...new Set(PAGES.map(p => p.group))]

const NavItem = memo(({ p, active, onClick }) => (
  <div className={`nav-item${active ? ' active' : ''}`} onClick={onClick} title={p.label}>
    <span className="nav-label">{p.label}</span>
  </div>
))

export default function App() {
  const [page, setPage]   = useState('overview')
  const [apiOk, setApiOk] = useState(null)
  const [isPending, startTransition] = useTransition()

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

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon" />
          <div className="sidebar-logo-text">
            <div className="sidebar-logo-name">SH-DFS <span>Monitor</span></div>
            <div className="sidebar-logo-sub">Walmart · Phase 1</div>
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
          <div style={{ marginTop: 2 }}>45 stores · 6,435 rows</div>
        </div>
      </aside>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="topbar">
          <span className="topbar-breadcrumb">
            SH-DFS &rsaquo; <span>{currentPage?.group}</span> &rsaquo; <span>{currentPage?.label}</span>
          </span>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6, fontSize: 11,
              color: apiOk === false ? 'var(--red)' : 'var(--green)',
              background: apiOk === false ? '#fef2f2' : '#f0fdf4',
              border: `1px solid ${apiOk === false ? '#fecaca' : '#bbf7d0'}`,
              padding: '4px 12px', borderRadius: 6, fontWeight: 600,
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

        <main className="main" style={{ opacity: isPending ? 0.7 : 1, transition: 'opacity 0.1s' }}>
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
