#!/usr/bin/env python3
"""Set Railway service variables via GraphQL (project token). No secrets in repo.

Usage:
  export RAILWAY_PROJECT_TOKEN='...'   # Project → Settings → Tokens
  export R2_ACCESS_KEY_ID='...'
  export R2_SECRET_ACCESS_KEY='...'
  python3 scripts/railway_set_vars_graphql.py

Optional: PROJECT_ID, ENVIRONMENT_ID, SERVICE_ID (auto-resolved from token if omitted).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

GRAPHQL = "https://backboard.railway.com/graphql/v2"

DEFAULT_PROJECT = "ead85fb6-1826-4eed-bad9-2513e89c4854"
DEFAULT_ENV = "73d09081-50d4-4b9c-8c78-26ea06d39a6b"
DEFAULT_SERVICE = "8cbf6141-ce7e-41db-83ef-021d2cb6a86b"
# insightes-projects/frontend (prj_ibo0tJpTFO1Y8d5cKiKicB7Yr6vN) — override after green Vercel deploy
VERCEL_URL = os.environ.get(
    "VERCEL_URL",
    "https://frontend-insightes-projects.vercel.app",
)


def gql(token: str, query: str, variables: dict | None = None) -> dict:
    body: dict = {"query": query}
    if variables is not None:
        body["variables"] = variables
    proc = subprocess.run(
        [
            "curl",
            "-sS",
            "-m",
            "90",
            GRAPHQL,
            "-H",
            f"Project-Access-Token: {token}",
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps(body),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "curl failed")
    text = (proc.stdout or "").strip()
    if not text:
        raise RuntimeError("empty GraphQL response")
    return json.loads(text)


def resolve_ids(token: str) -> tuple[str, str]:
    data = gql(token, "query { projectToken { projectId environmentId } }")
    pt = (data.get("data") or {}).get("projectToken") or {}
    return pt.get("projectId") or DEFAULT_PROJECT, pt.get("environmentId") or DEFAULT_ENV


def upsert(
    token: str,
    project_id: str,
    env_id: str,
    service_id: str,
    name: str,
    value: str,
) -> None:
    data = gql(
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
        raise RuntimeError(f"upsert {name}: {data['errors']}")


def delete_var(
    token: str,
    project_id: str,
    env_id: str,
    service_id: str,
    name: str,
) -> None:
    data = gql(
        token,
        "mutation($input: VariableDeleteInput!) { variableDelete(input: $input) }",
        {
            "input": {
                "projectId": project_id,
                "environmentId": env_id,
                "serviceId": service_id,
                "name": name,
            }
        },
    )
    if data.get("errors"):
        print(f"warn delete {name}: {data['errors']}", file=sys.stderr)


def main() -> int:
    token = os.environ.get("RAILWAY_PROJECT_TOKEN", "").strip()
    if not token:
        print("Set RAILWAY_PROJECT_TOKEN (project token, not account token).", file=sys.stderr)
        return 1

    r2_key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    r2_secret = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()

    project_id = os.environ.get("PROJECT_ID", "").strip()
    env_id = os.environ.get("ENVIRONMENT_ID", "").strip()
    if not project_id or not env_id:
        project_id, env_id = resolve_ids(token)
    service_id = os.environ.get("SERVICE_ID", DEFAULT_SERVICE).strip()

    cors = f"http://localhost:5173,{VERCEL_URL.rstrip('/')}"
    pairs = {
        "APP_ENV": "production",
        "SEED_DEMO_DATA": "false",
        "EMAIL_PROVIDER": "zeptomail",
        "SMTP_HOST": "smtp.zeptomail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "emailapikey",
        "SMTP_TLS": "true",
        "SMTP_FROM_EMAIL": "noreply@insighte.in",
        "SMTP_FROM_BILLING_EMAIL": "billing.noreply@insighte.in",
        "SMTP_FROM_VERIFICATION_EMAIL": "verification.noreply@insighte.in",
        "SMTP_FROM_NAME": "Insighte",
        "STORAGE_PROVIDER": "r2",
        "STORAGE_PREFIX": "insightcase",
        "STORAGE_ENVIRONMENT": "production",
        "R2_ACCOUNT_ID": "0409ea66ef188ae9783c5e9aa7af9445",
        "R2_BUCKET_NAME": "insightecase",
        "R2_ENDPOINT_URL": "https://0409ea66ef188ae9783c5e9aa7af9445.r2.cloudflarestorage.com",
        "FRONTEND_URL": VERCEL_URL.rstrip("/"),
        "CORS_ORIGINS": cors,
        # Requires a Redis plugin service named \"redis\" in the same Railway project.
        "REDIS_URL": "${{redis.REDIS_URL}}",
    }
    if r2_key and r2_secret:
        pairs["R2_ACCESS_KEY_ID"] = r2_key
        pairs["R2_SECRET_ACCESS_KEY"] = r2_secret

    for name, value in pairs.items():
        upsert(token, project_id, env_id, service_id, name, value)
        print(f"set {name}")

    for legacy in ("SMTP_USERNAME", "EMAIL_FROM_DEFAULT"):
        delete_var(token, project_id, env_id, service_id, legacy)
        print(f"removed legacy {legacy}")

    print(f"project={project_id} env={env_id} service={service_id}")
    print("Redeploy the case-manager-new service on Railway.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
