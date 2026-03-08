// Pure store — no React components, safe for Fast Refresh
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
