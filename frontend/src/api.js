import { useEffect, useState, useCallback, useRef } from 'react'

const BASE = import.meta.env.VITE_API_URL || ''

// ── Client cache (30s TTL) + stale-while-revalidate + in-flight dedup ─────────
const inflight = new Map()
const memCache = new Map()
const MEM_TTL  = 30_000

function dedupFetch(url, signal) {
  const hit   = memCache.get(url)
  const fresh = hit && Date.now() - hit.ts < MEM_TTL
  if (fresh) return Promise.resolve(hit.data)
  // stale: return old data immediately, refresh in background
  if (hit && !inflight.has(url)) {
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

// ── useFetch — instant render from cache, zero loading flash on revisit ───────
export function useFetch(path, { pollMs = 0 } = {}) {
  const url    = path ? BASE + path : null
  const cached = url ? memCache.get(url) : null

  // Initialise directly from cache — loading=false if we already have data
  const [data,    setData]    = useState(cached?.data ?? null)
  const [loading, setLoading] = useState(!cached && !!path)
  const [error,   setError]   = useState(null)
  const mounted = useRef(true)
  const hasData = useRef(!!cached)

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
    // If we have cached data, load in background (no spinner)
    const cleanup = load(!!cached)
    if (!pollMs) return () => { mounted.current = false; cleanup?.() }
    const id = setInterval(() => load(true), pollMs)
    return () => { mounted.current = false; cleanup?.(); clearInterval(id) }
  }, [load, pollMs])

  return { data, loading, error, reload: () => load(false) }
}

// ── usePredictions — polls meta, re-fetches only when file changes ─────────────
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
