import React from 'react'

const s = {
  card: {
    background: '#1e2030',
    border: '1px solid #3a3270',
    borderRadius: 10,
    padding: '12px 14px',
    margin: '8px 0',
    fontSize: 13,
    color: '#c5beff',
  },
  label: {
    fontWeight: 600,
    marginBottom: 10,
    color: '#e8e8e8',
    lineHeight: 1.4,
  },
  btnRow: {
    display: 'flex',
    gap: 8,
    marginTop: 10,
  },
  confirmBtn: {
    flex: 1,
    background: '#7c6af7',
    border: 'none',
    borderRadius: 7,
    color: '#fff',
    fontSize: 12,
    fontWeight: 600,
    padding: '7px 0',
    cursor: 'pointer',
  },
  cancelBtn: {
    flex: 1,
    background: 'none',
    border: '1px solid #3e3e3e',
    borderRadius: 7,
    color: '#888',
    fontSize: 12,
    padding: '7px 0',
    cursor: 'pointer',
  },
}

/**
 * ConfirmCard — shows a proposed calendar action and two buttons.
 *
 * Props:
 *   description  string   — human-readable summary of what will happen
 *   action       object   — CalendarAction payload to POST on confirm
 *   onConfirm(action)     — called when user clicks Confirm
 *   onCancel()            — called when user clicks Cancel
 */
export default function ConfirmCard({ description, action, onConfirm, onCancel }) {
  return (
    <div style={s.card}>
      <div style={s.label}>{description}</div>
      <div style={s.btnRow}>
        <button style={s.confirmBtn} onClick={() => onConfirm(action)}>Confirm</button>
        <button style={s.cancelBtn}  onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}
