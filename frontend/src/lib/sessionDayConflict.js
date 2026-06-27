/**
 * When multiple sessions exist for the same client + day, prefer the visit that
 * already started or ended over a duplicate scheduled slot.
 */
export function existingVisitForDay(session, { active, needsLog = [], logs = [] } = {}) {
  if (!session?.case_id || !session?.scheduled_date) return null
  const dayKey = `${session.case_id}|${session.scheduled_date}`

  if (
    active &&
    active.id !== session.id &&
    `${active.case_id}|${active.scheduled_date}` === dayKey
  ) {
    return active
  }

  const needs = needsLog.find(
    (s) => s.id !== session.id && `${s.case_id}|${s.scheduled_date}` === dayKey,
  )
  if (needs) return needs

  const logged = logs.find(
    (l) =>
      l.id > 0 &&
      l.case_id === session.case_id &&
      l.scheduled_date === session.scheduled_date &&
      Number(l.session_id) !== Number(session.id),
  )
  if (logged) {
    return {
      id: logged.session_id,
      case_id: logged.case_id,
      case_code: logged.case_code,
      child_name: logged.child_name,
      scheduled_date: logged.scheduled_date,
      start_time: logged.start_time,
      end_time: logged.end_time,
      actual_start_at: logged.actual_start_at,
      actual_end_at: logged.actual_end_at,
      edited_start_at: logged.edited_start_at,
      edited_end_at: logged.edited_end_at,
      status: 'COMPLETED',
      has_daily_log: true,
    }
  }

  return null
}

export function sessionToLogShape(session) {
  return {
    id: session.id,
    scheduled_date: session.scheduled_date,
    actual_start_at: session.actual_start_at,
    actual_end_at: session.actual_end_at,
    edited_start_at: session.edited_start_at,
    edited_end_at: session.edited_end_at,
    actual_times_edited: session.actual_times_edited,
    case_code: session.case_code,
    child_name: session.child_name,
    status: session.status || 'COMPLETED',
    has_daily_log: session.has_daily_log,
  }
}
