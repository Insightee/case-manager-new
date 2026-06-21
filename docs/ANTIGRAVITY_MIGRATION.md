# Migrating InsighteCase to Google Antigravity

_Last updated: June 2026 — covers developer toolchain (Antigravity CLI / IDE), agent skills, and optional UI design direction._

**Related:** [AGENTS.md](../AGENTS.md) · [AGENT_WORKFLOW.md](./AGENT_WORKFLOW.md) · [ARCHITECTURE.md](./ARCHITECTURE.md) · [CTO_DIRECTION_AND_DESIGN.md](./CTO_DIRECTION_AND_DESIGN.md) · [sessions/3264f04a-therapist-ux-merge-session-summary.md](./sessions/3264f04a-therapist-ux-merge-session-summary.md)

---

## What “Antigravity” means here

This doc covers **two related but separate** migrations:

| Layer | What it is | Priority for InsighteCase |
|-------|------------|---------------------------|
| **Google Antigravity platform** | Agent-first dev environment: Antigravity CLI (`agy`), Antigravity 2.0 IDE, sub-agents, plugins | **Required** for teams on Gemini CLI / Code Assist (consumer) before **June 18, 2026** |
| **Antigravity design language** | Spatial, glassmorphism, GSAP motion UI (see `antigravity-design-expert` skill) | **Optional phased** visual upgrade on marketing/login and selected hero surfaces—not a full portal rewrite |

Do **not** confuse Google’s platform migration with a mandatory frontend framework change. Production portals stay **Vite + React + Tailwind** on Vercel; API stays **FastAPI** on Railway.

---

## Part 1 — Google Antigravity platform migration

### Deadline and audience

- **June 18, 2026:** Gemini CLI and Gemini Code Assist IDE extensions stop serving requests for **free, Google AI Pro, and Google AI Ultra** accounts.
- **Enterprise / Gemini Code Assist Standard+** licenses: Gemini CLI continues; Antigravity is optional.
- Official notice: [Google Developers Blog — Transitioning Gemini CLI to Antigravity CLI](https://developers.googleblog.com/en/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)

### Install Antigravity CLI

```bash
# Install agy (binary name is agy, not antigravity)
# Follow current install instructions at https://antigravity.google/

agy   # first run → browser OAuth with your Google account
```

**Note:** If the Antigravity **desktop app** is installed, its `agy` binary may conflict with CLI on Linux/macOS. Use a symlink or PATH order so the CLI you intend is the one invoked.

### One-command import from Gemini CLI

```bash
agy plugin import gemini
```

This migrates extensions from `~/.gemini/extensions/` to Antigravity plugins. Node-only extensions may need author updates.

### Config mapping (Gemini → Antigravity)

| Gemini CLI | Antigravity CLI | InsighteCase action |
|------------|-----------------|---------------------|
| `~/.gemini/settings.json` (inline MCP) | `mcp_config.json` (`serverUrl` not `url`) | Copy MCP entries; test Postgres/Redis tools if used |
| `.gemini/skills/` (workspace) | `.agents/skills/` | **Move project skills** into repo `.agents/skills/insightecase/` |
| Global skills | `~/.agents/skills/` | Install global skill `insightecase-case-manager` (see below) |
| `GEMINI.md` | Still read | Optional; **prefer `AGENTS.md`** (already in repo root) |
| `AGENTS.md` | Still read | **Source of truth** for this monorepo |
| Hooks / subagents | Supported | Port hook scripts; validate on `case-manager-new-1` before deleting Gemini config |

Example `mcp_config.json` shape (adjust URLs to your MCP servers):

```json
{
  "mcpServers": {
    "example": {
      "serverUrl": "http://localhost:3000/mcp",
      "headers": {}
    }
  }
}
```

### Cursor + Antigravity together

Many contributors use **Cursor** (this repo’s primary agent surface) **and** Antigravity CLI in terminal:

| Concern | Cursor | Antigravity |
|---------|--------|-------------|
| Project rules | `AGENTS.md`, `.cursor/rules/` | `AGENTS.md`, `.agents/skills/` |
| Skills | `~/.cursor/skills*`, plugins | `~/.agents/skills/`, `.agents/skills/` |
| MCP | Cursor MCP config | `mcp_config.json` |
| Commits | User must ask explicitly | Same team norm—see [CONTRIBUTING.md](../CONTRIBUTING.md) |

**Keep both in sync:** when you update `AGENTS.md` or add a workspace skill under `.agents/skills/insightecase/`, mirror critical rules in Cursor rules if the team relies on both tools.

### Repo-specific Antigravity workspace setup

From monorepo root:

```bash
cd case-manager-new-1

# 1. Workspace skill (committed — for all Antigravity users)
ls .agents/skills/insightecase/SKILL.md

# 2. Read agent + CTO context
cat AGENTS.md
cat docs/CTO_DIRECTION_AND_DESIGN.md

# 3. Local API + UI (same as Cursor workflow)
cd backend && python3 -m app.seed.demo_seed && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev   # :5173, /api proxied

# 4. Pre-push gate (required before PR)
./scripts/pre-push-check.sh
```

### CI / deploy (unchanged by Antigravity)

Antigravity does **not** replace Railway or Vercel:

| Platform | Service | Env |
|----------|---------|-----|
| **Railway** | `case-manager-new` API | All secrets, `DATABASE_URL`, SMTP |
| **Vercel** | `insightes-projects/frontend` only | `VITE_API_URL` only |

See [RAILWAY_VERCEL.md](./RAILWAY_VERCEL.md). After schema changes, production applies migrations on API boot via `backend/scripts/migrate_production.py`.

### Migration checklist (team)

- [ ] Install `agy` and complete OAuth
- [ ] Run `agy plugin import gemini` (if coming from Gemini CLI)
- [ ] Move workspace skills to `.agents/skills/`
- [ ] Create `mcp_config.json`; rename MCP `url` → `serverUrl`
- [ ] Verify `AGENTS.md` loads in Antigravity session
- [ ] Run `./scripts/pre-push-check.sh` once locally
- [ ] Decommission `gemini` binary for consumer accounts before **2026-06-18**
- [ ] Document any personal MCP tokens in 1Password—not in git

### Parallel run window (recommended)

| Week | Action |
|------|--------|
| Week 1 | Install `agy`, import plugins, copy skills |
| Week 2 | Run both `gemini` and `agy` on non-critical tasks |
| Week 3 | Default to `agy`; keep Gemini only as fallback |
| By 2026-06-18 | Gemini consumer path off; Antigravity or Cursor only |

---

## Part 2 — Optional UI “Antigravity design” migration

**CTO call:** Apply Antigravity **visual language** only where it improves trust and delight without hurting **data density** on admin/therapist operational screens.

### Where to apply (phased)

| Phase | Surfaces | Motion / depth |
|-------|----------|----------------|
| **A — Brand** | Login, marketing hero, empty states | Light glass cards, staggered entrance, `prefers-reduced-motion` safe |
| **B — Therapist mobile** | Session composer sheets, booking success, quick actions | Floating sheets, soft shadows—not isometric tilt on forms |
| **C — Admin** | Workbench highlights, KPI strips only | Subtle parallax on headers; **keep tables dense** |
| **Defer** | Invoice grids, session log approval queues, kanban | No scroll hijacking; no 3D transforms on data tables |

### Technical constraints (production)

- **Stack stays:** React 19 + Vite + Tailwind; add GSAP only behind lazy imports for animated routes.
- **Performance:** Animate `transform` / `opacity` only; avoid continuous `filter` / `box-shadow` animation.
- **Accessibility:** Honor `prefers-reduced-motion: reduce`; maintain 44px touch targets ([admin-mobile-ux.md](../frontend/docs/admin-mobile-ux.md)).
- **Brand colors:** Keep Insighte teal `#0d9488` / `#0f766e`; glass layers use `backdrop-filter` with sufficient contrast (existing pattern in `frontend/src/index.css`).

### Where not to go

- Do not rebuild portals in Next.js solely for Antigravity design skill defaults.
- Do not replace operational CSS (`my-cases.css`, `admin-sessions-dashboard.css`) with isometric grids.
- Do not block pilot on R3F / Three.js unless a specific marketing page requires it.

Detailed design principles and feedback from the June 2026 therapist UX pass: [CTO_DIRECTION_AND_DESIGN.md](./CTO_DIRECTION_AND_DESIGN.md).

---

## Part 3 — Global skill installation

### Project skill (committed)

Path: [`.agents/skills/insightecase/SKILL.md`](../.agents/skills/insightecase/SKILL.md)

Antigravity loads workspace skills from `.agents/skills/`. Commit this directory so every clone gets the same CTO + delivery rules.

### Global skill (per developer machine)

Path: `~/.agents/skills/insightecase-case-manager/SKILL.md`

Copy from repo after clone:

```bash
mkdir -p ~/.agents/skills/insightecase-case-manager
cp .agents/skills/insightecase/SKILL.md ~/.agents/skills/insightecase-case-manager/SKILL.md
```

Or symlink for auto-updates:

```bash
ln -sf "$(pwd)/.agents/skills/insightecase" ~/.agents/skills/insightecase-case-manager
```

---

## Part 4 — Session history archive

| File | Description |
|------|-------------|
| [sessions/3264f04a-7f89-412c-a5f2-4a866995b3e1.jsonl](./sessions/3264f04a-7f89-412c-a5f2-4a866995b3e1.jsonl) | Full Cursor agent transcript (~22 MB JSONL) |
| [sessions/3264f04a-therapist-ux-merge-session-summary.md](./sessions/3264f04a-therapist-ux-merge-session-summary.md) | Human-readable digest of major decisions and shipped work |

**Git note:** The raw JSONL is large. If the team does not want it in git history, add `docs/sessions/*.jsonl` to `.gitignore` and store the archive in Drive/Notion instead. The summary markdown is the lightweight alternative.

---

## References

- [Google Antigravity CLI migration (community guide)](https://avinashsangle.com/blog/gemini-cli-to-antigravity-cli-guide)
- [ARCHITECTURE.md](./ARCHITECTURE.md) — CTO system view
- [PRODUCT_ROADMAP.md](./PRODUCT_ROADMAP.md) — P0–P3 priorities
- [AGENT_WORKFLOW.md](./AGENT_WORKFLOW.md) — agent delivery preferences from chats
- Antigravity UI skill: `~/.agents/skills/antigravity-design-expert/SKILL.md`
