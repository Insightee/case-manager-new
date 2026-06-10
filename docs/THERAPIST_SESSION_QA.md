# Therapist session logs — manual QA checklist

Sign in as `therapist@demo.com` / `demo123` after seeding (`python3 -m app.seed.demo_seed`).

## Case detail overview

1. Open any assigned case → **Overview** tab.
2. Confirm **Client history** is the top hero card.
3. Confirm **Operational timeline** shows recent status-request events (or empty hint).
4. Confirm **Case manager** card shows avatar, email, and support link.
5. Confirm **Quick actions** and inline status form are gone.
6. Use **Request change** in the title row → modal submits a status request.
7. If a pending status request exists, the banner appears under the header.

## Session start guard

1. On **Session logs**, find a visit scheduled for a future date → **Start** is hidden or blocked with forgot-to-log guidance.
2. Try starting tomorrow's session via API or deep link → blocked with visit-day message.

## Same-day duplicate

1. Complete one session for a client today.
2. Start a second scheduled session for the same client today → **Another session today?** dialog.
3. **Edit existing session** navigates to the first log.
4. **Start another session** succeeds; submitted log shows **Second session same day — pending review**.

## Edit actual times

1. Complete a session and submit its log.
2. Within 24 hours of end, use **Edit times** on the log row.
3. Save with a reason → **Times edited** badge; log returns to **Pending review**.

## Session logs month filter

1. **Needs log** tab is never month-filtered.
2. **Pending / Approved / Rejected / All** default to the current calendar month (IST).
3. Change month/year → historical tabs update; Needs log count unchanged.

## Admin visibility

1. As admin, open case **Sessions & logs** or **Session logs** dashboard.
2. Rows with edited times or same-day duplicates show **Times edited** / **Same-day duplicate** badges.
