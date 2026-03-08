import { useEffect, useState, useCallback, useRef } from 'react'

const BASE = import.meta.env.VITE_API_URL || ''

// ── Core fetch hook with polling + retry ────────────────────────────────────────────
export function useFetch(path, { pollMs = 0 } = {}) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const retries = useRef(0)

  const load = useCallback(() => {
    if (!path) return
    setLoading(true); setError(null)
    const ctrl = new AbortController()
    fetch(BASE + path, { signal: ctrl.signal })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => { setData(d); setLoading(false); retries.current = 0 })
      .catch(e => {
        if (e.name === 'AbortError') return
        if (retries.current < 2) {
          retries.current++
          setTimeout(load, retries.current * 1500)
        } else {
          setError(e.message); setLoading(false)
        }
      })
    return () => ctrl.abort()
  }, [path])

  useEffect(() => {
    const cleanup = load()
    if (!pollMs) return cleanup
    const id = setInterval(load, pollMs)
    return () => { cleanup?.(); clearInterval(id) }
  }, [load, pollMs])

  return { data, loading, error, reload: load }
}

// ── Smart predictions hook — polls meta for changes, only re-fetches when file changes ──
export function usePredictions(month) {
  const [data,      setData]      = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState(null)
  const [updatedAt, setUpdatedAt] = useState(null)  // last data refresh timestamp
  const [fresh,     setFresh]     = useState(false) // pulse flag
  const knownMtime = useRef(null)
  const abortRef   = useRef(null)

  const fetchData = useCallback((m) => {
    if (!m) return
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setLoading(true); setError(null)
    fetch(`${BASE}/api/predictions/${m}`, { signal: ctrl.signal })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => {
        setData(d); setLoading(false)
        setUpdatedAt(new Date())
        setFresh(true)
        setTimeout(() => setFresh(false), 2500)
      })
      .catch(e => { if (e.name !== 'AbortError') { setError(e.message); setLoading(false) } })
  }, [])

  // Initial load when month changes
  useEffect(() => {
    knownMtime.current = null
    fetchData(month)
    return () => abortRef.current?.abort()
  }, [month, fetchData])

  // Poll meta every 10s — only re-fetch if mtime changed
  useEffect(() => {
    if (!month) return
    const id = setInterval(() => {
      fetch(`${BASE}/api/predictions-meta`)
        .then(r => r.json())
        .then(meta => {
          const mtime = meta[month]
          if (mtime == null) return
          if (knownMtime.current !== null && mtime !== knownMtime.current) {
            fetchData(month)
          }
          knownMtime.current = mtime
        })
        .catch(() => {})
    }, 10_000)
    return () => clearInterval(id)
  }, [month, fetchData])

  return { data, loading, error, updatedAt, fresh, reload: () => fetchData(month) }
}

export const API = {
  drift:         () => fetch(BASE + '/api/drift').then(r => r.json()),
  health:        () => fetch(BASE + '/api/health').then(r => r.json()),
  uploadPredict: (file) => {
    const fd = new FormData(); fd.append('file', file)
    return fetch(BASE + '/api/upload-predict', { method: 'POST', body: fd })
  },
}
