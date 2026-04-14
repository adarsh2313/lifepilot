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

const s = {
  card: {
    background: '#242424',
    border: '1px solid #2e2e2e',
    borderRadius: 8,
    overflow: 'hidden',
  },
  main: {
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
    background: (PROGRESS_COLORS[progress] ?? '#555') + '33',
    color: PROGRESS_COLORS[progress] ?? '#555',
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
  // Threads section
  threadsToggle: {
    width: '100%',
    background: 'none',
    border: 'none',
    borderTop: '1px solid #2a2a2a',
    color: '#555',
    fontSize: 11,
    padding: '5px 12px',
    cursor: 'pointer',
    textAlign: 'left',
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  threadsPanel: {
    borderTop: '1px solid #2a2a2a',
    padding: '8px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  threadItem: (resolved) => ({
    display: 'flex',
    alignItems: 'flex-start',
    gap: 7,
    opacity: resolved ? 0.45 : 1,
  }),
  threadCheck: {
    width: 14,
    height: 14,
    borderRadius: 3,
    border: '1px solid #444',
    background: 'none',
    cursor: 'pointer',
    flexShrink: 0,
    marginTop: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 10,
    color: '#4caf7d',
  },
  threadText: (resolved) => ({
    fontSize: 12,
    color: resolved ? '#555' : '#bbb',
    lineHeight: 1.4,
    flex: 1,
    textDecoration: resolved ? 'line-through' : 'none',
  }),
  addThreadRow: {
    display: 'flex',
    gap: 6,
    marginTop: 2,
  },
  addThreadInput: {
    flex: 1,
    background: '#1e1e1e',
    border: '1px solid #3e3e3e',
    borderRadius: 4,
    color: '#e8e8e8',
    fontSize: 12,
    padding: '4px 8px',
    outline: 'none',
  },
  addThreadBtn: {
    background: 'none',
    border: '1px solid #444',
    borderRadius: 4,
    color: '#888',
    fontSize: 11,
    padding: '4px 8px',
    cursor: 'pointer',
    flexShrink: 0,
  },
  showAllBtn: {
    background: 'none',
    border: 'none',
    color: '#555',
    fontSize: 11,
    cursor: 'pointer',
    padding: '2px 0',
    textAlign: 'left',
  },
}

export default function GoalCard({ goal, threads = [], onUpdate, onProgressChange, onAddThread, onResolveThread }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(goal.text)
  const [threadsOpen, setThreadsOpen] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [newThread, setNewThread] = useState('')
  const [addingThread, setAddingThread] = useState(false)

  function handleSave() {
    if (draft.trim() && draft.trim() !== goal.text) onUpdate(goal.id, draft.trim())
    setEditing(false)
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') handleSave()
    if (e.key === 'Escape') { setDraft(goal.text); setEditing(false) }
  }

  async function handleAddThread(e) {
    e.preventDefault()
    if (!newThread.trim()) return
    await onAddThread(goal.id, newThread.trim())
    setNewThread('')
    setAddingThread(false)
  }

  const meta = goal.due_date ? `due ${goal.due_date}` : goal.period ?? goal.horizon

  // Split threads into open and resolved
  const open = threads.filter(t => !t.resolved)
  const resolved = threads.filter(t => t.resolved)

  // Show last 5 resolved unless showAll
  const visibleResolved = showAll ? resolved : resolved.slice(0, 5)
  const hasMore = resolved.length > 5 && !showAll
  const totalCount = open.length + resolved.length

  return (
    <div style={s.card}>
      <div style={s.main}>
        <div style={s.row}>
          <div style={s.badge(goal.progress)} title={goal.progress}>
            {PROGRESS_LABELS[goal.progress] ?? '○'}
          </div>

          {editing ? (
            <>
              <input
                style={s.editInput}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={handleKeyDown}
                autoFocus
              />
              <button style={s.saveBtn} onClick={handleSave}>Save</button>
              <button style={s.cancelBtn} onClick={() => { setDraft(goal.text); setEditing(false) }}>✕</button>
            </>
          ) : (
            <>
              <span style={s.text}>{goal.text}</span>
              <button style={s.editBtn} onClick={() => setEditing(true)} title="Edit">✏️</button>
            </>
          )}
        </div>

        <div style={{ ...s.row, paddingLeft: 28 }}>
          <span style={s.meta}>{meta}</span>
          <select
            style={s.progressSelect}
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

      {/* Threads toggle */}
      <button style={s.threadsToggle} onClick={() => setThreadsOpen(o => !o)}>
        <span>{threadsOpen ? '▾' : '▸'}</span>
        <span>
          {totalCount === 0
            ? 'No follow-ups'
            : `${open.length} open · ${resolved.length} done`}
        </span>
      </button>

      {threadsOpen && (
        <div style={s.threadsPanel}>
          {/* Open threads */}
          {open.map(t => (
            <div key={t.id} style={s.threadItem(false)}>
              <button
                style={s.threadCheck}
                onClick={() => onResolveThread(goal.id, t.id)}
                title="Mark done"
              >
                {' '}
              </button>
              <span style={s.threadText(false)}>{t.text}</span>
            </div>
          ))}

          {/* Resolved threads */}
          {visibleResolved.map(t => (
            <div key={t.id} style={s.threadItem(true)}>
              <div style={{ ...s.threadCheck, cursor: 'default', borderColor: '#333' }}>✓</div>
              <span style={s.threadText(true)}>{t.text}</span>
            </div>
          ))}

          {hasMore && (
            <button style={s.showAllBtn} onClick={() => setShowAll(true)}>
              + {resolved.length - 5} more resolved
            </button>
          )}

          {/* Add thread */}
          {addingThread ? (
            <form style={s.addThreadRow} onSubmit={handleAddThread}>
              <input
                style={s.addThreadInput}
                placeholder="Add a follow-up..."
                value={newThread}
                onChange={e => setNewThread(e.target.value)}
                autoFocus
              />
              <button type="submit" style={s.addThreadBtn}>Add</button>
              <button type="button" style={s.addThreadBtn} onClick={() => { setAddingThread(false); setNewThread('') }}>✕</button>
            </form>
          ) : (
            <button style={s.showAllBtn} onClick={() => setAddingThread(true)}>+ add follow-up</button>
          )}
        </div>
      )}
    </div>
  )
}
