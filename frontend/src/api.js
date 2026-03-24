import { useEffect, useState, useCallback, useRef } from 'react'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ── Cache + dedup ─────────────────────────────────────────────────────────────
const inflight = new Map()
export const memCache = new Map()   // exported so useFetch can read synchronously
const MEM_TTL = 15_000

// Bust cache when tab regains focus so data is always fresh on return
if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') memCache.clear()
  })
}

function dedupFetch(url, signal) {
  const hit   = memCache.get(url)
  const fresh = hit && Date.now() - hit.ts < MEM_TTL
  if (fresh) return Promise.resolve(hit.data)
  if (hit && !inflight.has(url)) {
    // stale: serve immediately, refresh in background
    const p = fetch(url)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(d => { memCache.set(url, { data: d, ts: Date.now() }); return d })
      .finally(() => inflight.delete(url))
    inflight.set(url, p)
    return Promise.resolve(hit.data)
  }
  if (inflight.has(url)) return inflight.get(url)
  const p = fetch(url, { signal })
    .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
    .then(d => { memCache.set(url, { data: d, ts: Date.now() }); return d })
    .finally(() => inflight.delete(url))
  inflight.set(url, p)
  return p
}

// ── useFetch — hooks always called in same order, lazy init from cache ─────────
export function useFetch(path, { pollMs = 0 } = {}) {
  const url = path ? BASE + path : null

  // Lazy initialisers run once — safe, no conditional hook calls
  const [data,    setData]    = useState(() => (url ? memCache.get(url)?.data : null) ?? null)
  const [loading, setLoading] = useState(() => !!url && !memCache.has(url))
  const [error,   setError]   = useState(null)
  const mounted = useRef(true)
  const hasData = useRef(!!url && memCache.has(url))

  const load = useCallback((bg = false) => {
    if (!url) return
    const ctrl = new AbortController()
    if (!bg && !hasData.current) { setLoading(true); setError(null) }
    dedupFetch(url, ctrl.signal)
      .then(d => {
        if (!mounted.current) return
        setData(d); setLoading(false); hasData.current = true
      })
      .catch(e => {
        if (e.name === 'AbortError' || !mounted.current) return
        if (!hasData.current) setError(e.message)
        setLoading(false)
      })
    return () => ctrl.abort()
  }, [url])

  useEffect(() => {
    mounted.current = true
    const cleanup = load(hasData.current)   // bg=true if cache hit → no spinner
    if (!pollMs) return () => { mounted.current = false; cleanup?.() }
    const id = setInterval(() => load(true), pollMs)
    return () => { mounted.current = false; cleanup?.(); clearInterval(id) }
  }, [load, pollMs])

  return { data, loading, error, reload: () => load(false) }
}

// ── usePredictions ─────────────────────────────────────────────────────────────
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
        setData(d); setLoading(false); setUpdatedAt(new Date())
        setFresh(true); setTimeout(() => { if (mounted.current) setFresh(false) }, 2500)
      })
      .catch(e => { if (e.name !== 'AbortError' && mounted.current) { setError(e.message); setLoading(false) } })
  }, [])

  useEffect(() => {
    mounted.current = true; knownMtime.current = null
    fetchData(month)
    return () => { mounted.current = false; abortRef.current?.abort() }
  }, [month, fetchData])

  useEffect(() => {
    if (!month) return
    const id = setInterval(() => {
      fetch(`${BASE}/api/predictions-meta`).then(r => r.json()).then(meta => {
        const mtime = meta[month]
        if (mtime == null) return
        if (knownMtime.current !== null && mtime !== knownMtime.current) fetchData(month)
        knownMtime.current = mtime
      }).catch(() => {})
    }, 12_000)
    return () => clearInterval(id)
  }, [month, fetchData])

  return { data, loading, error, updatedAt, fresh, reload: () => fetchData(month) }
}

export const API = {
  drift:           () => fetch(BASE + '/api/drift').then(r => r.json()),
  health:          () => fetch(BASE + '/api/health').then(r => r.json()),
  healingStatus:   () => fetch(BASE + '/api/healing-status').then(r => r.json()),
  healingActions:  () => fetch(BASE + '/api/healing-actions').then(r => r.json()),
  uploadPredict:   file => {
    const fd = new FormData(); fd.append('file', file)
    return fetch(BASE + '/api/upload-predict', { method: 'POST', body: fd })
  },
  uploadMonitor:   file => {
    const fd = new FormData(); fd.append('file', file)
    return fetch(BASE + '/api/upload-monitor', { method: 'POST', body: fd })
  },
  // Sequential prediction cycle
  seqStatus:       () => fetch(BASE + '/api/seq/status').then(r => r.json()),
  seqPredictNext:  () => fetch(BASE + '/api/seq/predict-next', { method: 'POST' }).then(r => r.json()),
  seqUploadActuals: file => {
    const fd = new FormData(); fd.append('file', file)
    return fetch(BASE + '/api/seq/upload-actuals', { method: 'POST', body: fd })
  },
  seqPrediction:   month => fetch(BASE + `/api/seq/prediction/${month}`).then(r => r.json()),
  seqComparison:   month => fetch(BASE + `/api/seq/comparison/${month}`).then(r => r.json()),
  seqDriftAnalysis: () => fetch(BASE + '/api/seq/drift-analysis').then(r => r.json()),
}
