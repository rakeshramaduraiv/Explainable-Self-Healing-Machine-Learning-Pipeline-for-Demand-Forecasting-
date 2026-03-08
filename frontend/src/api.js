import { useEffect, useState, useCallback, useRef } from 'react'

const BASE = import.meta.env.VITE_API_URL || ''

// ── In-flight deduplication: same URL won't fire twice simultaneously ────────
const inflight = new Map()

function dedupFetch(url, signal) {
  if (inflight.has(url)) return inflight.get(url)
  const p = fetch(url, { signal })
    .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
    .finally(() => inflight.delete(url))
  inflight.set(url, p)
  return p
}

// ── Core fetch hook with polling + retry ─────────────────────────────────────
export function useFetch(path, { pollMs = 0 } = {}) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const retries = useRef(0)
  const mounted = useRef(true)

  const load = useCallback(() => {
    if (!path) return
    const ctrl = new AbortController()
    setLoading(true); setError(null)

    dedupFetch(BASE + path, ctrl.signal)
      .then(d => { if (mounted.current) { setData(d); setLoading(false); retries.current = 0 } })
      .catch(e => {
        if (e.name === 'AbortError' || !mounted.current) return
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
    mounted.current = true
    const cleanup = load()
    if (!pollMs) return () => { mounted.current = false; cleanup?.() }
    const id = setInterval(load, pollMs)
    return () => { mounted.current = false; cleanup?.(); clearInterval(id) }
  }, [load, pollMs])

  return { data, loading, error, reload: load }
}

// ── Smart predictions hook ────────────────────────────────────────────────────
export function usePredictions(month) {
  const [data,      setData]      = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState(null)
  const [updatedAt, setUpdatedAt] = useState(null)
  const [fresh,     setFresh]     = useState(false)
  const knownMtime = useRef(null)
  const abortRef   = useRef(null)
  const mounted    = useRef(true)

  const fetchData = useCallback(m => {
    if (!m) return
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setLoading(true); setError(null)

    fetch(`${BASE}/api/predictions/${m}`, { signal: ctrl.signal })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => {
        if (!mounted.current) return
        setData(d); setLoading(false)
        setUpdatedAt(new Date())
        setFresh(true)
        setTimeout(() => { if (mounted.current) setFresh(false) }, 2500)
      })
      .catch(e => {
        if (e.name !== 'AbortError' && mounted.current) { setError(e.message); setLoading(false) }
      })
  }, [])

  useEffect(() => {
    mounted.current = true
    knownMtime.current = null
    fetchData(month)
    return () => { mounted.current = false; abortRef.current?.abort() }
  }, [month, fetchData])

  useEffect(() => {
    if (!month) return
    const id = setInterval(() => {
      fetch(`${BASE}/api/predictions-meta`)
        .then(r => r.json())
        .then(meta => {
          const mtime = meta[month]
          if (mtime == null) return
          if (knownMtime.current !== null && mtime !== knownMtime.current) fetchData(month)
          knownMtime.current = mtime
        })
        .catch(() => {})
    }, 12_000)
    return () => clearInterval(id)
  }, [month, fetchData])

  return { data, loading, error, updatedAt, fresh, reload: () => fetchData(month) }
}

export const API = {
  drift:         () => fetch(BASE + '/api/drift').then(r => r.json()),
  health:        () => fetch(BASE + '/api/health').then(r => r.json()),
  uploadPredict: file => {
    const fd = new FormData(); fd.append('file', file)
    return fetch(BASE + '/api/upload-predict', { method: 'POST', body: fd })
  },
}
