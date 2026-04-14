import React, { useState, useEffect, useRef } from 'react'

const API_BASE = 'http://127.0.0.1:8000'

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

const s = {
  overlay: {
    position: 'fixed', inset: 0,
    background: '#1a1a1a',
    display: 'flex', flexDirection: 'column',
    zIndex: 100,
  },
  header: {
    display: 'flex', alignItems: 'center',
    padding: '12px 14px 10px',
    borderBottom: '1px solid #2e2e2e',
    flexShrink: 0,
  },
  title: { flex: 1, fontSize: 13, fontWeight: 600, color: '#c5beff', letterSpacing: '0.02em' },
  endBtn: {
    background: 'none', border: '1px solid #3e3e3e', borderRadius: 6,
    color: '#888', fontSize: 12, padding: '5px 12px', cursor: 'pointer',
  },
  messages: {
    flex: 1, overflowY: 'auto', padding: '14px',
    display: 'flex', flexDirection: 'column', gap: 10,
  },
  bubble: (role) => ({
    maxWidth: '85%',
    padding: '9px 12px',
    borderRadius: role === 'assistant' ? '4px 12px 12px 12px' : '12px 4px 12px 12px',
    background: role === 'assistant' ? '#242424' : '#3a3270',
    color: '#e8e8e8', fontSize: 13, lineHeight: 1.5,
    alignSelf: role === 'assistant' ? 'flex-start' : 'flex-end',
    border: role === 'assistant' ? '1px solid #2e2e2e' : 'none',
    whiteSpace: 'pre-wrap',
  }),
  typingIndicator: {
    alignSelf: 'flex-start', padding: '9px 12px',
    borderRadius: '4px 12px 12px 12px',
    background: '#242424', border: '1px solid #2e2e2e',
    color: '#555', fontSize: 13,
  },
  inputRow: {
    display: 'flex', gap: 8,
    padding: '10px 14px',
    borderTop: '1px solid #2e2e2e',
    flexShrink: 0, alignItems: 'flex-end',
  },
  micBtn: (recording, transcribing) => ({
    width: 38, height: 38, borderRadius: '50%',
    border: 'none', cursor: transcribing ? 'default' : 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 17, flexShrink: 0,
    background: recording ? '#c0392b' : '#2e2e2e',
    boxShadow: recording ? '0 0 0 4px rgba(192,57,43,0.3)' : 'none',
    transition: 'background 0.15s, box-shadow 0.15s',
  }),
  input: {
    flex: 1, background: '#242424', border: '1px solid #3e3e3e',
    borderRadius: 8, color: '#e8e8e8', fontSize: 13,
    padding: '9px 12px', outline: 'none',
    resize: 'none', fontFamily: 'inherit', lineHeight: 1.4,
  },
  sendBtn: {
    background: '#7c6af7', border: 'none', borderRadius: 8,
    color: '#fff', fontSize: 13, fontWeight: 600,
    padding: '9px 16px', cursor: 'pointer',
    alignSelf: 'flex-end', flexShrink: 0, height: 38,
  },
  micHint: {
    fontSize: 11, color: '#555', padding: '3px 14px 0',
    flexShrink: 0, height: 16,
  },
  summaryCard: {
    margin: '0 14px', padding: '12px 14px',
    background: '#1e2030', border: '1px solid #3a3270',
    borderRadius: 10, fontSize: 12, color: '#c5beff', lineHeight: 1.6,
  },
  summaryTitle: { fontWeight: 600, marginBottom: 6, fontSize: 13 },
}

export default function SessionOverlay({ onClose }) {
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages]   = useState([])
  const [input, setInput]         = useState('')
  const [loading, setLoading]     = useState(false)
  const [ending, setEnding]       = useState(false)
  const [summary, setSummary]     = useState(null)
  const [error, setError]         = useState('')

  const [recording, setRecording]       = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [micHint, setMicHint]           = useState('')

  const audioContextRef   = useRef(null)
  const processorRef      = useRef(null)
  const streamRef         = useRef(null)
  const pcmBuffersRef     = useRef([])   // float32 chunks from ScriptProcessor
  const bottomRef        = useRef(null)
  const inputRef         = useRef(null)

  // Start coaching session on mount
  useEffect(() => {
    let cancelled = false
    apiFetch('/session/start', { method: 'POST' })
      .then(data => {
        if (cancelled) return
        setSessionId(data.session_id)
        setMessages([{ role: 'assistant', content: data.message }])
      })
      .catch(err => { if (!cancelled) setError(`Failed to start session: ${err.message}`) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // ── Text send ──────────────────────────────────────────────────────────────
  async function handleSend() {
    const text = input.trim()
    if (!text || loading || !sessionId) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setLoading(true)
    try {
      const data = await apiFetch('/session/chat', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId, message: text }),
      })
      setMessages(prev => [...prev, { role: 'assistant', content: data.message }])
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err.message}` }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  // ── WAV encoding helpers ──────────────────────────────────────────────────
  function encodeWav(pcmFloat32Chunks, sampleRate) {
    // Merge all chunks into one flat Float32Array
    const totalLen = pcmFloat32Chunks.reduce((n, c) => n + c.length, 0)
    const merged = new Float32Array(totalLen)
    let offset = 0
    for (const chunk of pcmFloat32Chunks) { merged.set(chunk, offset); offset += chunk.length }

    // Convert float32 → int16
    const int16 = new Int16Array(merged.length)
    for (let i = 0; i < merged.length; i++) {
      const s = Math.max(-1, Math.min(1, merged[i]))
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
    }

    // Build WAV file in an ArrayBuffer
    const dataLen  = int16.byteLength
    const buf      = new ArrayBuffer(44 + dataLen)
    const view     = new DataView(buf)
    const numCh    = 1
    const bitsPerSample = 16

    const writeStr = (off, str) => { for (let i = 0; i < str.length; i++) view.setUint8(off + i, str.charCodeAt(i)) }
    writeStr(0,  'RIFF')
    view.setUint32(4,  36 + dataLen, true)
    writeStr(8,  'WAVE')
    writeStr(12, 'fmt ')
    view.setUint32(16, 16, true)                          // chunk size
    view.setUint16(20, 1,  true)                          // PCM
    view.setUint16(22, numCh, true)
    view.setUint32(24, sampleRate, true)
    view.setUint32(28, sampleRate * numCh * bitsPerSample / 8, true)
    view.setUint16(32, numCh * bitsPerSample / 8, true)
    view.setUint16(34, bitsPerSample, true)
    writeStr(36, 'data')
    view.setUint32(40, dataLen, true)

    const out = new Uint8Array(buf)
    out.set(new Uint8Array(int16.buffer), 44)
    return buf
  }

  // ── Mic: AudioContext PCM capture → WAV → POST /transcribe ───────────────
  async function handleMicClick() {
    if (transcribing) return

    if (recording) {
      // Stop — finalise and transcribe
      processorRef.current?.disconnect()
      processorRef.current = null
      streamRef.current?.getTracks().forEach(t => t.stop())
      streamRef.current = null

      const sampleRate = audioContextRef.current?.sampleRate || 16000
      audioContextRef.current?.close()
      audioContextRef.current = null

      setRecording(false)
      setTranscribing(true)
      setMicHint('Transcribing…')

      const chunks = pcmBuffersRef.current
      pcmBuffersRef.current = []
      console.log('[STT] PCM chunks:', chunks.length, 'sampleRate:', sampleRate)

      if (chunks.length === 0) {
        setMicHint('No audio captured — try again')
        setTranscribing(false)
        return
      }

      try {
        const wavBuf = encodeWav(chunks, sampleRate)
        // btoa(String.fromCharCode(...largeArray)) blows the call stack — chunk it
        const bytes = new Uint8Array(wavBuf)
        let binary = ''
        for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
        const b64 = btoa(binary)
        console.log('[STT] WAV size:', wavBuf.byteLength, 'bytes')

        const data = await apiFetch('/transcribe', {
          method: 'POST',
          body: JSON.stringify({ audio_b64: b64, mime_type: 'audio/wav' }),
        })
        console.log('[STT] result:', data)

        if (data.text?.trim()) {
          setInput(data.text.trim())
          setMicHint('')
          setTimeout(() => inputRef.current?.focus(), 50)
        } else {
          setMicHint('Nothing detected — try again')
        }
      } catch (err) {
        setMicHint(`Transcription failed: ${err.message}`)
      } finally {
        setTranscribing(false)
      }
      return
    }

    // Start recording
    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
    } catch (err) {
      setMicHint(`Mic access denied: ${err.message}`)
      return
    }

    const ctx = new AudioContext()
    const source = ctx.createMediaStreamSource(stream)

    // ScriptProcessor captures raw float32 PCM at the AudioContext sample rate
    const processor = ctx.createScriptProcessor(4096, 1, 1)
    pcmBuffersRef.current = []

    processor.onaudioprocess = (e) => {
      const channelData = e.inputBuffer.getChannelData(0)
      pcmBuffersRef.current.push(new Float32Array(channelData))
    }

    source.connect(processor)
    processor.connect(ctx.destination)

    audioContextRef.current = ctx
    processorRef.current    = processor
    streamRef.current       = stream

    setRecording(true)
    setMicHint('Recording… click ⏹ to stop')
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      processorRef.current?.disconnect()
      streamRef.current?.getTracks().forEach(t => t.stop())
      audioContextRef.current?.close()
    }
  }, [])

  // ── End session ────────────────────────────────────────────────────────────
  async function handleEnd() {
    if (!sessionId || ending) return
    setEnding(true)
    try {
      const data = await apiFetch('/session/end', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId }),
      })
      setSummary(data.summary)
    } catch (err) {
      setError(`Failed to save session: ${err.message}`)
      setEnding(false)
    }
  }

  // ── Summary screen ─────────────────────────────────────────────────────────
  if (summary) {
    return (
      <div style={s.overlay}>
        <div style={s.header}>
          <span style={s.title}>Session saved</span>
          <button style={s.endBtn} onClick={onClose}>Close</button>
        </div>
        <div style={s.messages}>
          <div style={s.summaryCard}>
            <div style={s.summaryTitle}>{summary.one_line_summary}</div>
            {summary.wins?.length > 0 && (
              <><div style={{ color: '#4caf7d', marginTop: 8, fontWeight: 600 }}>Wins</div>
              {summary.wins.map((w, i) => <div key={i}>• {w}</div>)}</>
            )}
            {summary.blockers?.length > 0 && (
              <><div style={{ color: '#e07b39', marginTop: 8, fontWeight: 600 }}>Blockers</div>
              {summary.blockers.map((b, i) => <div key={i}>• {b}</div>)}</>
            )}
            {summary.open_threads?.length > 0 && (
              <><div style={{ color: '#888', marginTop: 8, fontWeight: 600 }}>Follow-ups</div>
              {summary.open_threads.map((t, i) => (
                <div key={i}>☐ {typeof t === 'object' ? t.text : t}</div>
              ))}</>
            )}
            <div style={{ color: '#555', marginTop: 10, fontSize: 11 }}>
              Journal saved · {new Date().toISOString().slice(0, 10)}
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ── Chat screen ────────────────────────────────────────────────────────────
  return (
    <div style={s.overlay}>
      <div style={s.header}>
        <span style={s.title}>Evening Check-in</span>
        {sessionId && (
          <button style={s.endBtn} onClick={handleEnd} disabled={ending}>
            {ending ? 'Saving…' : 'End Session'}
          </button>
        )}
      </div>

      <div style={s.messages}>
        {error && <div style={{ color: '#e07b39', fontSize: 12 }}>{error}</div>}
        {messages.map((msg, i) => (
          <div key={i} style={s.bubble(msg.role)}>{msg.content}</div>
        ))}
        {loading && <div style={s.typingIndicator}>...</div>}
        <div ref={bottomRef} />
      </div>

      {micHint && <div style={s.micHint}>{micHint}</div>}

      <div style={s.inputRow}>
        <button
          style={s.micBtn(recording, transcribing)}
          onClick={handleMicClick}
          disabled={transcribing || loading || ending || !sessionId}
          title={recording ? 'Stop recording' : 'Start recording'}
        >
          {transcribing ? '⏳' : recording ? '⏹' : '🎤'}
        </button>

        <textarea
          ref={inputRef}
          style={s.input}
          rows={2}
          placeholder={recording ? 'Recording…' : transcribing ? 'Transcribing…' : 'Speak or type…'}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading || ending || !sessionId || recording || transcribing}
        />

        <button
          style={s.sendBtn}
          onClick={handleSend}
          disabled={loading || !input.trim() || !sessionId || ending || recording}
        >
          Send
        </button>
      </div>
    </div>
  )
}
