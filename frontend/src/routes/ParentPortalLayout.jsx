import { useCallback } from 'react'
import { Outlet } from 'react-router-dom'
import '../components/client-portal/client-portal-mobile.css'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchParentCases } from '../lib/parentCases.js'
import { queryKeys } from '../lib/queryClient.js'

export function ParentPortalLayout() {
  const queryClient = useQueryClient()
  const { data: cases = [], isLoading } = useQuery({
    queryKey: queryKeys.parentCases,
    queryFn: fetchParentCases,
    staleTime: 60_000,
  })

  const reloadCases = useCallback(() => {
    return queryClient.invalidateQueries({ queryKey: queryKeys.parentCases })
  }, [queryClient])

  return <Outlet context={{ cases, casesLoading: isLoading, reloadCases }} />
}
