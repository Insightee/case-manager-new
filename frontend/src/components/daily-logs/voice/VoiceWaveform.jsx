import { useEffect, useRef, useState } from 'react'

const BAR_COUNT = 28

/**
 * Live mic level bars — gives therapists visible feedback that audio is being captured.
 */
const IDLE_LEVELS = Array(BAR_COUNT).fill(0.12)

export function VoiceWaveform({ stream, active, paused = false }) {
  const [levels, setLevels] = useState(IDLE_LEVELS)
  const rafRef = useRef(null)
  const ctxRef = useRef(null)
  const live = Boolean(stream && active)

  useEffect(() => {
    if (!stream || !active) return undefined

    let cancelled = false
    const ctx = new AudioContext()
    // Some browsers start suspended until resumed — without this the bars stay flat.
    ctx.resume().catch(() => {})
    ctxRef.current = ctx
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 128
    analyser.smoothingTimeConstant = 0.72
    const source = ctx.createMediaStreamSource(stream)
    source.connect(analyser)
    const data = new Uint8Array(analyser.frequencyBinCount)

    const tick = () => {
      if (cancelled) return
      analyser.getByteFrequencyData(data)
      const next = []
      const step = Math.max(1, Math.floor(data.length / BAR_COUNT))
      for (let i = 0; i < BAR_COUNT; i += 1) {
        const slice = data.slice(i * step, i * step + step)
        const avg = slice.reduce((sum, v) => sum + v, 0) / slice.length
        const norm = Math.min(1, avg / 140)
        next.push(paused ? 0.14 : 0.12 + norm * 0.88)
      }
      setLevels(next)
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)

    return () => {
      cancelled = true
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      source.disconnect()
      ctx.close().catch(() => {})
      ctxRef.current = null
    }
  }, [stream, active, paused])

  const shownLevels = live ? levels : IDLE_LEVELS

  return (
    <div className="vsl-waveform" aria-hidden="true">
      {shownLevels.map((scale, i) => (
        <span
          key={i}
          className={`vsl-waveform__bar${paused ? ' vsl-waveform__bar--paused' : ''}`}
          style={{ transform: `scaleY(${scale})` }}
        />
      ))}
    </div>
  )
}
