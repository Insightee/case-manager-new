#!/usr/bin/env python3
"""Set Railway FRONTEND_URL + CORS_ORIGINS for insighte.org production cutover.

Only updates domain-related vars (no SMTP/R2/JWT changes).

Usage:
  export RAILWAY_API_TOKEN='...'   # Account token, workspace = No workspace
  # OR export RAILWAY_PROJECT_TOKEN='...'  # Project → Settings → Tokens
  python3 scripts/railway_set_insighte_domain_cors.py

Optional:
  REDEPLOY=1  — trigger service redeploy after variable upsert
  DRY_RUN=1   — print values without mutating Railway
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

GRAPHQL = "https://backboard.railway.com/graphql/v2"

PROJECT_ID = os.environ.get("PROJECT_ID", "ead85fb6-1826-4eed-bad9-2513e89c4854")
ENVIRONMENT_ID = os.environ.get("ENVIRONMENT_ID", "73d09081-50d4-4b9c-8c78-26ea06d39a6b")
SERVICE_ID = os.environ.get("SERVICE_ID", "8cbf6141-ce7e-41db-83ef-021d2cb6a86b")

FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://www.insighte.org").rstrip("/")
CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,https://www.insighte.org,https://insighte.org,https://frontend-omega-eight-92.vercel.app",
)


def _token() -> tuple[str, str]:
    project = os.environ.get("RAILWAY_PROJECT_TOKEN", "").strip()
    if project:
        return project, "Project-Access-Token"
    account = os.environ.get("RAILWAY_API_TOKEN", "").strip()
    if account:
        return account, "Authorization"
    print(
        "Set RAILWAY_API_TOKEN (account) or RAILWAY_PROJECT_TOKEN (project token).",
        file=sys.stderr,
    )
    sys.exit(1)


def gql(token: str, header: str, query: str, variables: dict | None = None) -> dict:
    body: dict = {"query": query}
    if variables is not None:
        body["variables"] = variables
    auth_value = f"Bearer {token}" if header == "Authorization" else token
    proc = subprocess.run(
        [
            "curl",
            "-sS",
            "-m",
            "90",
            GRAPHQL,
            "-H",
            f"{header}: {auth_value}",
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
        raise RuntimeError(proc.stderr or proc.stdout or "curl failed")
    text = (proc.stdout or "").strip()
    if not text:
        raise RuntimeError("empty GraphQL response")
    return json.loads(text)


def upsert(token: str, header: str, name: str, value: str) -> None:
    data = gql(
        token,
        header,
        "mutation($input: VariableUpsertInput!) { variableUpsert(input: $input) }",
        {
            "input": {
                "projectId": PROJECT_ID,
                "environmentId": ENVIRONMENT_ID,
                "serviceId": SERVICE_ID,
                "name": name,
                "value": value,
            }
        },
    )
    if data.get("errors"):
        raise RuntimeError(f"upsert {name}: {data['errors']}")


def redeploy(token: str, header: str) -> None:
    data = gql(
        token,
        header,
        "mutation($input: ServiceInstanceRedeployInput!) { serviceInstanceRedeploy(input: $input) }",
        {
            "input": {
                "serviceId": SERVICE_ID,
                "environmentId": ENVIRONMENT_ID,
            }
        },
    )
    if data.get("errors"):
        raise RuntimeError(f"redeploy: {data['errors']}")


def main() -> int:
    dry = os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes")
    do_redeploy = os.environ.get("REDEPLOY", "1").strip().lower() in ("1", "true", "yes")

    print(f"FRONTEND_URL={FRONTEND_URL}")
    print(f"CORS_ORIGINS={CORS_ORIGINS}")
    if dry:
        print("DRY_RUN=1 — no Railway changes.")
        return 0

    token, header = _token()
    upsert(token, header, "FRONTEND_URL", FRONTEND_URL)
    print("set FRONTEND_URL")
    upsert(token, header, "CORS_ORIGINS", CORS_ORIGINS)
    print("set CORS_ORIGINS")

    if do_redeploy:
        redeploy(token, header)
        print("triggered API redeploy")
    else:
        print("REDEPLOY not set — restart API in Railway dashboard if needed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
