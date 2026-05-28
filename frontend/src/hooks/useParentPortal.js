import { useOutletContext } from 'react-router-dom'

const empty = { cases: [], casesLoading: false, reloadCases: async () => {} }

export function useParentPortal() {
  return useOutletContext() ?? empty
}
