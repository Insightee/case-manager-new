# insighte.org domain cutover — team rollout

**Date:** 2026-05-28  
**Status:** Railway CORS + `FRONTEND_URL` updated; API redeployed.

## Primary URL for everyone

**https://www.insighte.org**

- Therapist login: https://www.insighte.org/therapistlogin
- Parent login: https://www.insighte.org/clientlogin
- Staff login: https://www.insighte.org/stafflogin

`https://insighte.org` works too — it redirects to `www` automatically.

## What still works (do not remove yet)

| URL | Status |
|-----|--------|
| `https://www.insighte.org` | Primary production |
| `https://insighte.org` | Redirects to www |
| `https://frontend-omega-eight-92.vercel.app` | Legacy Vercel URL — still works for bookmarks |

## Email and invite links

New invites, password resets, and booking emails now use **`https://www.insighte.org`** in links.

**Action required:** Re-send any pending invites or password resets that were sent **before** this cutover (old links may still point at the `vercel.app` host).

From Admin portal: resend invite for affected users.

## API (unchanged)

Backend remains at:

`https://case-manager-new-production.up.railway.app`

No change for developers — only the browser-facing UI hostname changed.

## Verification completed

- Railway `FRONTEND_URL` → `https://www.insighte.org`
- Railway `CORS_ORIGINS` includes www, apex, legacy vercel.app, and localhost
- CORS preflight OK for all three production origins
- Apex `insighte.org` → 308 → `www.insighte.org`
- Demo login API succeeds with `Origin: https://www.insighte.org`

## Share with teaching team (copy/paste)

> Insighte Case Manager is now on our custom domain: **https://www.insighte.org**
>
> Use that link for therapist, parent, and staff logins. The old `frontend-omega-eight-92.vercel.app` link still works for now.
>
> If you received an invite email before today, ask admin to **re-send** the invite so the link uses the new domain.

## Future cleanup (optional, later)

When the team no longer needs the legacy Vercel URL:

1. Remove `frontend-omega-eight-92.vercel.app` from Vercel → Domains
2. Remove that host from Railway `CORS_ORIGINS`
3. Redeploy Railway API

Do **not** skip step 1 — removing CORS first breaks users still on the old URL.
