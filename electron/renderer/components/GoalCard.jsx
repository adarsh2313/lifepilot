import React, { useState } from 'react'

const PROGRESS_COLORS = {
  not_started: '#555',
  in_progress: '#7c6af7',
  at_risk: '#e07b39',
  achieved: '#4caf7d',
  dropped: '#555',
}

const PROGRESS_LABELS = {
  not_started: '○',
  in_progress: '●',
  at_risk: '!',
  achieved: '✓',
  dropped: '–',
}

const styles = {
  card: {
    background: '#242424',
    border: '1px solid #2e2e2e',
    borderRadius: 8,
    padding: '10px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  row: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  badge: (progress) => ({
    width: 20,
    height: 20,
    borderRadius: '50%',
    background: PROGRESS_COLORS[progress] + '33',
    color: PROGRESS_COLORS[progress],
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 11,
    fontWeight: 700,
    flexShrink: 0,
  }),
  text: {
    flex: 1,
    fontSize: 13,
    color: '#e8e8e8',
    lineHeight: 1.4,
  },
  editBtn: {
    background: 'none',
    border: 'none',
    color: '#555',
    cursor: 'pointer',
    fontSize: 13,
    padding: '2px 4px',
    borderRadius: 4,
    flexShrink: 0,
  },
  meta: {
    fontSize: 11,
    color: '#555',
    paddingLeft: 28,
  },
  editInput: {
    flex: 1,
    background: '#2e2e2e',
    border: '1px solid #7c6af7',
    borderRadius: 4,
    color: '#e8e8e8',
    fontSize: 13,
    padding: '3px 8px',
    outline: 'none',
  },
  saveBtn: {
    background: '#7c6af7',
    border: 'none',
    borderRadius: 4,
    color: '#fff',
    fontSize: 12,
    padding: '3px 10px',
    cursor: 'pointer',
    flexShrink: 0,
  },
  cancelBtn: {
    background: 'none',
    border: '1px solid #444',
    borderRadius: 4,
    color: '#888',
    fontSize: 12,
    padding: '3px 8px',
    cursor: 'pointer',
    flexShrink: 0,
  },
  progressSelect: {
    background: '#2e2e2e',
    border: '1px solid #3e3e3e',
    borderRadius: 4,
    color: '#888',
    fontSize: 11,
    padding: '2px 4px',
    cursor: 'pointer',
    marginLeft: 'auto',
  },
}

export default function GoalCard({ goal, onUpdate, onProgressChange }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(goal.text)

  function handleSave() {
    if (draft.trim() && draft.trim() !== goal.text) {
      onUpdate(goal.id, draft.trim())
    }
    setEditing(false)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') handleSave()
    if (e.key === 'Escape') { setDraft(goal.text); setEditing(false) }
  }

  const meta = goal.due_date
    ? `due ${goal.due_date}`
    : goal.period
    ? goal.period
    : goal.horizon

  return (
    <div style={styles.card}>
      <div style={styles.row}>
        <div style={styles.badge(goal.progress)} title={goal.progress}>
          {PROGRESS_LABELS[goal.progress] ?? '○'}
        </div>

        {editing ? (
          <>
            <input
              style={styles.editInput}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              autoFocus
            />
            <button style={styles.saveBtn} onClick={handleSave}>Save</button>
            <button style={styles.cancelBtn} onClick={() => { setDraft(goal.text); setEditing(false) }}>✕</button>
          </>
        ) : (
          <>
            <span style={styles.text}>{goal.text}</span>
            <button style={styles.editBtn} onClick={() => setEditing(true)} title="Edit">✏️</button>
          </>
        )}
      </div>

      <div style={{ ...styles.row, paddingLeft: 28 }}>
        <span style={styles.meta}>{meta}</span>
        <select
          style={styles.progressSelect}
          value={goal.progress}
          onChange={(e) => onProgressChange(goal.id, e.target.value)}
        >
          <option value="not_started">Not started</option>
          <option value="in_progress">In progress</option>
          <option value="at_risk">At risk</option>
          <option value="achieved">Achieved</option>
          <option value="dropped">Dropped</option>
        </select>
      </div>
    </div>
  )
}
