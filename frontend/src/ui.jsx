import { memo, useState, useEffect, useCallback } from 'react'
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'

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
    <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 16 }}>⚠</span>
      <span>{msg}</span>
    </span>
    {onRetry && (
      <button className="btn btn-outline" style={{ padding: '4px 12px', fontSize: 11, flexShrink: 0 }} onClick={onRetry}>
        ↻ Retry
      </button>
    )}
  </div>
))

export const KPI = memo(({ label, value, delta, color, trend, icon }) => (
  <div className="kpi">
    <div className="kpi-label">{icon && <span style={{ marginRight: 5 }}>{icon}</span>}{label}</div>
    <div className="kpi-value" style={color ? { color } : {}}>
      {value ?? '—'}
      {trend != null && (
        <span style={{ fontSize: 13, marginLeft: 7, color: trend >= 0 ? 'var(--green)' : 'var(--red)', fontFamily: 'sans-serif' }}>
          {trend >= 0 ? '↑' : '↓'}
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
  const map = { severe: ['red', '● SEVERE'], mild: ['orange', '◐ MILD'], none: ['green', '○ NONE'] }
  const [type, label] = map[severity] || ['blue', severity?.toUpperCase() || '—']
  return <Badge text={label} type={type} />
})

export const MiniSparkline = memo(({ data, dataKey, color = 'var(--blue)' }) => (
  <ResponsiveContainer width="100%" height={40}>
    <LineChart data={data}>
      <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={1.5} dot={false} />
      <Tooltip contentStyle={{ display: 'none' }} />
    </LineChart>
  </ResponsiveContainer>
))

// ── Toast system ────────────────────────────────────────────────────────────
let _addToast = null
export const toast = {
  success: msg => _addToast?.({ msg, type: 'g', icon: '✓' }),
  error:   msg => _addToast?.({ msg, type: 'r', icon: '✕' }),
  info:    msg => _addToast?.({ msg, type: 'b', icon: 'ℹ' }),
  warn:    msg => _addToast?.({ msg, type: 'y', icon: '⚠' }),
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

  const bgMap = { g: 'rgba(16,185,129,0.12)', r: 'rgba(239,68,68,0.12)', b: 'rgba(59,130,246,0.12)', y: 'rgba(245,158,11,0.12)' }
  const clrMap = { g: 'var(--green)', r: 'var(--red)', b: 'var(--blue)', y: 'var(--orange)' }
  const bdrMap = { g: 'rgba(16,185,129,0.25)', r: 'rgba(239,68,68,0.25)', b: 'rgba(59,130,246,0.25)', y: 'rgba(245,158,11,0.25)' }

  return (
    <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {toasts.map(t => (
        <div key={t.id} className="toast"
          style={{ background: bgMap[t.type], border: `1px solid ${bdrMap[t.type]}`, color: 'var(--text)', cursor: 'pointer' }}
          onClick={() => dismiss(t.id)}>
          <span style={{ color: clrMap[t.type], marginRight: 8, fontWeight: 700 }}>{t.icon}</span>
          {t.msg}
        </div>
      ))}
    </div>
  )
})

// ── Formatters ──────────────────────────────────────────────────────────────
export const fmt  = n => n == null ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 })
export const fmtK = n => n == null ? '—' : '$' + (n / 1000).toFixed(1) + 'K'
export const fmtD = n => n == null ? '—' : '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 })
export const fmtPct = n => n == null ? '—' : Number(n).toFixed(2) + '%'

// ── Chart tooltip style ──────────────────────────────────────────────────────
export const CHART_STYLE = {
  contentStyle: {
    background: 'var(--card)',
    border: '1px solid var(--border2)',
    color: 'var(--text)',
    fontSize: 12,
    borderRadius: 8,
    boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
    padding: '10px 14px',
  },
  labelStyle: { color: 'var(--text2)', fontWeight: 600, marginBottom: 4 },
  itemStyle: { color: 'var(--text2)' },
}

// ── Empty state ──────────────────────────────────────────────────────────────
export const EmptyState = memo(({ icon = '📭', title = 'No data', sub }) => (
  <div style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--text3)' }}>
    <div style={{ fontSize: 36, marginBottom: 12, opacity: 0.5 }}>{icon}</div>
    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text2)', marginBottom: 6 }}>{title}</div>
    {sub && <div style={{ fontSize: 12 }}>{sub}</div>}
  </div>
))
