export { slicerActions, useSlicerStore } from './slicerStore.js'

import { memo } from 'react'
import { slicerActions } from './slicerStore.js'

export const SlicerPanel = memo(({ months = [], stores = [], slicer }) => {
  const active = slicer.months.length || slicer.stores.length || slicer.severity
  const count  = slicer.months.length + slicer.stores.length + (slicer.severity ? 1 : 0)

  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '10px 14px', marginBottom: 16,
      display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center',
    }}>
      <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '1.4px', marginRight: 4 }}>
        Filter
      </span>

      {months.slice(0, 30).map(m => (
        <button key={m} className={`slicer-pill${slicer.months.includes(m) ? ' active' : ''}`}
          onClick={() => slicerActions.toggleMonth(m)}>{m}</button>
      ))}

      {stores.slice(0, 30).map(s => (
        <button key={s} className={`slicer-pill${slicer.stores.includes(s) ? ' active' : ''}`}
          onClick={() => slicerActions.toggleStore(s)}>Store {s}</button>
      ))}

      {['severe', 'mild', 'none'].map(v => (
        <button key={v} className={`slicer-pill${slicer.severity === v ? ' active' : ''}`}
          onClick={() => slicerActions.setSeverity(v)}
          style={{ textTransform: 'capitalize' }}>{v}</button>
      ))}

      {active ? (
        <button className="slicer-pill clear" onClick={slicerActions.clear}>
          Clear{count > 1 ? ` (${count})` : ''}
        </button>
      ) : (
        <span style={{ fontSize: 11, color: 'var(--text3)', marginLeft: 4 }}>No filters active</span>
      )}
    </div>
  )
})
