#!/usr/bin/env bash
# Regenerate docs/THERAPIST_PORTAL_GUIDE.pdf from the Markdown source.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
node scripts/generate-therapist-guide-pdf.mjs
