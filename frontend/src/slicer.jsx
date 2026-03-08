import { useState, useEffect, memo } from 'react'

// ── Global slicer state ──────────────────────────────────────────────────────
let _listeners = []
const _state = { stores: [], months: [], severity: null }

function notify() { _listeners.forEach(fn => fn({ ..._state, stores:[..._state.stores], months:[..._state.months] })) }

export function useSlicerStore() {
  const [s, setS] = useState(() => ({ ..._state, stores:[..._state.stores], months:[..._state.months] }))
  useEffect(() => {
    _listeners.push(setS)
    return () => { _listeners = _listeners.filter(f => f !== setS) }
  }, [])
  return s
}

export const slicerActions = {
  toggleStore:   id  => { const i=_state.stores.indexOf(id); _state.stores = i>=0 ? _state.stores.filter(s=>s!==id) : [..._state.stores,id]; notify() },
  toggleMonth:   m   => { const i=_state.months.indexOf(m);  _state.months = i>=0 ? _state.months.filter(x=>x!==m)  : [..._state.months,m];  notify() },
  setSeverity:   sev => { _state.severity = _state.severity===sev ? null : sev; notify() },
  clearAll:      ()  => { _state.stores=[]; _state.months=[]; _state.severity=null; notify() },
}

// ── Slicer Panel UI ──────────────────────────────────────────────────────────
export const SlicerPanel = memo(({ stores = [], months = [], slicer }) => {
  const hasFilter = slicer.stores.length || slicer.months.length || slicer.severity

  return (
    <div style={{
      background:'var(--card)', border:'1px solid var(--border)', borderRadius:8,
      padding:'14px 16px', marginBottom:18, fontSize:12
    }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:12 }}>
        <span style={{ fontWeight:700, color:'var(--text)', fontSize:11, textTransform:'uppercase', letterSpacing:'1.2px' }}>
          ▼ Slicers
        </span>
        {hasFilter && (
          <button className="btn btn-outline" style={{ padding:'2px 10px', fontSize:11 }}
            onClick={slicerActions.clearAll}>✕ Clear all</button>
        )}
      </div>

      <div style={{ display:'flex', gap:20, flexWrap:'wrap' }}>
        {/* Severity slicer */}
        <div>
          <div style={{ color:'var(--text3)', fontSize:10, fontWeight:700, textTransform:'uppercase', letterSpacing:'1px', marginBottom:6 }}>Severity</div>
          <div style={{ display:'flex', gap:5 }}>
            {['severe','mild','none'].map(sev => (
              <button key={sev}
                onClick={() => slicerActions.setSeverity(sev)}
                style={{
                  padding:'3px 10px', borderRadius:4, fontSize:11, fontWeight:600, cursor:'pointer', border:'1px solid',
                  borderColor: sev==='severe'?'rgba(239,68,68,.4)':sev==='mild'?'rgba(245,158,11,.4)':'rgba(16,185,129,.4)',
                  background: slicer.severity===sev
                    ? (sev==='severe'?'rgba(239,68,68,.2)':sev==='mild'?'rgba(245,158,11,.2)':'rgba(16,185,129,.2)')
                    : 'transparent',
                  color: sev==='severe'?'#f87171':sev==='mild'?'#fbbf24':'#34d399',
                  opacity: slicer.severity && slicer.severity!==sev ? 0.4 : 1,
                }}>
                {sev.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Month slicer */}
        {months.length > 0 && (
          <div style={{ flex:1, minWidth:200 }}>
            <div style={{ color:'var(--text3)', fontSize:10, fontWeight:700, textTransform:'uppercase', letterSpacing:'1px', marginBottom:6 }}>
              Month {slicer.months.length > 0 && <span style={{ color:'var(--blue)' }}>({slicer.months.length} selected)</span>}
            </div>
            <div style={{ display:'flex', gap:4, flexWrap:'wrap' }}>
              {months.map(m => {
                const active = slicer.months.includes(m)
                return (
                  <button key={m} onClick={() => slicerActions.toggleMonth(m)}
                    style={{
                      padding:'2px 8px', borderRadius:4, fontSize:10, cursor:'pointer', border:'1px solid',
                      borderColor: active ? 'var(--blue)' : 'var(--border2)',
                      background:  active ? 'rgba(59,130,246,.15)' : 'transparent',
                      color:       active ? 'var(--blue)' : 'var(--text3)',
                      fontWeight:  active ? 700 : 400,
                    }}>{m}</button>
                )
              })}
            </div>
          </div>
        )}

        {/* Store slicer */}
        {stores.length > 0 && (
          <div style={{ flex:1, minWidth:200 }}>
            <div style={{ color:'var(--text3)', fontSize:10, fontWeight:700, textTransform:'uppercase', letterSpacing:'1px', marginBottom:6 }}>
              Store {slicer.stores.length > 0 && <span style={{ color:'var(--blue)' }}>({slicer.stores.length} selected)</span>}
            </div>
            <div style={{ display:'flex', gap:4, flexWrap:'wrap', maxHeight:72, overflowY:'auto' }}>
              {stores.map(s => {
                const active = slicer.stores.includes(s)
                return (
                  <button key={s} onClick={() => slicerActions.toggleStore(s)}
                    style={{
                      padding:'2px 8px', borderRadius:4, fontSize:10, cursor:'pointer', border:'1px solid',
                      borderColor: active ? 'var(--blue)' : 'var(--border2)',
                      background:  active ? 'rgba(59,130,246,.15)' : 'transparent',
                      color:       active ? 'var(--blue)' : 'var(--text3)',
                      fontWeight:  active ? 700 : 400,
                    }}>{s}</button>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {hasFilter && (
        <div style={{ marginTop:10, fontSize:11, color:'var(--text3)', borderTop:'1px solid var(--border)', paddingTop:8 }}>
          Active filters:
          {slicer.severity && <span className="badge b-orange" style={{ marginLeft:6 }}>Severity: {slicer.severity}</span>}
          {slicer.months.map(m => <span key={m} className="badge b-blue" style={{ marginLeft:4 }}>{m}</span>)}
          {slicer.stores.map(s => <span key={s} className="badge b-purple" style={{ marginLeft:4 }}>Store {s}</span>)}
        </div>
      )}
    </div>
  )
})
