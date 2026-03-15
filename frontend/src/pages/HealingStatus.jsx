import { useState, useEffect } from 'react'
import { API } from '../api.js'

export function HealingStatusDisplay({ running }) {
  const [status, setStatus] = useState(null)
  const [logs, setLogs] = useState([])

  useEffect(() => {
    if (!running) return

    const interval = setInterval(async () => {
      try {
        const data = await API.healingStatus()
        setStatus(data)
        
        // Add to logs if action changed
        if (data.action && data.action !== 'idle') {
          setLogs(prev => {
            const isDuplicate = prev.length > 0 && 
              prev[prev.length - 1].action === data.action &&
              prev[prev.length - 1].month === data.month
            
            if (!isDuplicate) {
              return [...prev, { ...data, id: Date.now() }]
            }
            return prev
          })
        }
      } catch (e) {
        console.error('Failed to fetch healing status:', e)
      }
    }, 1000)

    return () => clearInterval(interval)
  }, [running])

  const getIcon = (action) => {
    if (action.includes('fine_tune')) return '🔧'
    if (action.includes('monitor')) return '👁️'
    if (action.includes('complete')) return '✅'
    if (action.includes('failed')) return '❌'
    return '⏳'
  }

  const getColor = (action) => {
    if (action.includes('fine_tune') && !action.includes('complete')) return '#3b82f6'
    if (action.includes('monitor')) return '#10b981'
    if (action.includes('complete')) return '#10b981'
    if (action.includes('failed')) return '#dc2626'
    return '#6b7280'
  }

  return (
    <div style={{ marginTop: 16 }}>
      {/* Current Status */}
      {status && status.action !== 'idle' && (
        <div style={{
          background: 'linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%)',
          border: `2px solid ${getColor(status.action)}`,
          borderRadius: 8,
          padding: 12,
          marginBottom: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 20 }}>{getIcon(status.action)}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, color: 'var(--text)', fontSize: 13 }}>
                {status.message}
              </div>
              {status.progress !== undefined && (
                <div style={{ marginTop: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>
                    <span>Progress</span>
                    <span>{status.progress}%</span>
                  </div>
                  <div style={{ height: 4, background: '#e5e7eb', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{
                      height: '100%',
                      width: `${status.progress}%`,
                      background: getColor(status.action),
                      transition: 'width 0.3s ease',
                    }} />
                  </div>
                </div>
              )}
              {status.improvement !== undefined && (
                <div style={{ marginTop: 6, fontSize: 11, color: 'var(--green)', fontWeight: 600 }}>
                  Improvement: {(status.improvement * 100).toFixed(1)}%
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Logs */}
      {logs.length > 0 && (
        <div style={{
          background: '#f9fafb',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: 12,
          maxHeight: 200,
          overflowY: 'auto',
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '1px' }}>
            Pipeline Log
          </div>
          {logs.map(log => (
            <div key={log.id} style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 0',
              borderBottom: '1px solid var(--border)',
              fontSize: 12,
              color: 'var(--text)',
            }}>
              <span style={{ fontSize: 14 }}>{getIcon(log.action)}</span>
              <span style={{ flex: 1 }}>{log.message}</span>
              {log.improvement !== undefined && (
                <span style={{ color: 'var(--green)', fontWeight: 600, fontSize: 11 }}>
                  +{(log.improvement * 100).toFixed(1)}%
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
