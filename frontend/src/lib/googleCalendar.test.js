import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildGoogleCalendarAccountChooserUrl,
  buildGoogleCalendarUrl,
  durationMinutesFromTimes,
  mapCmMeetingToCalendarEvent,
  mapSlotToCalendarEvent,
  normalizeSlotForCalendar,
} from './googleCalendar.js'

describe('googleCalendar', () => {
  it('buildGoogleCalendarUrl uses ctz and local wall-clock dates', () => {
    const url = buildGoogleCalendarUrl({
      title: 'Care coordination',
      scheduledDate: '2026-07-15',
      startTime: '11:00',
      durationMinutes: 45,
      details: 'Join: https://meet.google.com/abc',
      location: 'https://meet.google.com/abc',
      timezone: 'Asia/Kolkata',
    })
    assert.ok(url.startsWith('https://calendar.google.com/calendar/render?'))
    assert.match(url, /action=TEMPLATE/)
    assert.match(url, /ctz=Asia%2FKolkata/)
    assert.match(url, /20260715T110000/)
    assert.match(url, /20260715T114500/)
    assert.match(url, /Care\+coordination|Care%20coordination/)
  })

  it('durationMinutesFromTimes computes slot length', () => {
    assert.equal(durationMinutesFromTimes('10:00', '10:45'), 45)
    assert.equal(durationMinutesFromTimes('09:30', '10:00'), 30)
  })

  it('mapSlotToCalendarEvent builds therapy session title', () => {
    const event = mapSlotToCalendarEvent({
      id: 12,
      slot_date: '2026-05-28',
      start_time: '14:00',
      end_time: '15:00',
      child_name: 'Alex',
      case_code: 'HC-001',
    })
    assert.equal(event.title, 'Therapy session · Alex')
    assert.equal(event.scheduledDate, '2026-05-28')
    assert.match(event.details, /HC-001/)
    assert.match(event.details, /Booking ID: 12/)
  })

  it('buildGoogleCalendarAccountChooserUrl wraps public template URL', () => {
    const event = {
      title: 'Therapy',
      scheduledDate: '2026-07-15',
      startTime: '11:00',
      durationMinutes: 30,
    }
    const chooser = buildGoogleCalendarAccountChooserUrl(event)
    assert.ok(chooser?.startsWith('https://accounts.google.com/AccountChooser?continue='))
    assert.ok(chooser.includes(encodeURIComponent('https://calendar.google.com/calendar/render?')))
    assert.ok(!chooser.includes('workspace.google.com'))
  })

  it('normalizeSlotForCalendar accepts date aliases', () => {
    const normalized = normalizeSlotForCalendar({
      id: 3,
      date: '2026-05-28',
      startTime: '14:00',
      endTime: '15:00',
    })
    assert.equal(normalized.slot_date, '2026-05-28')
    assert.equal(normalized.start_time, '14:00')
  })

  it('mapCmMeetingToCalendarEvent includes meeting metadata', () => {
    const event = mapCmMeetingToCalendarEvent({
      id: 5,
      scheduled_date: '2026-06-01',
      scheduled_time: '10:30',
      duration_minutes: 30,
      meeting_type: 'IEP_MEETING',
      child_name: 'Sam',
      case_code: 'SS-002',
      meeting_url: 'https://meet.google.com/xyz',
    })
    assert.match(event.title, /Sam/)
    assert.equal(event.durationMinutes, 30)
    assert.equal(event.location, 'https://meet.google.com/xyz')
    assert.match(event.details, /Meeting ID: 5/)
  })
})
