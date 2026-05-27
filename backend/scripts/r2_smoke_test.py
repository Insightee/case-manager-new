#!/usr/bin/env python3
"""Verify R2 S3 credentials (put/get/delete). Reads env only — no secrets in repo."""
from __future__ import annotations

import os
import sys

import boto3
from botocore.config import Config


def main() -> int:
    required = (
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_ENDPOINT_URL",
        "R2_BUCKET_NAME",
    )
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print("Missing:", ", ".join(missing), file=sys.stderr)
        return 1

    key = "insightcase/production/_smoke/r2-ok.txt"
    body = b"r2-smoke-ok"
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    bucket = os.environ["R2_BUCKET_NAME"]
    client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="text/plain")
    got = client.get_object(Bucket=bucket, Key=key)["Body"].read()
    client.delete_object(Bucket=bucket, Key=key)
    if got != body:
        print("get mismatch", file=sys.stderr)
        return 1
    print(f"R2 OK: bucket={bucket}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
