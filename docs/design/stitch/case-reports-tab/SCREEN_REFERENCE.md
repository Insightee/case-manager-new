# Case Reports Tab — Stitch Screen Reference

Project: **Therapy Map & Clinical Planner** (`2676660861211267049`)

Download with Stitch MCP (`get_screen`) or:

```bash
curl -sS -X POST "https://stitch.googleapis.com/mcp" \
  -H "Content-Type: application/json" \
  -H "X-Goog-Api-Key: $STITCH_API_KEY" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_screen","arguments":{"projectId":"2676660861211267049","screenId":"<id>"}}}'
```

| Screen | ID | Folder | UI target |
|--------|-----|--------|-----------|
| Reports - Client Case View | `bd07d0c97e8b49d395f3a889a8e3d865` | `reports-client-case/` | `CaseReportsTab.jsx` (desktop) |
| Reports - Mobile View | `a922c4b5331f4abd8f1939209a89c6b5` | `reports-mobile/` | Same component (mobile stack) |
| Reports - Empty State | `af17897a468c45959e93200572371709` | `reports-empty/` | Empty state inside `CaseReportsTab` |
| Reports - Overdue Alert State | `9a660372c04f4f28aa14e12e5fc56824` | `reports-overdue/` | Attention + timeline overdue chips |

## Implementation files

| File | Role |
|------|------|
| `frontend/src/components/clinical/reports-tab/CaseReportsTab.jsx` | Orchestrator |
| `frontend/src/lib/caseReportsCompose.js` | Filter + route helpers |
| `frontend/src/hooks/useCaseReportsSummary.js` | React Query hook |
| `frontend/src/styles/case-reports-tab.css` | Forest Light styles (`crt-*`) |

## Parent shell

Rendered inside `CaseReportsHub` when `?tab=reports&section=dashboard` (default). Case header + tabs from `CaseProfileShell`.

## Design doc

See [DESIGN.md](./DESIGN.md).
