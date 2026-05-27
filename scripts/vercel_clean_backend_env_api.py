#!/usr/bin/env python3
"""Remove backend env vars from Vercel project insightes-projects/frontend via REST API.

Faster and explicit than looping `vercel env rm` (always targets --project frontend).

  export VERCEL_TOKEN=...
  python3 scripts/vercel_clean_backend_env_api.py
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TEAM_SLUG = os.environ.get("VERCEL_SCOPE", "insightes-projects")
PROJECT = os.environ.get("VERCEL_PROJECT", "frontend")
PROJECT_ID = os.environ.get("VERCEL_PROJECT_ID", "prj_ibo0tJpTFO1Y8d5cKiKicB7Yr6vN")
KEEP = frozenset({"VITE_API_URL"})

if PROJECT == "case-manager-new":
    print("ERROR: Vercel project must be 'frontend', not 'case-manager-new'.", file=sys.stderr)
    raise SystemExit(1)


def _request(method: str, path: str) -> dict | list:
    token = os.environ.get("VERCEL_TOKEN", "").strip()
    if not token:
        print("Set VERCEL_TOKEN.", file=sys.stderr)
        raise SystemExit(1)
    qs = urllib.parse.urlencode({"teamId": TEAM_SLUG})
    url = f"https://api.vercel.com{path}?{qs}" if "?" not in path else f"https://api.vercel.com{path}&{qs}"
    req = urllib.request.Request(
        url,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            import json

            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        print(f"HTTP {exc.code} {method} {path}: {body[:300]}", file=sys.stderr)
        raise


def main() -> int:
    data = _request("GET", f"/v9/projects/{PROJECT_ID}/env")
    envs = data if isinstance(data, list) else data.get("envs") or data.get("data") or []
    removed = 0
    for item in envs:
        key = item.get("key") or item.get("name")
        eid = item.get("id")
        targets = item.get("target") or []
        if not key or key in KEEP:
            continue
        _request("DELETE", f"/v9/projects/{PROJECT_ID}/env/{eid}")
        tgt = ",".join(targets) if isinstance(targets, list) else str(targets)
        print(f"removed {key} ({tgt})")
        removed += 1
    print(f"Done: removed {removed} var(s) from {TEAM_SLUG}/{PROJECT} ({PROJECT_ID}).")
    remaining = [
        (e.get("key") or e.get("name"))
        for e in envs
        if (e.get("key") or e.get("name")) not in KEEP
    ]
    if remaining and removed == 0:
        print("No removals (list may be stale); re-fetch or check token scope.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
