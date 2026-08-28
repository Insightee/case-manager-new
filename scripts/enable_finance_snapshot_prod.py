#!/usr/bin/env python3
"""Enable Stage 1 Finance snapshot + Control Tower on insighte.org (read-only cutover).

Sets:
  Railway (case-manager-new API): ENABLE_BILLING=true (mounts control-tower routes)
  Railway (unchanged):            BILLING_LEDGER_WRITES=false, FINANCE_CUTOVER_COMPLETE=false
  Vercel (insightes-projects/frontend, Production target):
    VITE_ENABLE_FINANCE_DASHBOARD_V1=true
    VITE_FINANCE_DASHBOARD_ALLOW_PROD=true

Requires (one of each platform):
  Railway: RAILWAY_PROJECT_TOKEN  OR  RAILWAY_API_TOKEN + linked project (backend/)
  Vercel:  VERCEL_TOKEN

Usage:
  export RAILWAY_PROJECT_TOKEN='...'
  export VERCEL_TOKEN='...'
  python3 scripts/enable_finance_snapshot_prod.py

  python3 scripts/enable_finance_snapshot_prod.py --verify-only   # post-redeploy smoke

See docs/FINANCE_SNAPSHOT_PROD_CUTOVER.md
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"

VERCEL_TEAM = os.environ.get("VERCEL_SCOPE", "insightes-projects")
VERCEL_PROJECT_ID = os.environ.get("VERCEL_PROJECT_ID", "prj_ibo0tJpTFO1Y8d5cKiKicB7Yr6vN")
PROD_API = os.environ.get("PROD_API_URL", "https://case-manager-new-production.up.railway.app").rstrip("/")

RAILWAY_GRAPHQL = "https://backboard.railway.com/graphql/v2"
RAILWAY_DEFAULT_PROJECT = "ead85fb6-1826-4eed-bad9-2513e89c4854"
RAILWAY_DEFAULT_ENV = "73d09081-50d4-4b9c-8c78-26ea06d39a6b"
RAILWAY_DEFAULT_SERVICE = "8cbf6141-ce7e-41db-83ef-021d2cb6a86b"

VERCEL_PROD_FLAGS = {
    "VITE_ENABLE_FINANCE_DASHBOARD_V1": "true",
    "VITE_FINANCE_DASHBOARD_ALLOW_PROD": "true",
}

RAILWAY_FLAGS = {
    "ENABLE_BILLING": "true",
    "BILLING_LEDGER_WRITES": "false",
    "FINANCE_CUTOVER_COMPLETE": "false",
}


def _vercel_request(method: str, path: str, body: dict | None = None) -> dict | list:
    token = os.environ.get("VERCEL_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Set VERCEL_TOKEN (Vercel account token with project access).")
    qs = urllib.parse.urlencode({"teamId": VERCEL_TEAM})
    url = f"https://api.vercel.com{path}?{qs}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode() if exc.fp else ""
        raise RuntimeError(f"Vercel HTTP {exc.code} {method} {path}: {detail[:400]}") from exc


def _railway_gql(token: str, query: str, variables: dict | None = None) -> dict:
    body: dict = {"query": query}
    if variables is not None:
        body["variables"] = variables
    proc = subprocess.run(
        [
            "curl",
            "-sS",
            "-m",
            "90",
            RAILWAY_GRAPHQL,
            "-H",
            f"Project-Access-Token: {token}",
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps(body),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "Railway GraphQL curl failed")
    text = (proc.stdout or "").strip()
    if not text:
        raise RuntimeError("empty Railway GraphQL response")
    return json.loads(text)


def _railway_upsert(token: str, project_id: str, env_id: str, service_id: str, name: str, value: str) -> None:
    data = _railway_gql(
        token,
        "mutation($input: VariableUpsertInput!) { variableUpsert(input: $input) }",
        {
            "input": {
                "projectId": project_id,
                "environmentId": env_id,
                "serviceId": service_id,
                "name": name,
                "value": value,
            }
        },
    )
    if data.get("errors"):
        raise RuntimeError(f"Railway upsert {name}: {data['errors']}")


def _railway_via_project_token() -> None:
    token = os.environ.get("RAILWAY_PROJECT_TOKEN", "").strip()
    if not token:
        return
    project_id = os.environ.get("PROJECT_ID", RAILWAY_DEFAULT_PROJECT).strip()
    env_id = os.environ.get("ENVIRONMENT_ID", RAILWAY_DEFAULT_ENV).strip()
    service_id = os.environ.get("SERVICE_ID", RAILWAY_DEFAULT_SERVICE).strip()
    if not os.environ.get("PROJECT_ID") or not os.environ.get("ENVIRONMENT_ID"):
        data = _railway_gql(token, "query { projectToken { projectId environmentId } }")
        pt = (data.get("data") or {}).get("projectToken") or {}
        project_id = pt.get("projectId") or project_id
        env_id = pt.get("environmentId") or env_id
    for name, value in RAILWAY_FLAGS.items():
        _railway_upsert(token, project_id, env_id, service_id, name, value)
        print(f"[railway] set {name}={value}")
    print(f"[railway] project={project_id} env={env_id} service={service_id}")


def _railway_via_cli() -> None:
    if os.environ.get("RAILWAY_PROJECT_TOKEN"):
        return
    api_token = os.environ.get("RAILWAY_API_TOKEN", "").strip()
    if not api_token:
        raise RuntimeError("Set RAILWAY_PROJECT_TOKEN or RAILWAY_API_TOKEN.")
    env = {**os.environ, "RAILWAY_API_TOKEN": api_token}
    env.pop("RAILWAY_TOKEN", None)
    args = ["npx", "@railway/cli", "variable", "set"]
    for name, value in RAILWAY_FLAGS.items():
        args.append(f"{name}={value}")
    proc = subprocess.run(args, cwd=BACKEND, env=env, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"railway variable set failed: {proc.stderr or proc.stdout}")
    print(proc.stdout or "[railway] variables set via CLI")


def _vercel_upsert_prod(key: str, value: str) -> None:
    existing = _vercel_request("GET", f"/v9/projects/{VERCEL_PROJECT_ID}/env")
    envs = existing if isinstance(existing, list) else existing.get("envs") or existing.get("data") or []
    for item in envs:
        if (item.get("key") or item.get("name")) != key:
            continue
        targets = item.get("target") or []
        if "production" not in targets:
            continue
        eid = item.get("id")
        _vercel_request(
            "PATCH",
            f"/v9/projects/{VERCEL_PROJECT_ID}/env/{eid}",
            {"value": value, "target": ["production"], "type": "plain"},
        )
        print(f"[vercel] updated {key}={value} (production)")
        return
    _vercel_request(
        "POST",
        f"/v10/projects/{VERCEL_PROJECT_ID}/env",
        {"key": key, "value": value, "type": "plain", "target": ["production"]},
    )
    print(f"[vercel] created {key}={value} (production)")


def apply_cutover() -> None:
    print("==> Railway: enable read-only finance control tower routes")
    _railway_via_project_token()
    _railway_via_cli()

    print("==> Vercel: enable finance snapshot on canonical production")
    for key, value in VERCEL_PROD_FLAGS.items():
        _vercel_upsert_prod(key, value)

    print("")
    print("Next steps (required):")
    print("  1. Redeploy Railway service case-manager-new (API picks up ENABLE_BILLING).")
    print("  2. Redeploy Vercel project insightes-projects/frontend (Production).")
    print("  3. Run: python3 scripts/enable_finance_snapshot_prod.py --verify-only")
    print("")
    print("Rollback: set ENABLE_BILLING=false on Railway; remove or set false the two VITE_* flags on Vercel Production.")


def verify_cutover() -> None:
    print(f"==> GET {PROD_API}/health")
    with urllib.request.urlopen(f"{PROD_API}/health", timeout=30) as resp:
        health = json.loads(resp.read().decode())
    print(json.dumps(health, indent=2))

    tower_url = f"{PROD_API}/api/v1/admin/finance-control-tower/summary?billing_month=2026-07"
    print(f"==> GET {tower_url} (expect 401 without token, NOT 404 when ENABLE_BILLING=true)")
    try:
        with urllib.request.urlopen(tower_url, timeout=30) as resp:
            print(f"unexpected {resp.status}: {resp.read()[:200]}")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print("FAIL: control tower still 404 — ENABLE_BILLING may be false or API not redeployed yet.")
            raise SystemExit(1)
        if exc.code in (401, 403):
            print(f"PASS: route mounted (HTTP {exc.code} without auth — expected).")
        else:
            print(f"WARN: HTTP {exc.code} — check manually.")
            raise SystemExit(1)

    print("")
    print("Frontend: sign in as superadmin@… on https://www.insighte.org")
    print("  Admin → Client invoices → Tools → Snapshot")
    print("  Expect finance summary metrics (not the environment gate empty state).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Enable finance snapshot on insighte.org")
    parser.add_argument("--verify-only", action="store_true", help="Post-redeploy smoke checks only")
    args = parser.parse_args()
    if args.verify_only:
        verify_cutover()
        return 0
    apply_cutover()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
