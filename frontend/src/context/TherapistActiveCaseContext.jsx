import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { loadActiveCase, pushRecentCaseId, saveActiveCase } from '../lib/therapistActiveCase.js'

const TherapistActiveCaseContext = createContext(null)

export function TherapistActiveCaseProvider({ children }) {
  const [activeCase, setActiveCaseState] = useState(() => loadActiveCase())

  const setActiveCase = useCallback((row) => {
    const next = row?.id
      ? {
          id: row.id,
          caseId: row.caseId || row.case_code || row.caseCode,
          child: row.child || row.child_name || row.childName,
        }
      : null
    setActiveCaseState(next)
    saveActiveCase(next)
  }, [])

  const touchRecentCase = useCallback((caseId) => {
    pushRecentCaseId(caseId)
  }, [])

  const value = useMemo(
    () => ({ activeCase, setActiveCase, touchRecentCase }),
    [activeCase, setActiveCase, touchRecentCase],
  )

  return (
    <TherapistActiveCaseContext.Provider value={value}>{children}</TherapistActiveCaseContext.Provider>
  )
}

export function useTherapistActiveCase() {
  const ctx = useContext(TherapistActiveCaseContext)
  if (!ctx) {
    return { activeCase: null, setActiveCase: () => {}, touchRecentCase: () => {} }
  }
  return ctx
}
