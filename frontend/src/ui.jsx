import { memo, useState, useEffect } from 'react'
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'

export const Spinner = memo(() => <div className="spinner" />)

export const Skeleton = memo(({ h = 20, w = '100%', mb = 8 }) => (
  <div className="skel" style={{ height: h, width: w, marginBottom: mb }} />
))

export const SkeletonCard = memo(({ rows = 3 }) => (
  <div className="card">
    <Skeleton h={12} w="40%" mb={16} />
    {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} h={16} mb={10} />)}
  </div>
))

export const ErrorBox = memo(({ msg, onRetry }) => (
  <div className="alert alert-r" style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
    <span>⚠ {msg}</span>
    {onRetry && <button className="btn btn-outline" style={{ padding: '4px 12px', fontSize: 11 }} onClick={onRetry}>Retry</button>}
  </div>
))

export const KPI = memo(({ label, value, delta, color, trend }) => (
  <div className="kpi">
    <div className="kpi-label">{label}</div>
    <div className="kpi-value" style={color ? { color } : {}}>
      {value ?? '—'}
      {trend != null && (
        <span style={{ fontSize: 12, marginLeft: 6, color: trend >= 0 ? 'var(--green)' : 'var(--red)' }}>
          {trend >= 0 ? '▲' : '▼'}
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
        {action && <span style={{ marginLeft: 'auto', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>{action}</span>}
      </div>
    )}
    {children}
  </div>
))

export const Badge = memo(({ text, type = 'blue' }) => (
  <span className={`badge b-${type}`}>{text}</span>
))

export const SevBadge = memo(({ severity }) => {
  const map = { severe: 'red', mild: 'orange', none: 'green' }
  return <Badge text={severity?.toUpperCase()} type={map[severity] || 'blue'} />
})

export const MiniSparkline = memo(({ data, dataKey, color = 'var(--blue)' }) => (
  <ResponsiveContainer width="100%" height={40}>
    <LineChart data={data}>
      <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={1.5} dot={false} />
      <Tooltip contentStyle={{ display: 'none' }} />
    </LineChart>
  </ResponsiveContainer>
))

// Toast notification system
let _addToast = null
export const toast = {
  success: msg => _addToast?.({ msg, type: 'g' }),
  error:   msg => _addToast?.({ msg, type: 'r' }),
  info:    msg => _addToast?.({ msg, type: 'b' }),
}

export const ToastContainer = memo(() => {
  const [toasts, setToasts] = useState([])
  useEffect(() => {
    _addToast = (t) => {
      const id = Date.now()
      setToasts(p => [...p, { ...t, id }])
      setTimeout(() => setToasts(p => p.filter(x => x.id !== id)), 3500)
    }
    return () => { _addToast = null }
  }, [])
  return (
    <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {toasts.map(t => (
        <div key={t.id} className={`alert alert-${t.type}`}
          style={{ minWidth: 260, boxShadow: 'var(--shadow)', animation: 'fadeIn .2s ease' }}>
          {t.msg}
        </div>
      ))}
    </div>
  )
})

export const fmt  = n => n == null ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 })
export const fmtK = n => n == null ? '—' : '$' + (n / 1000).toFixed(1) + 'K'
export const fmtD = n => n == null ? '—' : '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 })

export const CHART_STYLE = {
  contentStyle: {
    background: 'var(--card)', border: '1px solid var(--border)',
    color: 'var(--text)', fontSize: 12, borderRadius: 6,
  }
}
