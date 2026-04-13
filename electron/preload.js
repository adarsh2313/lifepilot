const { contextBridge } = require('electron')

const BASE = 'http://127.0.0.1:8000'

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${options.method || 'GET'} ${path} → ${res.status}: ${text}`)
  }
  return res.json()
}

contextBridge.exposeInMainWorld('lifepilot', {
  getGoals:       ()           => apiFetch('/goals'),
  createGoal:     (payload)    => apiFetch('/goals', { method: 'POST', body: JSON.stringify(payload) }),
  updateGoal:     (id, text)   => apiFetch(`/goals/${id}`, { method: 'PUT', body: JSON.stringify({ text }) }),
  updateProgress: (id, progress) => apiFetch(`/goals/${id}/progress`, { method: 'PATCH', body: JSON.stringify({ progress }) }),
  health:         ()           => apiFetch('/health'),
})
