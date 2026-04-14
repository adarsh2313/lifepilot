import React, { useState, useEffect, useCallback } from 'react'
import ConfirmCard from '../components/ConfirmCard.jsx'

const API_BASE = 'http://127.0.0.1:8000'
const REQUEST_TIMEOUT_MS = 10000

async function apiFetch(path, options = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    signal: controller.signal,
    ...options,
  }).finally(() => clearTimeout(timer))
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s = {
  root: {
    flex: 1, display: 'flex', flexDirection: 'column',
    overflowY: 'auto', padding: '12px 14px', gap: 8,
  },
  weekNav: {
    display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0, marginBottom: 2,
  },
  weekNavBtn: {
    background: 'none', border: '1px solid #2e2e2e', borderRadius: 6,
    color: '#666', fontSize: 11, padding: '3px 8px', cursor: 'pointer',
  },
  weekLabel: {
    flex: 1, fontSize: 11, color: '#555', textAlign: 'center',
  },
  dayTabs: {
    display: 'flex', gap: 4, flexShrink: 0, overflowX: 'auto',
    paddingBottom: 2,
  },
  dayTab: (active) => ({
    flexShrink: 0,
    padding: '5px 10px', borderRadius: 7,
    background: active ? '#3a3270' : 'none',
    border: active ? '1px solid #7c6af7' : '1px solid #2e2e2e',
    color: active ? '#c5beff' : '#666',
    fontSize: 11, cursor: 'pointer',
    textAlign: 'center', minWidth: 44,
  }),
  dayTabDay: { fontWeight: 600, fontSize: 12 },
  dayTabName: { fontSize: 10, marginTop: 1, color: 'inherit', opacity: 0.7 },
  eventRow: {
    display: 'flex', alignItems: 'flex-start', gap: 10,
    padding: '8px 10px', borderRadius: 8,
    background: '#242424', border: '1px solid #2e2e2e',
  },
  timeCol: {
    flexShrink: 0, width: 68, fontSize: 11, color: '#666',
    paddingTop: 1, lineHeight: 1.5,
  },
  titleCol: {
    flex: 1, fontSize: 13, color: '#e8e8e8', lineHeight: 1.4,
  },
  calBadge: {
    fontSize: 10, color: '#666', marginTop: 2,
  },
  freeRow: {
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '4px 10px',
    borderLeft: '2px solid #2a2a2a', marginLeft: 2,
  },
  freeTime: {
    flexShrink: 0, width: 68, fontSize: 10, color: '#333',
  },
  freeLabel: { fontSize: 10, color: '#333' },
  error:   { fontSize: 12, color: '#e07b39', padding: '6px 0' },
  empty:   { fontSize: 13, color: '#555', textAlign: 'center', paddingTop: 24 },
  loading: { fontSize: 12, color: '#555', padding: '6px 0' },
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function addDays(dateStr, n) {
  const d = new Date(dateStr + 'T12:00:00')
  d.setDate(d.getDate() + n)
  return toLocalIsoDate(d)
}

function startOfWeek(dateStr) {
  const d = new Date(dateStr + 'T12:00:00')
  const day = d.getDay() // 0=Sun
  d.setDate(d.getDate() - day)
  return toLocalIsoDate(d)
}

function toLocalIsoDate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function getWeekDays(weekStart) {
  return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i))
}

function formatTime(isoStr) {
  const d = new Date(isoStr)
  const h = d.getHours(), m = d.getMinutes().toString().padStart(2, '0')
  const ampm = h >= 12 ? 'pm' : 'am'
  return `${h % 12 || 12}:${m}${ampm}`
}

function formatDuration(min) {
  if (min < 60) return `${min}m`
  const h = Math.floor(min / 60), m = min % 60
  return m ? `${h}h ${m}m` : `${h}h`
}

function shortDayName(dateStr) {
  return new Date(dateStr + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short' })
}

function dayNum(dateStr) {
  return new Date(dateStr + 'T12:00:00').getDate()
}

function friendlyDate(dateStr) {
  return new Date(dateStr + 'T12:00:00').toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric',
  })
}

function weekRangeLabel(weekStart) {
  const end = addDays(weekStart, 6)
  const s = new Date(weekStart + 'T12:00:00')
  const e = new Date(end + 'T12:00:00')
  const mo = s.toLocaleDateString('en-US', { month: 'short' })
  const mo2 = e.toLocaleDateString('en-US', { month: 'short' })
  return mo === mo2
    ? `${mo} ${s.getDate()}–${e.getDate()}`
    : `${mo} ${s.getDate()} – ${mo2} ${e.getDate()}`
}

function buildTimeline(schedule) {
  const all = [
    ...schedule.events.map(e => ({ type: 'event', ...e })),
    ...schedule.free_blocks.map(f => ({ type: 'free', ...f })),
  ]
  all.sort((a, b) => a.start.localeCompare(b.start))
  return all
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function Calendar() {
  const today = toLocalIsoDate(new Date())

  const [weekStart,    setWeekStart]    = useState(() => startOfWeek(today))
  const [selectedDate, setSelectedDate] = useState(today)
  const [schedulesByDate, setSchedulesByDate] = useState({})
  const [dateErrors, setDateErrors] = useState({})
  const [loading,      setLoading]      = useState(false)
  const [error,        setError]        = useState('')
  const [pendingAction, setPendingAction] = useState(null)
  const [actionStatus,  setActionStatus]  = useState('')

  const loadDate = useCallback(async (dateStr, force = false) => {
    if (schedulesByDate[dateStr] && !force) return
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(`/calendar/date/${dateStr}`)
      setSchedulesByDate((prev) => ({ ...prev, [dateStr]: data }))
      setDateErrors((prev) => ({ ...prev, [dateStr]: '' }))
    } catch (err) {
      const msg = err?.message || 'Unknown error'
      setDateErrors((prev) => ({ ...prev, [dateStr]: msg }))
      setError(`Could not load calendar: ${msg}`)
    } finally {
      setLoading(false)
    }
  }, [schedulesByDate])

  useEffect(() => { loadDate(selectedDate) }, [selectedDate, loadDate])

  function prevWeek() {
    const ws = addDays(weekStart, -7)
    setWeekStart(ws)
    setSelectedDate(ws)
    setError('')
  }
  function nextWeek() {
    const ws = addDays(weekStart, 7)
    setWeekStart(ws)
    setSelectedDate(ws)
    setError('')
  }

  function pickDate(dateStr) {
    setSelectedDate(dateStr)
    const dayErr = dateErrors[dateStr]
    setError(dayErr ? `Could not load calendar: ${dayErr}` : '')
  }

  async function handleConfirm(action) {
    setPendingAction(null)
    setActionStatus('Applying…')
    try {
      await apiFetch('/calendar/action', { method: 'POST', body: JSON.stringify(action) })
      setActionStatus('Done!')
      await loadDate(selectedDate, true)
    } catch (err) {
      setActionStatus(`Failed: ${err.message}`)
    }
    setTimeout(() => setActionStatus(''), 3000)
  }

  const weekDays = getWeekDays(weekStart)
  const schedule = schedulesByDate[selectedDate] || null
  const timeline = schedule ? buildTimeline(schedule) : []

  return (
    <div style={s.root}>
      {/* Week navigator */}
      <div style={s.weekNav}>
        <button style={s.weekNavBtn} onClick={prevWeek}>‹</button>
        <span style={s.weekLabel}>{weekRangeLabel(weekStart)}</span>
        <button style={s.weekNavBtn} onClick={nextWeek}>›</button>
      </div>

      {/* Day tabs */}
      <div style={s.dayTabs}>
        {weekDays.map(d => (
          <button
            key={d}
            style={s.dayTab(d === selectedDate)}
            onClick={() => pickDate(d)}
          >
            <div style={s.dayTabDay}>{dayNum(d)}</div>
            <div style={s.dayTabName}>{shortDayName(d)}</div>
          </button>
        ))}
      </div>

      {/* Confirm card */}
      {pendingAction && (
        <ConfirmCard
          description={pendingAction.description}
          action={pendingAction.action}
          onConfirm={handleConfirm}
          onCancel={() => setPendingAction(null)}
        />
      )}

      {actionStatus && <div style={s.loading}>{actionStatus}</div>}
      {error        && <div style={s.error}>{error}</div>}
      {loading      && <div style={s.loading}>Loading…</div>}

      {/* Timeline */}
      {!loading && schedule && timeline.length === 0 && (
        <div style={s.empty}>No events — open day</div>
      )}

      {!loading && schedule && timeline.map((item, i) => {
        if (item.type === 'event') {
          return (
            <div key={item.uid || i} style={s.eventRow}>
              <div style={s.timeCol}>
                {item.all_day
                  ? <span style={{ color: '#555' }}>All day</span>
                  : <>{formatTime(item.start)}<br /><span style={{ color: '#444' }}>{formatTime(item.end)}</span></>
                }
              </div>
              <div style={s.titleCol}>
                {item.title}
                <div style={s.calBadge}>{item.calendar} · {formatDuration(item.duration_min)}</div>
              </div>
            </div>
          )
        }
        return (
          <div key={`free-${i}`} style={s.freeRow}>
            <div style={s.freeTime}>{formatTime(item.start)}</div>
            <div style={s.freeLabel}>── free {formatDuration(item.duration_min)} ──</div>
          </div>
        )
      })}
    </div>
  )
}
