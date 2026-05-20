/**
 * Unwrap paginated list API responses (`{ items, total, ... }`) or return arrays as-is.
 */
export function unwrapList(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.items)) return data.items
  return []
}
