/**
 * Unwrap paginated list API responses (`{ items, total, ... }`) or return arrays as-is.
 */
export function unwrapList(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.items)) return data.items
  return []
}

/**
 * Fetch every page from a paginated API. `fetchPage(page, pageSize)` must return
 * `{ items, total, ... }` or a bare array.
 */
export async function fetchAllPages(fetchPage, { pageSize = 100, maxPages = 50 } = {}) {
  let page = 1
  let allItems = []
  let total = 0

  while (page <= maxPages) {
    const data = await fetchPage(page, pageSize)
    const items = unwrapList(data)
    total = typeof data?.total === 'number' ? data.total : items.length
    allItems = allItems.concat(items)
    if (items.length === 0 || allItems.length >= total) break
    page += 1
  }

  return { items: allItems, total: Math.max(total, allItems.length) }
}
