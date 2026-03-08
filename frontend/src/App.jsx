import { useState, lazy, Suspense, useEffect } from 'react'
import { Spinner, ToastContainer } from './ui.jsx'
import { API } from './api.js'

const Overview    = lazy(() => import('./pages/Overview.jsx'))
const Drift       = lazy(() => import('./pages/Drift.jsx'))
const Performance = lazy(() => import('./pages/Performance.jsx'))
const Features    = lazy(() => import('./pages/Features.jsx'))
const StoreStats  = lazy(() => import('./pages/StoreStats.jsx'))
const Predictions = lazy(() => import('./pages/Predictions.jsx'))
const Upload      = lazy(() => import('./pages/Upload.jsx'))

const PAGES = [
  { id: 'overview',     label: 'Overview',           icon: '◈', group: 'Monitor' },
  { id: 'drift',        label: 'Drift Analysis',     icon: '⬡', group: 'Monitor' },
  { id: 'performance',  label: 'Model Performance',  icon: '▲', group: 'Monitor' },
  { id: 'features',     label: 'Feature Importance', icon: '◉', group: 'Analysis' },
  { id: 'storestats',   label: 'Store Analytics',    icon: '▦', group: 'Analysis' },
  { id: 'predictions',  label: 'Predictions',        icon: '◎', group: 'Analysis' },
  { id: 'upload',       label: 'Upload & Monitor',   icon: '⬆', group: 'Actions' },
]

const MAP = { overview: Overview, drift: Drift, performance: Performance, features: Features, storestats: StoreStats, predictions: Predictions, upload: Upload }

export default function App() {
  const [page, setPage] = useState('overview')
  const [apiOk, setApiOk] = useState(null)
  const Page = MAP[page]
  const groups = [...new Set(PAGES.map(p => p.group))]

  useEffect(() => {
    const check = () => API.health().then(() => setApiOk(true)).catch(() => setApiOk(false))
    check()
    const id = setInterval(check, 15000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">◈</div>
          <div className="sidebar-logo-text">
            SH-DFS <span>Monitor</span>
            <div className="sidebar-logo-sub">Phase 1 · Walmart Sales</div>
          </div>
        </div>
        {groups.map(g => (
          <div key={g}>
            <div className="sidebar-section">{g}</div>
            {PAGES.filter(p => p.group === g).map(p => (
              <div key={p.id} className={`nav-item${page === p.id ? ' active' : ''}`} onClick={() => setPage(p.id)}>
                <span className="nav-icon">{p.icon}</span>
                <span>{p.label}</span>
              </div>
            ))}
          </div>
        ))}
        <div className="sidebar-footer">
          <div>
            <span className="status-dot" style={apiOk === false ? { background: 'var(--red)', animation: 'none' } : {}} />
            {apiOk === false ? 'API offline' : 'API connected'}
          </div>
          <div style={{ marginTop: 3 }}>45 stores · 6,435 rows</div>
        </div>
      </aside>
      <main className="main">
        <Suspense fallback={<Spinner />}>
          <Page />
        </Suspense>
      </main>
      <ToastContainer />
    </div>
  )
}
