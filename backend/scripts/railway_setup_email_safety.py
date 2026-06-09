#!/usr/bin/env python3
"""Apply email-safety env vars to API + create/update email-jobs cron on Railway.

Uses account/project API token (Authorization: Bearer), NOT Project-Access-Token.

Usage:
  export RAILWAY_API_TOKEN='...'   # Account token with project access
  export ADMIN_NOTIFICATION_EMAILS='ops@example.com'  # optional override
  python3 scripts/railway_setup_email_safety.py

Optional: DRY_RUN=1 to print actions without mutating.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

GRAPHQL = "https://backboard.railway.com/graphql/v2"

PROJECT_ID = os.environ.get("PROJECT_ID", "ead85fb6-1826-4eed-bad9-2513e89c4854")
ENVIRONMENT_ID = os.environ.get("ENVIRONMENT_ID", "73d09081-50d4-4b9c-8c78-26ea06d39a6b")
API_SERVICE_ID = os.environ.get("API_SERVICE_ID", "8cbf6141-ce7e-41db-83ef-021d2cb6a86b")
CRON_SERVICE_NAME = os.environ.get("CRON_SERVICE_NAME", "email-jobs")

EMAIL_SAFETY_VARS = {
    "EMAIL_INVITE_RETRY_DELAY_MINUTES": "15",
    "EMAIL_INVITE_MAX_ATTEMPTS_24H": "3",
    "EMAIL_TEMPLATE_DEDUPE_MINUTES": "15",
    "EMAIL_RECIPIENT_MAX_PER_DAY": "10",
    "EMAIL_ADMIN_ALERT_ON_FAILED_FINAL": "true",
    "ZEPTOMAIL_LOG_SYNC_ENABLED": "false",
    "PASSWORD_RESET_EXPIRE_HOURS": "1",
    "PASSWORD_RESET_RATE_LIMIT_PER_HOUR": "3",
}

CRON_VARS = {
    "DATABASE_URL": "${{Postgres.DATABASE_URL}}",
    "REDIS_URL": "${{Redis.REDIS_URL}}",
    "APP_ENV": "production",
    **EMAIL_SAFETY_VARS,
}


def _token() -> str:
    tok = (
        os.environ.get("RAILWAY_API_TOKEN", "").strip()
        or os.environ.get("RAILWAY_TOKEN", "").strip()
    )
    if not tok:
        print("Set RAILWAY_API_TOKEN (Bearer token with project access).", file=sys.stderr)
        sys.exit(1)
    return tok


def gql(token: str, query: str, variables: dict | None = None) -> dict:
    body: dict = {"query": query}
    if variables is not None:
        body["variables"] = variables
    proc = subprocess.run(
        [
            "curl",
            "-sS",
            "-m",
            "120",
            GRAPHQL,
            "-H",
            f"Authorization: Bearer {token}",
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps(body),
        ],
        capture_output=True,
        text=True,
        timeout=130,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "curl failed")
    text = (proc.stdout or "").strip()
    if not text:
        raise RuntimeError("empty GraphQL response")
    return json.loads(text)


def list_services(token: str) -> list[dict]:
    data = gql(
        token,
        """
        query($id: String!) {
          project(id: $id) {
            services { edges { node { id name } } }
          }
        }
        """,
        {"id": PROJECT_ID},
    )
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    edges = (data.get("data") or {}).get("project", {}).get("services", {}).get("edges") or []
    return [e["node"] for e in edges]


def upsert_vars_batch(
    token: str,
    *,
    service_id: str,
    variables: dict[str, str],
    dry_run: bool,
    skip_deploys: bool = True,
) -> None:
    if dry_run:
        print(f"  [dry-run] batch set {len(variables)} vars on {service_id}")
        return
    data = gql(
        token,
        """
        mutation($input: VariableCollectionUpsertInput!) {
          variableCollectionUpsert(input: $input)
        }
        """,
        {
            "input": {
                "projectId": PROJECT_ID,
                "environmentId": ENVIRONMENT_ID,
                "serviceId": service_id,
                "skipDeploys": skip_deploys,
                "variables": variables,
            }
        },
    )
    if data.get("errors"):
        raise RuntimeError(f"variableCollectionUpsert: {data['errors']}")
    if not (data.get("data") or {}).get("variableCollectionUpsert"):
        raise RuntimeError(f"variableCollectionUpsert failed: {data}")


def upsert_var(
    token: str,
    *,
    service_id: str,
    name: str,
    value: str,
    dry_run: bool,
    skip_deploys: bool = True,
) -> None:
    if dry_run:
        print(f"  [dry-run] set {name} on {service_id}")
        return
    data = gql(
        token,
        "mutation($input: VariableUpsertInput!) { variableUpsert(input: $input) }",
        {
            "input": {
                "projectId": PROJECT_ID,
                "environmentId": ENVIRONMENT_ID,
                "serviceId": service_id,
                "name": name,
                "value": value,
                "skipDeploys": skip_deploys,
            }
        },
    )
    if data.get("errors"):
        raise RuntimeError(f"variableUpsert {name}: {data['errors']}")


def find_cron_service(services: list[dict]) -> dict | None:
    for s in services:
        if s.get("name") == CRON_SERVICE_NAME:
            return s
    return None


def create_cron_service(token: str, *, dry_run: bool) -> str:
    if dry_run:
        print(f"  [dry-run] serviceCreate name={CRON_SERVICE_NAME}")
        return "dry-run-service-id"
    data = gql(
        token,
        """
        mutation($input: ServiceCreateInput!) {
          serviceCreate(input: $input) { id name }
        }
        """,
        {
            "input": {
                "projectId": PROJECT_ID,
                "environmentId": ENVIRONMENT_ID,
                "name": CRON_SERVICE_NAME,
            }
        },
    )
    if data.get("errors"):
        raise RuntimeError(f"serviceCreate: {data['errors']}")
    svc = (data.get("data") or {}).get("serviceCreate") or {}
    return svc["id"]


def configure_cron_instance(token: str, service_id: str, *, dry_run: bool) -> None:
    inp = {
        "rootDirectory": "backend",
        "railwayConfigFile": "railway.email-cron.toml",
        "startCommand": "python scripts/run_email_jobs.py all",
        "cronSchedule": "*/10 * * * *",
        "restartPolicyType": "ON_FAILURE",
        "builder": "DOCKERFILE",
        "dockerfilePath": "Dockerfile",
        "healthcheckPath": None,
    }
    if dry_run:
        print(f"  [dry-run] serviceInstanceUpdate {service_id}: {inp}")
        return
    data = gql(
        token,
        """
        mutation($serviceId: String!, $environmentId: String!, $input: ServiceInstanceUpdateInput!) {
          serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input)
        }
        """,
        {
            "serviceId": service_id,
            "environmentId": ENVIRONMENT_ID,
            "input": inp,
        },
    )
    if data.get("errors"):
        raise RuntimeError(f"serviceInstanceUpdate: {data['errors']}")


def main() -> int:
    dry_run = os.environ.get("DRY_RUN", "").strip() in ("1", "true", "yes")
    token = _token()
    admin_emails = os.environ.get(
        "ADMIN_NOTIFICATION_EMAILS", "midhunnoble@gmail.com"
    ).strip()

    api_vars = dict(EMAIL_SAFETY_VARS)
    if admin_emails:
        api_vars["ADMIN_NOTIFICATION_EMAILS"] = admin_emails

    print("Setting email-safety variables on API service (case-manager-new)...")
    if dry_run:
        for name in api_vars:
            print(f"  API: {name}")
    else:
        upsert_vars_batch(token, service_id=API_SERVICE_ID, variables=api_vars, dry_run=False)

    services = list_services(token)
    cron = find_cron_service(services)
    if cron:
        cron_id = cron["id"]
        print(f"Found cron service {CRON_SERVICE_NAME} ({cron_id})")
    else:
        print(f"Creating cron service {CRON_SERVICE_NAME}...")
        cron_id = create_cron_service(token, dry_run=dry_run)
        print(f"  created {cron_id}")

    print("Configuring cron instance (schedule, start command, config file)...")
    configure_cron_instance(token, cron_id, dry_run=dry_run)

    print("Setting cron service variables...")
    cron_vars = dict(CRON_VARS)
    if admin_emails:
        cron_vars["ADMIN_NOTIFICATION_EMAILS"] = admin_emails
    if dry_run:
        for name in cron_vars:
            print(f"  CRON: {name}")
    else:
        upsert_vars_batch(token, service_id=cron_id, variables=cron_vars, dry_run=False)
        print(f"  CRON: set {len(cron_vars)} variables (batch)")

    print("\nDone.")
    print("  API: redeploy case-manager-new if not auto-deployed.")
    print("  Cron: connect GitHub repo in Railway if new service has no source; set Root Directory=backend.")
    print("  Verify: curl https://case-manager-new-production.up.railway.app/health")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
