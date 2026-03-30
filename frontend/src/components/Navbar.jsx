import React from 'react';

export default function Navbar({ activeView, setActiveView, status }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '' },
    { id: 'pipeline', label: 'Pipeline', icon: '' },
    { id: 'analytics', label: 'Analytics', icon: '' },
    { id: 'feature-extraction', label: 'How Features Work', icon: '' },
    { id: 'xai', label: 'XAI', icon: '' },
    { id: 'logbook', label: 'Logbook', icon: '' },
  ];

  return (
    <nav style={{
      background: '#ffffff',
      borderBottom: '1px solid #e2e8f0',
      padding: '0 24px',
      height: '64px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      position: 'sticky',
      top: 0,
      zIndex: 1000,
      boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
    }}>
      {/* Logo & Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{
          background: '#3b82f6',
          borderRadius: 8,
          padding: '8px 16px',
          fontWeight: 700,
          fontSize: 18,
          color: '#fff'
        }}>
          ForecastAI
        </div>
        <div style={{ color: '#64748b', fontSize: 14 }}>
          Real-Time Demand Forecasting Platform
        </div>
      </div>

      {/* Navigation Items */}
      <div style={{ display: 'flex', gap: 8 }}>
        {navItems.map(item => (
          <button
            key={item.id}
            onClick={() => setActiveView(item.id)}
            style={{
              background: activeView === item.id 
                ? '#3b82f6' 
                : 'transparent',
              border: activeView === item.id ? 'none' : '1px solid #e2e8f0',
              color: activeView === item.id ? '#fff' : '#64748b',
              padding: '8px 16px',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
            onMouseEnter={(e) => {
              if (activeView !== item.id) {
                e.target.style.background = '#f1f5f9';
                e.target.style.color = '#1e293b';
              }
            }}
            onMouseLeave={(e) => {
              if (activeView !== item.id) {
                e.target.style.background = 'transparent';
                e.target.style.color = '#64748b';
              }
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      {/* Status Indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: 8,
          padding: '6px 12px'
        }}>
          <div style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: status?.files?.model ? '#10b981' : '#ef4444'
          }} />
          <span style={{ color: '#64748b', fontSize: 12 }}>
            {status?.files?.model ? 'Model Ready' : 'No Model'}
          </span>
        </div>
        
        {status?.model?.type && (
          <div style={{
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: 8,
            padding: '6px 12px',
            fontSize: 12,
            color: '#3b82f6'
          }}>
            {status.model.type} ({status.model.trees} trees)
          </div>
        )}
      </div>
    </nav>
  );
}