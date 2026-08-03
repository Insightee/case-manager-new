#!/usr/bin/env bash
# Carve non-finance clinical/reports WIP from wip/local-preserve-20260803
# onto the current branch (expected: staging/stabilisation-pre-reports tip).
#
# Prerequisites:
#   git fetch origin wip/local-preserve-20260803
#   git checkout staging/stabilisation-pre-reports
#   git reset --hard origin/staging/stabilisation-pre-reports
#
# Usage (from repo root):
#   ./scripts/carve-reports-from-wip-preserve.sh
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

WIP_REF="${WIP_REF:-origin/wip/local-preserve-20260803}"
if ! git rev-parse --verify "$WIP_REF" >/dev/null 2>&1; then
  echo "Missing $WIP_REF. On your Mac, run the preserve snapshot first:" >&2
  echo "  git checkout -b wip/local-preserve-20260803" >&2
  echo "  git add -A && git commit -m 'chore(wip): preserve local working tree before reports carve'" >&2
  echo "  git push -u origin wip/local-preserve-20260803" >&2
  exit 1
fi

echo "==> Checking out REPORTS_CLINICAL paths from $WIP_REF"

REPORTS_PATHS=(
  # New backend services
  backend/app/services/clinical_language_engine_service.py
  backend/app/services/insights/insights_ask_service.py
  backend/app/services/insights/insights_chat_usage_limiter.py
  backend/app/services/progress_evidence_scope_service.py
  backend/app/services/progress_legacy_read_service.py
  backend/app/services/progress_report_service.py
  backend/app/services/progress_review_service.py
  backend/app/services/progress_status_rules.py
  backend/app/services/session_analytics_event_service.py
  backend/app/services/session_clinical_insight_service.py
  backend/app/services/session_context_builder.py
  backend/app/services/session_longitudinal_aggregator.py
  # Tests
  backend/app/tests/test_clinical_language_engine.py
  backend/app/tests/test_insights_ask.py
  backend/app/tests/test_progress_report_service.py
  backend/app/tests/test_session_clinical_insight.py
  # API glue (differs on staging)
  backend/app/api/v1/clinical_reports.py
  backend/app/api/v1/daily_logs.py
  backend/app/api/v1/insights_routes.py
  backend/app/api/v1/reports.py
  backend/app/api/v1/session_voice.py
  # Schemas / constants / existing services ahead of staging
  backend/app/report_engine_constants.py
  backend/app/schemas/structured_session_evidence.py
  backend/app/schemas/voice_session_log.py
  backend/app/services/ai_gateway_service.py
  backend/app/services/case_reports_summary_service.py
  backend/app/services/insights/ai_insight_refresh_service.py
  backend/app/services/parent_canonical_report_service.py
  backend/app/services/parent_reports_service.py
  backend/app/services/report_engine_service.py
  backend/app/services/report_status_service.py
  backend/app/services/session_log_application_service.py
  backend/app/services/session_log_extraction_service.py
  backend/app/services/voice_session_log_service.py
  # Frontend progress UI
  frontend/src/components/reports-engine/hooks/useProgressReport.js
  frontend/src/components/reports-engine/progress
  # Frontend case reports / insights / voice
  frontend/src/components/case-profile/CaseReportsHub.jsx
  frontend/src/components/clinical/insights-v2/CaseInsightsTab.jsx
  frontend/src/components/clinical/insights-v2/InsightsAskPanel.jsx
  frontend/src/components/clinical/insights-v2/InsightsRefreshBar.jsx
  frontend/src/components/clinical/insights-v2/InsightsSubTabBar.jsx
  frontend/src/components/daily-logs/DailyLogsPage.jsx
  frontend/src/components/daily-logs/ForgotSessionForm.jsx
  frontend/src/components/daily-logs/voice/ChallengesAndConcerns.jsx
  frontend/src/components/daily-logs/voice/ClinicalBrainInsightPanel.jsx
  frontend/src/components/daily-logs/voice/EmergingGoalCandidates.jsx
  frontend/src/components/daily-logs/voice/IepGoalsSection.jsx
  frontend/src/components/daily-logs/voice/SessionContextHeader.jsx
  frontend/src/components/daily-logs/voice/StrategiesUsedSection.jsx
  frontend/src/components/daily-logs/voice/VoiceDraftTopBar.jsx
  frontend/src/components/daily-logs/voice/VoiceFlowFooter.jsx
  frontend/src/components/daily-logs/voice/VoiceProcessingScreen.jsx
  frontend/src/components/daily-logs/voice/VoiceReviewAccordion.jsx
  frontend/src/components/daily-logs/voice/VoiceReviewSummary.jsx
  frontend/src/components/daily-logs/voice/VoiceSessionLogFlow.jsx
  frontend/src/components/daily-logs/voice/VoiceSessionPreviewScreen.jsx
  frontend/src/components/daily-logs/voice/VoiceStoryDraftScreen.jsx
  frontend/src/components/daily-logs/voice/voice-session-log-stitch.css
  frontend/src/components/therapist/TherapistSessionComposer.jsx
  frontend/src/hooks/useCaseInsightsAsk.js
  frontend/src/lib/queryClient.js
  frontend/src/lib/sessionStartRules.js
  frontend/src/lib/structuredSessionEvidence.js
  frontend/src/lib/structuredSessionEvidence.test.js
  frontend/src/lib/voiceExtractionMapper.js
  frontend/src/styles/case-insights-v2.css
  frontend/src/styles/session-logs-dashboard.css
  frontend/index.html
  # PWA / favicons (from WIP; favicon.svg may be deleted)
  frontend/public/apple-touch-icon.png
  frontend/public/favicon-16x16.png
  frontend/public/favicon-32x32.png
  frontend/public/favicon-source.png
  frontend/public/favicon.ico
  frontend/public/favicon.png
  frontend/public/icon-192.png
  frontend/public/icon-512.png
  frontend/public/site.webmanifest
  # Docs (clinical only)
  docs/CLINICAL_HANDOVER.md
  docs/PROGRESS_REPORT_RULES.md
  docs/REPORT_ARCHITECTURE.md
  docs/design/stitch/insights-tab/DESIGN.md
  docs/design/stitch/voice-session-log-v2/DESIGN.md
  docs/design/stitch/voice-session-log-v2/SCREEN_REFERENCE.md
  docs/product/VOICE_SESSION_V2_IMPLEMENTATION_MAP.md
)

# Checkout only paths that exist in the WIP tree
existing=()
missing=()
for p in "${REPORTS_PATHS[@]}"; do
  if git cat-file -e "$WIP_REF:$p" 2>/dev/null || git ls-tree -r --name-only "$WIP_REF" -- "$p" | grep -q .; then
    existing+=("$p")
  else
    missing+=("$p")
  fi
done

if ((${#existing[@]})); then
  git checkout "$WIP_REF" -- "${existing[@]}"
fi

# Intentional delete: old progress section replaced by ProgressReportRoute
if git cat-file -e "HEAD:frontend/src/components/case-profile/sections/CaseProgressReportsSection.jsx" 2>/dev/null; then
  if ! git cat-file -e "$WIP_REF:frontend/src/components/case-profile/sections/CaseProgressReportsSection.jsx" 2>/dev/null; then
    git rm -f frontend/src/components/case-profile/sections/CaseProgressReportsSection.jsx || true
  fi
fi

# Favicon.svg deleted in WIP
if git cat-file -e "HEAD:frontend/public/favicon.svg" 2>/dev/null; then
  if ! git cat-file -e "$WIP_REF:frontend/public/favicon.svg" 2>/dev/null; then
    git rm -f frontend/public/favicon.svg || true
  fi
fi

echo "==> Restoring Coming Soon gates from HEAD (do not take WIP deletes)"
git checkout HEAD -- \
  frontend/src/components/shared/PortalModuleRolloutNotice.jsx \
  frontend/src/components/shared/portal-module-rollout-notice.css \
  frontend/src/layouts/PortalShell.jsx \
  frontend/src/lib/productFeatureFlags.js \
  2>/dev/null || true

echo "==> Applying clinical-only hunks for shared files from WIP (patch filter)"

apply_clinical_shared() {
  local path="$1"
  if ! git cat-file -e "$WIP_REF:$path" 2>/dev/null; then
    echo "  skip missing $path"
    return
  fi
  # Take WIP version for known clinical-only shared files (verified in plan triage)
  case "$path" in
    backend/app/core/config.py|backend/app/core/feature_flags.py|docs/ENVIRONMENT_VARIABLES.md)
      git checkout "$WIP_REF" -- "$path"
      echo "  took clinical shared: $path"
      ;;
  esac
}

apply_clinical_shared backend/app/core/config.py
apply_clinical_shared backend/app/core/feature_flags.py
apply_clinical_shared docs/ENVIRONMENT_VARIABLES.md

echo "==> Stripping finance bullets from CHANGELOG if present from WIP"
if git cat-file -e "$WIP_REF:CHANGELOG.md" 2>/dev/null; then
  git show "$WIP_REF:CHANGELOG.md" > /tmp/changelog_wip.md
  # Keep staging CHANGELOG as base; append clinical Unreleased bullets from WIP via Python
  python3 - <<'PY'
from pathlib import Path
import re

staging = Path("CHANGELOG.md").read_text()
wip = Path("/tmp/changelog_wip.md").read_text()

def unreleased_block(text: str) -> str:
    m = re.search(r"## \[Unreleased\]\n(.*?)(?=\n## \[|\Z)", text, re.S)
    return m.group(1) if m else ""

wip_u = unreleased_block(wip)
# Keep only non-billing clinical lines from WIP Unreleased
keep_lines = []
skip_billing = False
for line in wip_u.splitlines():
    low = line.lower()
    if any(k in low for k in ("billing step", "monthly_fixed", "ledger", "period charge", "retainer", "pay share", "allotment wizard monthly")):
        continue
    if line.strip().startswith("- ") or line.strip().startswith("###") or not line.strip():
        keep_lines.append(line)
    else:
        keep_lines.append(line)

clinical = "\n".join(keep_lines).strip()
if not clinical:
    print("No clinical CHANGELOG lines detected; leaving staging CHANGELOG")
    raise SystemExit(0)

# Merge: ensure clinical bullets exist under staging Unreleased Added/Fixed
if "Voice Session Log V2" in staging and "Insights Ask" in staging:
    print("Staging CHANGELOG already has clinical notes; leaving as-is")
    raise SystemExit(0)

# Insert clinical block after ## [Unreleased]
inserted = re.sub(
    r"(## \[Unreleased\]\n)",
    r"\1\n### Added (from WIP carve)\n" + clinical + "\n\n",
    staging,
    count=1,
)
Path("CHANGELOG.md").write_text(inserted)
print("Merged clinical CHANGELOG bullets")
PY
fi

echo "==> Guard: finance / loop / exports must not be staged"
FORBIDDEN_PATTERNS=(
  'backend/alembic/versions/a4b5c6d7e8f9'
  'backend/alembic/versions/y2z3a4b5c6d7'
  'backend/alembic/versions/z3a4b5c6d7e8'
  'billing_step6'
  'ledger_billing.py'
  'billing_ledger_service'
  'test_billing_'
  'test_period_charge'
  'test_monthly_billing'
  'docs/LOOP_SYSTEM.md'
  'scripts/grind-check.sh'
  'docs/plans/finance'
  'docs/initiatives/finance'
  'docs/design/finance-ui-screenshots'
  'exports/insightecase_'
  'exports/july_2026'
  'exports/monthly_case_review'
  'export_case_attendance'
  'export_case_leave'
  'export_case_manager'
  'export_therapist_monthly'
  'verify_july_2026'
  'staging_step5_eligibility'
  'AdminCaseAllotmentWizard'
  'backend/app/core/database.py'
)

bad=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  for pat in "${FORBIDDEN_PATTERNS[@]}"; do
    if [[ "$f" == *"$pat"* ]]; then
      echo "FORBIDDEN staged path: $f" >&2
      git reset HEAD -- "$f" 2>/dev/null || true
      git checkout HEAD -- "$f" 2>/dev/null || true
      rm -rf "$f" 2>/dev/null || true
      bad=1
    fi
  done
done < <(git diff --cached --name-only; git status --porcelain | awk '{print $2}')

# Drop stitch screen dumps if accidentally present
find docs/design/stitch/voice-session-log-v2 -type f \( -name 'code.html' -o -name 'screen.png' -o -name 'title.txt' \) -print -delete 2>/dev/null || true

echo "==> Status after carve"
git status --short | head -80
echo "missing_optional_paths=${#missing[@]}"
if ((${#missing[@]})); then
  printf '  %s\n' "${missing[@]}" | head -40
fi
echo "Done. Review, commit, then verify with agent-pytest + npm run build."
