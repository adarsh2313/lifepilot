import React, { useState } from 'react'
import Goals from './tabs/Goals.jsx'

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
}

export default function App() {
  const [activeTab, setActiveTab] = useState('Goals')

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
        {activeTab === 'Goals' && <Goals />}
        {activeTab === 'Calendar' && <div style={styles.placeholder}>Coming soon</div>}
        {activeTab === 'Journal' && <div style={styles.placeholder}>Coming soon</div>}
      </div>
    </div>
  )
}
