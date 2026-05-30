import { useEffect, useRef, useState } from 'react'

export function CopyLinkButton({
  url,
  label = 'Copy link',
  copiedLabel = 'Copied',
  className = 'admin-btn admin-btn--ghost admin-btn--sm',
  disabled = false,
}) {
  const [state, setState] = useState('idle')
  const timerRef = useRef(null)

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current)
  }, [])

  async function handleCopy() {
    if (!url || disabled) return
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('Clipboard not available')
      }
      await navigator.clipboard.writeText(url)
      setState('copied')
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setState('idle'), 2000)
    } catch (err) {
      setState('error')
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setState('idle'), 3000)
    }
  }

  const text = state === 'copied' ? copiedLabel : state === 'error' ? 'Copy failed' : label
  const liveMessage =
    state === 'copied' ? copiedLabel : state === 'error' ? 'Copy failed. Try again.' : ''

  return (
    <>
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {liveMessage}
      </span>
      <button
        type="button"
        className={className}
        disabled={disabled || !url}
        onClick={handleCopy}
        aria-busy={state === 'copied' ? false : undefined}
        aria-label={state === 'copied' ? copiedLabel : label}
        style={{ minHeight: 44, minWidth: 44 }}
      >
        {text}
      </button>
    </>
  )
}
