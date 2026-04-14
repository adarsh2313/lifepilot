import React, { useEffect, useState, useCallback, useMemo } from 'react'
import GoalCard from '../components/GoalCard.jsx'

const API_BASE = 'http://127.0.0.1:8000'

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${options.method || 'GET'} ${path} -> ${res.status}: ${text}`)
  }
  return res.json()
}

function getApi() {
  if (window.lifepilot) return window.lifepilot
  return {
    getGoals: () => apiFetch('/goals'),
    createGoal: (payload) => apiFetch('/goals', { method: 'POST', body: JSON.stringify(payload) }),
    updateGoal: (id, text) => apiFetch(`/goals/${id}`, { method: 'PUT', body: JSON.stringify({ text }) }),
    updateProgress: (id, progress) => apiFetch(`/goals/${id}/progress`, { method: 'PATCH', body: JSON.stringify({ progress }) }),
    getThreads: (goalId) => apiFetch(`/goals/${goalId}/threads`),
    addThread: (goalId, text) => apiFetch(`/goals/${goalId}/threads`, { method: 'POST', body: JSON.stringify({ text }) }),
    resolveThread: (goalId, threadId) => apiFetch(`/goals/${goalId}/threads/${threadId}/resolve`, { method: 'PATCH' }),
  }
}

const HORIZONS = [
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'custom', label: 'Custom' },
]

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    overflow: 'hidden',
  },
  scroll: {
    flex: 1,
    overflowY: 'auto',
    padding: '12px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: '#666',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  addRow: {
    borderTop: '1px solid #2e2e2e',
    padding: '10px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    flexShrink: 0,
  },
  addToggle: {
    background: 'none',
    border: '1px dashed #3e3e3e',
    borderRadius: 6,
    color: '#666',
    fontSize: 13,
    padding: '8px 12px',
    cursor: 'pointer',
    textAlign: 'left',
    transition: 'border-color 0.15s, color 0.15s',
  },
  addForm: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  input: {
    background: '#242424',
    border: '1px solid #3e3e3e',
    borderRadius: 6,
    color: '#e8e8e8',
    fontSize: 13,
    padding: '8px 10px',
    outline: 'none',
    width: '100%',
  },
  formRow: {
    display: 'flex',
    gap: 8,
  },
  select: {
    background: '#242424',
    border: '1px solid #3e3e3e',
    borderRadius: 6,
    color: '#e8e8e8',
    fontSize: 13,
    padding: '7px 8px',
    flex: 1,
    outline: 'none',
  },
  dateInput: {
    background: '#242424',
    border: '1px solid #3e3e3e',
    borderRadius: 6,
    color: '#e8e8e8',
    fontSize: 13,
    padding: '7px 8px',
    flex: 1,
    outline: 'none',
  },
  submitBtn: {
    background: '#7c6af7',
    border: 'none',
    borderRadius: 6,
    color: '#fff',
    fontSize: 13,
    fontWeight: 600,
    padding: '8px 16px',
    cursor: 'pointer',
    width: '100%',
  },
  error: {
    fontSize: 12,
    color: '#e07b39',
    padding: '4px 0',
  },
  empty: {
    fontSize: 12,
    color: '#444',
    fontStyle: 'italic',
    padding: '4px 0',
  },
  backendDown: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    gap: 8,
    color: '#555',
    fontSize: 13,
  },
  retryBtn: {
    background: 'none',
    border: '1px solid #444',
    borderRadius: 6,
    color: '#888',
    fontSize: 12,
    padding: '6px 14px',
    cursor: 'pointer',
    marginTop: 4,
  },
}

export default function Goals() {
  const api = useMemo(() => getApi(), [])
  const [goals, setGoals] = useState([])
  const [threads, setThreads] = useState({}) // { [goalId]: Thread[] }
  const [loading, setLoading] = useState(true)
  const [backendDown, setBackendDown] = useState(false)
  const [backendError, setBackendError] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [newText, setNewText] = useState('')
  const [newHorizon, setNewHorizon] = useState('weekly')
  const [newDueDate, setNewDueDate] = useState('')
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  const loadThreadsForGoals = useCallback(async (goalList) => {
    const entries = await Promise.all(
      goalList.map(async (g) => {
        try {
          const data = await api.getThreads(g.id)
          return [g.id, data]
        } catch {
          return [g.id, []]
        }
      })
    )
    setThreads(Object.fromEntries(entries))
  }, [api])

  const loadGoals = useCallback(async () => {
    try {
      const data = await api.getGoals()
      setGoals(data)
      setBackendDown(false)
      setBackendError('')
      await loadThreadsForGoals(data)
    } catch (err) {
      setBackendDown(true)
      setBackendError(err?.message || 'Could not connect to backend')
    } finally {
      setLoading(false)
    }
  }, [api, loadThreadsForGoals])

  useEffect(() => { loadGoals() }, [loadGoals])
  useEffect(() => {
    if (!backendDown) return
    const id = setInterval(() => { loadGoals() }, 3000)
    return () => clearInterval(id)
  }, [backendDown, loadGoals])

  async function handleCreate(e) {
    e.preventDefault()
    setFormError('')
    if (!newText.trim()) { setFormError('Goal text is required'); return }
    if (newHorizon === 'custom' && !newDueDate) { setFormError('Due date required for custom goals'); return }

    setSaving(true)
    try {
      await api.createGoal({
        text: newText.trim(),
        horizon: newHorizon,
        due_date: newHorizon === 'custom' ? newDueDate : null,
      })
      setNewText('')
      setNewDueDate('')
      setNewHorizon('weekly')
      setShowAdd(false)
      await loadGoals()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleUpdate(id, text) {
    try {
      await api.updateGoal(id, text)
      await loadGoals()
    } catch (err) {
      console.error('Update failed:', err)
    }
  }

  async function handleProgress(id, progress) {
    try {
      await api.updateProgress(id, progress)
      if (progress === 'dropped') {
        // Goal is now inactive — remove from list
        setGoals((prev) => prev.filter((g) => g.id !== id))
      } else {
        setGoals((prev) => prev.map((g) => g.id === id ? { ...g, progress } : g))
      }
    } catch (err) {
      console.error('Progress update failed:', err)
    }
  }

  async function handleAddThread(goalId, text) {
    try {
      const thread = await api.addThread(goalId, text)
      setThreads((prev) => ({
        ...prev,
        [goalId]: [thread, ...(prev[goalId] || [])],
      }))
    } catch (err) {
      console.error('Add thread failed:', err)
    }
  }

  async function handleResolveThread(goalId, threadId) {
    try {
      const updated = await api.resolveThread(goalId, threadId)
      setThreads((prev) => ({
        ...prev,
        [goalId]: (prev[goalId] || []).map((t) => t.id === threadId ? updated : t),
      }))
    } catch (err) {
      console.error('Resolve thread failed:', err)
    }
  }

  if (loading) return <div style={{ ...styles.backendDown }}><span>Loading...</span></div>

  if (backendDown) return (
    <div style={styles.backendDown}>
      <span>Backend not running</span>
      <span style={{ fontSize: 11, color: '#444' }}>uvicorn backend.main:app --port 8000</span>
      <span style={{ fontSize: 11, color: '#444', textAlign: 'center', maxWidth: 300 }}>
        Auto-retrying every 3s. {backendError}
      </span>
      <button style={styles.retryBtn} onClick={loadGoals}>Retry</button>
    </div>
  )

  const weekly = goals.filter((g) => g.horizon === 'weekly')
  const monthly = goals.filter((g) => g.horizon === 'monthly')
  const custom = goals.filter((g) => g.horizon === 'custom')

  return (
    <div style={styles.container}>
      <div style={styles.scroll}>
        {weekly.length > 0 && (
          <div style={styles.section}>
            <span style={styles.sectionLabel}>Weekly</span>
            {weekly.map((g) => (
              <GoalCard key={g.id} goal={g} threads={threads[g.id] || []}
                onUpdate={handleUpdate} onProgressChange={handleProgress}
                onAddThread={handleAddThread} onResolveThread={handleResolveThread} />
            ))}
          </div>
        )}

        {monthly.length > 0 && (
          <div style={styles.section}>
            <span style={styles.sectionLabel}>Monthly</span>
            {monthly.map((g) => (
              <GoalCard key={g.id} goal={g} threads={threads[g.id] || []}
                onUpdate={handleUpdate} onProgressChange={handleProgress}
                onAddThread={handleAddThread} onResolveThread={handleResolveThread} />
            ))}
          </div>
        )}

        {custom.length > 0 && (
          <div style={styles.section}>
            <span style={styles.sectionLabel}>Custom</span>
            {custom.map((g) => (
              <GoalCard key={g.id} goal={g} threads={threads[g.id] || []}
                onUpdate={handleUpdate} onProgressChange={handleProgress}
                onAddThread={handleAddThread} onResolveThread={handleResolveThread} />
            ))}
          </div>
        )}

        {goals.length === 0 && (
          <div style={styles.empty}>No goals yet — add one below.</div>
        )}
      </div>

      <div style={styles.addRow}>
        {!showAdd ? (
          <button style={styles.addToggle} onClick={() => setShowAdd(true)}>
            + Add goal
          </button>
        ) : (
          <form style={styles.addForm} onSubmit={handleCreate}>
            <input
              style={styles.input}
              placeholder="What do you want to achieve?"
              value={newText}
              onChange={(e) => setNewText(e.target.value)}
              autoFocus
            />
            <div style={styles.formRow}>
              <select style={styles.select} value={newHorizon} onChange={(e) => setNewHorizon(e.target.value)}>
                {HORIZONS.map((h) => (
                  <option key={h.value} value={h.value}>{h.label}</option>
                ))}
              </select>
              {newHorizon === 'custom' && (
                <input
                  type="date"
                  style={styles.dateInput}
                  value={newDueDate}
                  onChange={(e) => setNewDueDate(e.target.value)}
                />
              )}
            </div>
            {formError && <div style={styles.error}>{formError}</div>}
            <div style={styles.formRow}>
              <button type="submit" style={styles.submitBtn} disabled={saving}>
                {saving ? 'Saving…' : 'Add goal'}
              </button>
              <button
                type="button"
                style={{ ...styles.submitBtn, background: 'none', border: '1px solid #444', color: '#888', flex: '0 0 auto', width: 'auto', padding: '8px 14px' }}
                onClick={() => { setShowAdd(false); setFormError('') }}
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
