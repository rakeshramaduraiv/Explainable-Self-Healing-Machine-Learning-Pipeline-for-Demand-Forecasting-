import { useEffect, useState, useCallback, useRef } from 'react'

const BASE = import.meta.env.VITE_API_URL || ''

// ── Client-side memory cache (30s TTL) + stale-while-revalidate + in-flight dedup ──
const inflight = new Map()
const memCache = new Map()
const MEM_TTL  = 30_000   // serve from cache instantly, revalidate in background

function dedupFetch(url, signal) {
  const hit = memCache.get(url)
  const fresh = hit && Date.now() - hit.ts < MEM_TTL
  // Always revalidate in background after TTL, but return stale immediately
  if (hit && !fresh) {
    // stale — return old data now, kick off background refresh
    if (!inflight.has(url)) {
      const p = fetch(url)
        .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
        .then(d => { memCache.set(url, { data: d, ts: Date.now() }); return d })
        .finally(() => inflight.delete(url))
      inflight.set(url, p)
    }
    return Promise.resolve(hit.data)
  }
  if (fresh) return Promise.resolve(hit.data)
  if (inflight.has(url)) return inflight.get(url)
  const p = fetch(url, { signal })
    .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
    .then(d => { memCache.set(url, { data: d, ts: Date.now() }); return d })
    .finally(() => inflight.delete(url))
  inflight.set(url, p)
  return p
}

// ── Core fetch hook — no skeleton flash on background polls ──────────────────
export function useFetch(path, { pollMs = 0 } = {}) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(!!path)
  const [error,   setError]   = useState(null)
  const retries = useRef(0)
  const mounted = useRef(true)
  const hasData = useRef(false)

  const load = useCallback((bg = false) => {
    if (!path) return
    const ctrl = new AbortController()
    if (!bg) { setLoading(true); setError(null) }

    dedupFetch(BASE + path, ctrl.signal)
      .then(d => {
        if (!mounted.current) return
        setData(d); setLoading(false); retries.current = 0; hasData.current = true
      })
      .catch(e => {
        if (e.name === 'AbortError' || !mounted.current) return
        if (retries.current < 2) { retries.current++; setTimeout(() => load(bg), retries.current * 1500) }
        else { if (!hasData.current) setError(e.message); setLoading(false) }
      })
    return () => ctrl.abort()
  }, [path])

  useEffect(() => {
    mounted.current = true; hasData.current = false
    const cleanup = load(false)
    if (!pollMs) return () => { mounted.current = false; cleanup?.() }
    const id = setInterval(() => load(true), pollMs)
    return () => { mounted.current = false; cleanup?.(); clearInterval(id) }
  }, [load, pollMs])

  return { data, loading, error, reload: () => load(false) }
}

// ── Smart predictions hook — polls meta, re-fetches only on file change ───────
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
  drift:         () => fetch(BASE + '/api/drift').then(r => r.json()),
  health:        () => fetch(BASE + '/api/health').then(r => r.json()),
  uploadPredict: file => {
    const fd = new FormData(); fd.append('file', file)
    return fetch(BASE + '/api/upload-predict', { method: 'POST', body: fd })
  },
}
