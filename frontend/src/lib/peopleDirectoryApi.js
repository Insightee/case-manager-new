import { apiFetch } from './apiClient.js'
import { fetchAllPages } from './listApi.js'
import { PEOPLE_PAGE_SIZE } from './peopleDirectoryList.js'

function buildQs(params) {
  const p = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value != null && value !== '') p.set(key, String(value))
  }
  return p.toString()
}

export async function fetchStaffPage({
  page = 1,
  pageSize = PEOPLE_PAGE_SIZE,
  search = '',
} = {}) {
  const qs = buildQs({
    page,
    page_size: pageSize,
    sort: 'email_asc',
    exclude_roles: 'THERAPIST,PARENT',
    search: search.trim() || undefined,
  })
  return apiFetch(`/api/v1/admin/users?${qs}`)
}

export async function fetchTherapistsPage({
  page = 1,
  pageSize = PEOPLE_PAGE_SIZE,
  search = '',
  sort = 'id_asc',
} = {}) {
  const qs = buildQs({
    page,
    page_size: pageSize,
    roles: 'THERAPIST',
    active_only: 'false',
    sort,
    search: search.trim() || undefined,
  })
  return apiFetch(`/api/v1/admin/users/directory?${qs}`)
}

export async function fetchClientsPage({
  page = 1,
  pageSize = PEOPLE_PAGE_SIZE,
  search = '',
} = {}) {
  const qs = buildQs({
    page,
    page_size: pageSize,
    search: search.trim() || undefined,
  })
  return apiFetch(`/api/v1/admin/families?${qs}`)
}

export async function fetchAllStaff({ search = '' } = {}) {
  return fetchAllPages((page, pageSize) => {
    const qs = buildQs({
      page,
      page_size: pageSize,
      sort: 'email_asc',
      exclude_roles: 'THERAPIST,PARENT',
      search: search.trim() || undefined,
    })
    return apiFetch(`/api/v1/admin/users?${qs}`)
  })
}

export async function fetchAllTherapists({ search = '', sort = 'id_asc' } = {}) {
  return fetchAllPages((page, pageSize) => {
    const qs = buildQs({
      page,
      page_size: pageSize,
      roles: 'THERAPIST',
      active_only: 'false',
      sort,
      search: search.trim() || undefined,
    })
    return apiFetch(`/api/v1/admin/users/directory?${qs}`)
  })
}

export async function fetchAllClients({ search = '' } = {}) {
  return fetchAllPages((page, pageSize) => {
    const qs = buildQs({
      page,
      page_size: pageSize,
      search: search.trim() || undefined,
    })
    return apiFetch(`/api/v1/admin/families?${qs}`)
  })
}

export async function fetchStaffMeta() {
  const [moduleMeta, rbacMeta] = await Promise.all([
    apiFetch('/api/v1/admin/modules'),
    apiFetch('/api/v1/admin/rbac/catalog').catch(() => null),
  ])
  return {
    catalog:
      rbacMeta ?? {
        modules: moduleMeta.modules ?? [],
        service_categories: moduleMeta.modules ?? [],
        org_capabilities: [],
        role_defaults: moduleMeta.role_defaults ?? {},
      },
    roleDefaults: rbacMeta?.role_defaults ?? moduleMeta.role_defaults ?? {},
    assignableRoles: rbacMeta?.assignable_roles ?? [],
    deprecatedRoles: rbacMeta?.deprecated_roles ?? [],
    staffDepartments: rbacMeta?.staff_departments ?? [],
  }
}

export async function fetchTabInvites() {
  const rows = await apiFetch('/api/v1/admin/invites').catch(() => [])
  return Array.isArray(rows) ? rows : []
}

export async function fetchParentsAwaitingLogin() {
  return apiFetch('/api/v1/admin/families/parents-awaiting-login').catch(() => ({
    count: 0,
    items: [],
  }))
}

export async function fetchTherapistProfiles() {
  const rows = await apiFetch('/api/v1/admin/therapist-profiles').catch(() => [])
  return Array.isArray(rows) ? rows : []
}
