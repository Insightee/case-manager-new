/** Pure helpers for the app-usage tracker (useAppUsageTracker), kept testable without React. */

/**
 * Persist the queue (with the new chunk) BEFORE sending, then send. On success remove only the
 * chunks that were sent, so anything queued meanwhile, or anything that failed, stays persisted.
 * @param {{
 *   getQueue: () => any[]
 *   setQueue: (q: any[]) => void
 *   save: (q: any[]) => void
 *   send: (payload: { chunks: any[] }) => Promise<void>
 *   chunk: any | null
 *   maxQueue: number
 * }} args
 * @returns {Promise<boolean>} true when the batch was accepted
 */
export async function sendUsageQueue({ getQueue, setQueue, save, send, chunk, maxQueue }) {
  const queued = chunk ? [...getQueue(), chunk].slice(-maxQueue) : getQueue().slice(-maxQueue)
  setQueue(queued)
  save(queued)
  if (queued.length === 0) return true
  const sentKeys = new Set(queued.map((c) => c?.idempotency_key))
  try {
    await send({ chunks: queued })
  } catch {
    return false
  }
  const remaining = getQueue().filter((c) => !sentKeys.has(c?.idempotency_key))
  setQueue(remaining)
  save(remaining)
  return true
}

/**
 * Flush immediately (keepalive) when the tab is hidden or the page is closing, so usage is never
 * lost between interval flushes.
 * @param {{ flush: (opts: { reason: string, useKeepalive: boolean }) => unknown, win: any, doc: any }} args
 * @returns {() => void} unbind
 */
export function bindUsageFlushOnLeave({ flush, win, doc }) {
  const onPageHide = () => {
    void flush({ reason: 'pagehide', useKeepalive: true })
  }
  const onVisibility = () => {
    if (doc.visibilityState === 'hidden') {
      void flush({ reason: 'hidden', useKeepalive: true })
    }
  }
  win.addEventListener('pagehide', onPageHide)
  doc.addEventListener('visibilitychange', onVisibility)
  return () => {
    win.removeEventListener('pagehide', onPageHide)
    doc.removeEventListener('visibilitychange', onVisibility)
  }
}
