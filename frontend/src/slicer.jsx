import { useSyncExternalStore } from 'react'

let state = { months: [], stores: [], severity: '' }
const listeners = new Set()
const notify = () => listeners.forEach(l => l())

export const slicerActions = {
  toggleMonth: m => {
    state = { ...state, months: state.months.includes(m) ? state.months.filter(x => x !== m) : [...state.months, m] }
    notify()
  },
  toggleStore: s => {
    state = { ...state, stores: state.stores.includes(s) ? state.stores.filter(x => x !== s) : [...state.stores, s] }
    notify()
  },
  setSeverity: v => { state = { ...state, severity: state.severity === v ? '' : v }; notify() },
  clear: () => { state = { months: [], stores: [], severity: '' }; notify() },
}

export const useSlicerStore = () =>
  useSyncExternalStore(cb => { listeners.add(cb); return () => listeners.delete(cb) }, () => state)

export function SlicerPanel({ months = [], stores = [], slicer }) {
  const active = slicer.months.length || slicer.stores.length || slicer.severity
  return (
    <div style={{ display:'flex', flexWrap:'wrap', gap:6, marginBottom:12, alignItems:'center' }}>
      {months.map(m => (
        <button key={m} onClick={() => slicerActions.toggleMonth(m)}
          style={{ fontSize:11, padding:'2px 8px', borderRadius:4, cursor:'pointer', border:'1px solid',
            borderColor: slicer.months.includes(m) ? 'var(--blue)' : 'var(--border)',
            background: slicer.months.includes(m) ? 'rgba(59,130,246,.15)' : 'transparent',
            color: slicer.months.includes(m) ? 'var(--blue)' : 'var(--text2)' }}>
          {m}
        </button>
      ))}
      {stores.map(s => (
        <button key={s} onClick={() => slicerActions.toggleStore(s)}
          style={{ fontSize:11, padding:'2px 8px', borderRadius:4, cursor:'pointer', border:'1px solid',
            borderColor: slicer.stores.includes(s) ? 'var(--blue)' : 'var(--border)',
            background: slicer.stores.includes(s) ? 'rgba(59,130,246,.15)' : 'transparent',
            color: slicer.stores.includes(s) ? 'var(--blue)' : 'var(--text2)' }}>
          Store {s}
        </button>
      ))}
      {['severe','mild','none'].map(v => (
        <button key={v} onClick={() => slicerActions.setSeverity(v)}
          style={{ fontSize:11, padding:'2px 8px', borderRadius:4, cursor:'pointer', border:'1px solid',
            borderColor: slicer.severity === v ? 'var(--blue)' : 'var(--border)',
            background: slicer.severity === v ? 'rgba(59,130,246,.15)' : 'transparent',
            color: slicer.severity === v ? 'var(--blue)' : 'var(--text2)' }}>
          {v}
        </button>
      ))}
      {active ? (
        <button onClick={slicerActions.clear}
          style={{ fontSize:11, padding:'2px 8px', borderRadius:4, cursor:'pointer',
            border:'1px solid var(--red)', background:'rgba(239,68,68,.1)', color:'var(--red)' }}>
          Clear
        </button>
      ) : null}
    </div>
  )
}
