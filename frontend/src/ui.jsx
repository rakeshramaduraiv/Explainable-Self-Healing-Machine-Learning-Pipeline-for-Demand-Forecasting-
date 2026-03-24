import { memo, useState, useEffect, useCallback } from 'react'

export const Spinner = memo(() => <div className="spinner" />)

export const Skeleton = memo(({ h = 20, w = '100%', mb = 8 }) => (
  <div className="skel" style={{ height: h, width: w, marginBottom: mb }} />
))

export const SkeletonCard = memo(({ rows = 3 }) => (
  <div className="card">
    <Skeleton h={10} w="35%" mb={18} />
    {Array.from({ length: rows }).map((_, i) => (
      <Skeleton key={i} h={14} w={i % 2 === 0 ? '100%' : '80%'} mb={10} />
    ))}
  </div>
))

export const ErrorBox = memo(({ msg, onRetry }) => (
  <div className="alert alert-r" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
    <span style={{ fontSize: 13 }}>{msg}</span>
    {onRetry && (
      <button className="btn btn-outline" style={{ padding: '4px 12px', fontSize: 11, flexShrink: 0 }} onClick={onRetry}>
        Retry
      </button>
    )}
  </div>
))

export const KPI = memo(({ label, value, delta, color, trend }) => (
  <div className="kpi">
    <div className="kpi-label">{label}</div>
    <div className="kpi-value" style={color ? { color } : {}}>
      {value ?? '—'}
      {trend != null && (
        <span style={{ fontSize: 12, marginLeft: 8, color: trend >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 500 }}>
          {trend >= 0 ? '+' : ''}{trend.toFixed(1)}%
        </span>
      )}
    </div>
    {delta && <div className="kpi-delta">{delta}</div>}
  </div>
))

export const SectionCard = memo(({ title, children, style, action }) => (
  <div className="card" style={style}>
    {title && (
      <div className="card-title">
        {title}
        {action && (
          <span style={{ marginLeft: 'auto', fontWeight: 500, textTransform: 'none', letterSpacing: 0, fontSize: 12 }}>
            {action}
          </span>
        )}
      </div>
    )}
    {children}
  </div>
))

export const Badge = memo(({ text, type = 'blue' }) => (
  <span className={`badge b-${type}`}>{text}</span>
))

export const SevBadge = memo(({ severity }) => {
  const map = { severe: ['red', 'Severe'], mild: ['orange', 'Mild'], none: ['green', 'None'] }
  const [type, label] = map[severity] || ['blue', severity?.toUpperCase() || '—']
  return <Badge text={label} type={type} />
})

// ── Toast system ─────────────────────────────────────────────────────────────
let _addToast = null
export const toast = {
  success: msg => _addToast?.({ msg, type: 'g' }),
  error:   msg => _addToast?.({ msg, type: 'r' }),
  info:    msg => _addToast?.({ msg, type: 'b' }),
  warn:    msg => _addToast?.({ msg, type: 'y' }),
}

export const ToastContainer = memo(() => {
  const [toasts, setToasts] = useState([])

  useEffect(() => {
    _addToast = t => {
      const id = Date.now()
      setToasts(p => [...p.slice(-4), { ...t, id }])
      setTimeout(() => setToasts(p => p.filter(x => x.id !== id)), 4000)
    }
    return () => { _addToast = null }
  }, [])

  const dismiss = useCallback(id => setToasts(p => p.filter(x => x.id !== id)), [])

  const bgMap  = { g: '#f0fdf4', r: '#fef2f2', b: '#eff6ff', y: '#fffbeb' }
  const clrMap = { g: 'var(--green)', r: 'var(--red)', b: 'var(--blue)', y: 'var(--orange)' }
  const bdrMap = { g: '#bbf7d0', r: '#fecaca', b: '#bfdbfe', y: '#fde68a' }
  const lblMap = { g: 'Success', r: 'Error', b: 'Info', y: 'Warning' }

  return (
    <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {toasts.map(t => (
        <div key={t.id} className="toast"
          style={{ background: bgMap[t.type], border: `1px solid ${bdrMap[t.type]}`, color: 'var(--text)', cursor: 'pointer' }}
          onClick={() => dismiss(t.id)}>
          <span style={{ color: clrMap[t.type], fontWeight: 700, marginRight: 8, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{lblMap[t.type]}</span>
          {t.msg}
        </div>
      ))}
    </div>
  )
})

// ── Formatters ───────────────────────────────────────────────────────────────
export const fmt    = n => n == null ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 })
export const fmtK   = n => n == null ? '—' : (n / 1000).toFixed(1) + 'K'
export const fmtD   = n => n == null ? '—' : Number(n).toFixed(2)
export const fmtPct = n => n == null ? '—' : Number(n).toFixed(2) + '%'

export const CHART_STYLE = {
  contentStyle: {
    background: '#ffffff',
    border: '1px solid var(--border2)',
    color: 'var(--text)',
    fontSize: 12,
    borderRadius: 10,
    boxShadow: '0 8px 32px rgba(37,99,235,0.12)',
    padding: '12px 16px',
  },
  labelStyle: { color: 'var(--text2)', fontWeight: 700, marginBottom: 6 },
  itemStyle:  { color: 'var(--text2)' },
}

export const EmptyState = memo(({ title = 'No data', sub }) => (
  <div style={{ textAlign: 'center', padding: '48px 24px' }}>
    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text2)', marginBottom: 6 }}>{title}</div>
    {sub && <div style={{ fontSize: 12, color: 'var(--text3)' }}>{sub}</div>}
  </div>
))
