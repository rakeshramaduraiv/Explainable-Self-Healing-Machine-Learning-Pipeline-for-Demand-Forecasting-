import { useState, lazy, Suspense, useEffect, useCallback, memo } from 'react'
import { Spinner, ToastContainer } from './ui.jsx'
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

// Prefetch all chunks on idle so navigation is instant after first load
const prefetchAll = () => [
  import('./pages/Drift.jsx'), import('./pages/Performance.jsx'),
  import('./pages/Features.jsx'), import('./pages/StoreStats.jsx'),
  import('./pages/Predictions.jsx'), import('./pages/Upload.jsx'),
  import('./pages/Datasets.jsx'), import('./pages/Demand.jsx'),
]

const PAGES = [
  { id: 'overview',     label: 'Overview',           icon: '⬡', group: 'Monitor' },
  { id: 'drift',        label: 'Drift Analysis',     icon: '◈', group: 'Monitor' },
  { id: 'performance',  label: 'Model Performance',  icon: '▲', group: 'Monitor' },
  { id: 'features',     label: 'Feature Importance', icon: '◉', group: 'Analysis' },
  { id: 'storestats',   label: 'Store Analytics',    icon: '▦', group: 'Analysis' },
  { id: 'predictions',  label: 'Predictions',        icon: '◎', group: 'Analysis' },
  { id: 'demand',       label: 'Demand Insights',    icon: '📈', group: 'Analysis' },
  { id: 'datasets',     label: 'Datasets',           icon: '🗄', group: 'Data' },
  { id: 'upload',       label: 'Upload & Monitor',   icon: '⬆', group: 'Data' },
]

const MAP = {
  overview: Overview, drift: Drift, performance: Performance,
  features: Features, storestats: StoreStats, predictions: Predictions,
  upload: Upload, datasets: Datasets, demand: Demand,
}

const groups = [...new Set(PAGES.map(p => p.group))]

const NavItem = memo(({ p, active, onClick }) => (
  <div
    className={`nav-item${active ? ' active' : ''}`}
    onClick={onClick}
    title={p.label}
  >
    <span className="nav-icon">{p.icon}</span>
    <span className="nav-label">{p.label}</span>
  </div>
))

const PageLoader = memo(() => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
    <div style={{ textAlign: 'center' }}>
      <Spinner />
      <div style={{ color: 'var(--text3)', fontSize: 12, marginTop: 8 }}>Loading…</div>
    </div>
  </div>
))

export default function App() {
  const [page, setPage] = useState('overview')
  const [apiOk, setApiOk] = useState(null)

  const navigate = useCallback(id => setPage(id), [])

  useEffect(() => {
    // Prefetch all page chunks after first paint
    if ('requestIdleCallback' in window) requestIdleCallback(prefetchAll)
    else setTimeout(prefetchAll, 1000)
  }, [])

  useEffect(() => {
    const check = () => API.health().then(() => setApiOk(true)).catch(() => setApiOk(false))
    check()
    const id = setInterval(check, 20000)
    return () => clearInterval(id)
  }, [])

  // Keyboard shortcut: Alt+1..9
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
          <div className="sidebar-logo-icon">⬡</div>
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
            <span className="status-dot" style={apiOk === false ? { background: 'var(--red)', animation: 'none' } : {}} />
            {apiOk === false ? 'API offline' : apiOk === null ? 'Connecting…' : 'API connected'}
          </div>
          <div style={{ marginTop: 2 }}>45 stores · 6,435 rows</div>
          <div style={{ marginTop: 2, fontSize: 10, opacity: 0.6 }}>Alt+1–9 to navigate</div>
        </div>
      </aside>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="topbar">
          <span className="topbar-breadcrumb">
            SH-DFS &rsaquo; <span>{currentPage?.group}</span> &rsaquo; <span>{currentPage?.label}</span>
          </span>
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              fontSize: 11, color: apiOk === false ? 'var(--red)' : 'var(--green)',
              background: apiOk === false ? 'rgba(239,68,68,0.08)' : 'rgba(16,185,129,0.08)',
              border: `1px solid ${apiOk === false ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)'}`,
              padding: '4px 10px', borderRadius: 6,
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: apiOk === false ? 'var(--red)' : 'var(--green)',
                display: 'inline-block',
                boxShadow: apiOk !== false ? '0 0 6px var(--green)' : 'none',
              }} />
              {apiOk === false ? 'Offline' : 'Live'}
            </div>
          </div>
        </div>

        <main className="main">
          <Suspense fallback={<PageLoader />}>
            <div className="page-enter">
              <Page />
            </div>
          </Suspense>
        </main>
      </div>

      <ToastContainer />
    </div>
  )
}
