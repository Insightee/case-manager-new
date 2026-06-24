#!/usr/bin/env python3
"""Create or update session-day-end Railway cron (10 PM IST auto-close).

Usage:
  export RAILWAY_API_TOKEN='...'
  python3 scripts/railway_setup_session_day_end_cron.py

Optional: DRY_RUN=1
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

GRAPHQL = "https://backboard.railway.com/graphql/v2"

PROJECT_ID = os.environ.get("PROJECT_ID", "ead85fb6-1826-4eed-bad9-2513e89c4854")
ENVIRONMENT_ID = os.environ.get("ENVIRONMENT_ID", "73d09081-50d4-4b9c-8c78-26ea06d39a6b")
CRON_SERVICE_NAME = os.environ.get("CRON_SERVICE_NAME", "session-day-end")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "Insightee/case-manager-new")

CRON_VARS = {
    "DATABASE_URL": "${{Postgres.DATABASE_URL}}",
    "APP_ENV": "production",
}


def _token() -> str:
    tok = os.environ.get("RAILWAY_API_TOKEN", "").strip()
    if not tok:
        print("Set RAILWAY_API_TOKEN.", file=sys.stderr)
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
    return json.loads((proc.stdout or "").strip() or "{}")


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


def create_cron_service(token: str, *, dry_run: bool) -> str:
    if dry_run:
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
    return (data.get("data") or {}).get("serviceCreate", {})["id"]


def configure_cron_instance(token: str, service_id: str, *, dry_run: bool) -> None:
    inp = {
        "rootDirectory": "backend",
        "railwayConfigFile": "railway.session-day-end-cron.toml",
        "startCommand": "python scripts/auto_close_sessions_day_end.py",
        "cronSchedule": "30 16 * * *",
        "restartPolicyType": "ON_FAILURE",
        "builder": "RAILPACK",
        "healthcheckPath": None,
    }
    if dry_run:
        print(f"  [dry-run] serviceInstanceUpdate: {inp}")
        return
    data = gql(
        token,
        """
        mutation($serviceId: String!, $environmentId: String!, $input: ServiceInstanceUpdateInput!) {
          serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input)
        }
        """,
        {"serviceId": service_id, "environmentId": ENVIRONMENT_ID, "input": inp},
    )
    if data.get("errors"):
        raise RuntimeError(f"serviceInstanceUpdate: {data['errors']}")


def connect_repo(token: str, service_id: str, *, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] connect repo {GITHUB_REPO} to {service_id}")
        return
    data = gql(
        token,
        """
        mutation($id: String!, $input: ServiceConnectInput!) {
          serviceConnect(id: $id, input: $input) { id }
        }
        """,
        {
            "id": service_id,
            "input": {
                "repo": GITHUB_REPO,
                "branch": "main",
            },
        },
    )
    if data.get("errors"):
        err = data["errors"]
        # Repo may already be linked when service is created from project template.
        if any("ServiceInstance not found" in str(e) for e in err):
            print("  repo connect skipped (service may already be linked)")
            return
        raise RuntimeError(f"serviceConnect: {err}")


def upsert_vars_batch(token: str, *, service_id: str, variables: dict[str, str], dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] set {len(variables)} vars on {service_id}")
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
                "skipDeploys": False,
                "variables": variables,
            }
        },
    )
    if data.get("errors"):
        raise RuntimeError(f"variableCollectionUpsert: {data['errors']}")


def trigger_deploy(token: str, service_id: str, *, dry_run: bool) -> None:
    if dry_run:
        print(f"  [dry-run] deploy {service_id}")
        return
    data = gql(
        token,
        """
        mutation($serviceId: String!, $environmentId: String!) {
          serviceInstanceDeploy(serviceId: $serviceId, environmentId: $environmentId)
        }
        """,
        {"serviceId": service_id, "environmentId": ENVIRONMENT_ID},
    )
    if data.get("errors"):
        raise RuntimeError(f"serviceInstanceDeploy: {data['errors']}")


def main() -> int:
    dry_run = os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes")
    token = _token()

    services = list_services(token)
    cron = next((s for s in services if s.get("name") == CRON_SERVICE_NAME), None)
    if cron:
        cron_id = cron["id"]
        print(f"Found cron service {CRON_SERVICE_NAME} ({cron_id})")
    else:
        print(f"Creating cron service {CRON_SERVICE_NAME}...")
        cron_id = create_cron_service(token, dry_run=dry_run)
        print(f"  created {cron_id}")

    print("Connecting GitHub repo...")
    connect_repo(token, cron_id, dry_run=dry_run)

    print("Configuring cron instance...")
    configure_cron_instance(token, cron_id, dry_run=dry_run)

    print("Setting cron variables...")
    upsert_vars_batch(token, service_id=cron_id, variables=CRON_VARS, dry_run=dry_run)

    print("Triggering deploy...")
    trigger_deploy(token, cron_id, dry_run=dry_run)

    print(f"\nDone. Service: {CRON_SERVICE_NAME} ({cron_id})")
    print("  Schedule: 30 16 * * * UTC (22:00 IST)")
    print("  Command: python scripts/auto_close_sessions_day_end.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
