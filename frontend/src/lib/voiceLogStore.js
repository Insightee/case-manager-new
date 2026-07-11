/**
 * Voice-first session log — local audio recovery store.
 * Holds the recorded blob until the backend confirms upload, so a network
 * drop never loses the therapist's recording. Separate DB from log drafts
 * to avoid a version bump on the existing store.
 */

const DB_NAME = 'insighte-voice-audio'
const STORE = 'recordings'
const VERSION = 1

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, VERSION)
    req.onerror = () => reject(req.error)
    req.onsuccess = () => resolve(req.result)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'sessionId' })
      }
    }
  })
}

export async function savePendingAudio(sessionId, blob, meta = {}) {
  const db = await openDb()
  const record = {
    sessionId: Number(sessionId),
    blob,
    mimeType: blob?.type || 'audio/webm',
    durationSeconds: meta.durationSeconds ?? null,
    recordingId: meta.recordingId ?? null,
    updated_at: new Date().toISOString(),
  }
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    const req = tx.objectStore(STORE).put(record)
    req.onsuccess = () => resolve(record)
    req.onerror = () => reject(req.error)
  })
}

export async function getPendingAudio(sessionId) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly')
    const req = tx.objectStore(STORE).get(Number(sessionId))
    req.onsuccess = () => resolve(req.result || null)
    req.onerror = () => reject(req.error)
  })
}

export async function clearPendingAudio(sessionId) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    const req = tx.objectStore(STORE).delete(Number(sessionId))
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

const FLOW_KEY = (sessionId) => `vsl-flow-${sessionId}`

/** Persist voice-flow step so a refresh mid-processing can resume. */
export function saveVoiceFlowState(sessionId, state) {
  try {
    sessionStorage.setItem(FLOW_KEY(sessionId), JSON.stringify({ ...state, updated_at: Date.now() }))
  } catch {
    // sessionStorage full or unavailable — non-fatal
  }
}

export function readVoiceFlowState(sessionId) {
  try {
    const raw = sessionStorage.getItem(FLOW_KEY(sessionId))
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function clearVoiceFlowState(sessionId) {
  try {
    sessionStorage.removeItem(FLOW_KEY(sessionId))
  } catch {
    // ignore
  }
}
