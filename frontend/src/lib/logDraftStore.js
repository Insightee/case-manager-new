const DB_NAME = 'insighte-log-drafts'
const STORE = 'drafts'
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

export async function getLogDraft(sessionId) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly')
    const req = tx.objectStore(STORE).get(Number(sessionId))
    req.onsuccess = () => resolve(req.result || null)
    req.onerror = () => reject(req.error)
  })
}

export async function saveLogDraft(sessionId, fields) {
  const db = await openDb()
  const record = {
    sessionId: Number(sessionId),
    fields,
    sync_payload: fields.sync_payload || null,
    updated_at: new Date().toISOString(),
    sync_status: fields.sync_status || 'local',
  }
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    const req = tx.objectStore(STORE).put(record)
    req.onsuccess = () => resolve(record)
    req.onerror = () => reject(req.error)
  })
}

export async function clearLogDraft(sessionId) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    const req = tx.objectStore(STORE).delete(Number(sessionId))
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

export async function listPendingDrafts() {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly')
    const req = tx.objectStore(STORE).getAll()
    req.onsuccess = () => {
      const all = req.result || []
      resolve(all.filter((d) => d.sync_status === 'pending_sync'))
    }
    req.onerror = () => reject(req.error)
  })
}

/** Session ids with any local draft (saved or pending sync). */
export async function listDraftSessionIds() {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly')
    const req = tx.objectStore(STORE).getAll()
    req.onsuccess = () => {
      const all = req.result || []
      resolve(all.map((d) => Number(d.sessionId)).filter((id) => Number.isFinite(id)))
    }
    req.onerror = () => reject(req.error)
  })
}

export async function markDraftSynced(sessionId) {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    const store = tx.objectStore(STORE)
    const getReq = store.get(Number(sessionId))
    getReq.onsuccess = () => {
      const row = getReq.result
      if (!row) {
        resolve(false)
        return
      }
      row.sync_status = 'synced'
      row.synced_at = new Date().toISOString()
      const putReq = store.put(row)
      putReq.onsuccess = () => resolve(true)
      putReq.onerror = () => reject(putReq.error)
    }
    getReq.onerror = () => reject(getReq.error)
  })
}
