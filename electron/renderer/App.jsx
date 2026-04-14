import React, { useState } from 'react'
import Goals from './tabs/Goals.jsx'
import Calendar from './tabs/Calendar.jsx'
import SessionOverlay from './components/SessionOverlay.jsx'

const TABS = ['Goals', 'Calendar', 'Journal']

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    background: '#1a1a1a',
  },
  tabBar: {
    display: 'flex',
    borderBottom: '1px solid #2e2e2e',
    flexShrink: 0,
    paddingTop: 4,
  },
  tab: (active) => ({
    flex: 1,
    padding: '10px 0',
    background: 'none',
    border: 'none',
    borderBottom: active ? '2px solid #7c6af7' : '2px solid transparent',
    color: active ? '#c5beff' : '#888',
    fontSize: 13,
    fontWeight: active ? 600 : 400,
    cursor: 'pointer',
    transition: 'color 0.15s',
  }),
  content: {
    flex: 1,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  placeholder: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    color: '#555',
    fontSize: 13,
  },
  footer: {
    borderTop: '1px solid #2e2e2e',
    padding: '8px 14px',
    flexShrink: 0,
  },
  checkinBtn: {
    width: '100%',
    background: 'none',
    border: '1px solid #3a3270',
    borderRadius: 7,
    color: '#c5beff',
    fontSize: 13,
    fontWeight: 500,
    padding: '8px 0',
    cursor: 'pointer',
  },
}

export default function App() {
  const [activeTab, setActiveTab] = useState('Goals')
  const [sessionOpen, setSessionOpen] = useState(false)

  if (sessionOpen) {
    return <SessionOverlay onClose={() => setSessionOpen(false)} />
  }

  return (
    <div style={styles.container}>
      <div style={styles.tabBar}>
        {TABS.map((tab) => (
          <button key={tab} style={styles.tab(activeTab === tab)} onClick={() => setActiveTab(tab)}>
            {tab}
          </button>
        ))}
      </div>

      <div style={styles.content}>
        {activeTab === 'Goals'    && <Goals />}
        {activeTab === 'Calendar' && <Calendar />}
        {activeTab === 'Journal'  && <div style={styles.placeholder}>Coming soon</div>}
      </div>

      <div style={styles.footer}>
        <button style={styles.checkinBtn} onClick={() => setSessionOpen(true)}>
          Evening Check-in
        </button>
      </div>
    </div>
  )
}
