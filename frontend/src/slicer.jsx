import { useSyncExternalStore, memo, useCallback } from 'react'

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

const SEV_LABELS = { severe: '● Severe', mild: '◐ Mild', none: '○ None' }

export const SlicerPanel = memo(({ months = [], stores = [], slicer }) => {
  const active = slicer.months.length || slicer.stores.length || slicer.severity
  const count  = slicer.months.length + slicer.stores.length + (slicer.severity ? 1 : 0)

  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '10px 14px', marginBottom: 16,
      display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center',
    }}>
      <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.2px', marginRight: 4 }}>
        Filter
      </span>

      {months.map(m => (
        <button key={m} className={`slicer-pill${slicer.months.includes(m) ? ' active' : ''}`}
          onClick={() => slicerActions.toggleMonth(m)}>{m}</button>
      ))}

      {stores.map(s => (
        <button key={s} className={`slicer-pill${slicer.stores.includes(s) ? ' active' : ''}`}
          onClick={() => slicerActions.toggleStore(s)}>Store {s}</button>
      ))}

      {['severe', 'mild', 'none'].map(v => (
        <button key={v} className={`slicer-pill${slicer.severity === v ? ' active' : ''}`}
          onClick={() => slicerActions.setSeverity(v)}>{SEV_LABELS[v]}</button>
      ))}

      {active ? (
        <button className="slicer-pill clear" onClick={slicerActions.clear}>
          ✕ Clear {count > 1 ? `(${count})` : ''}
        </button>
      ) : (
        <span style={{ fontSize: 11, color: 'var(--text3)', marginLeft: 4 }}>No filters active</span>
      )}
    </div>
  )
})
