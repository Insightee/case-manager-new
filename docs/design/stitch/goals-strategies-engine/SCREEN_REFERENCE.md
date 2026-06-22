# Goals & Strategies Engine — Stitch Screen Reference

Project: **Observation Report Builder** (`5191405174740405927`)

Download with `STITCH_API_KEY` set:

```bash
# Example per screen (stitch-design-cli or @google/stitch-sdk)
stitch screen get --project-id 5191405174740405927 \
  --screen-id <id> --include-html --include-image --json
```

| Screen | ID | UI target |
|--------|-----|-----------|
| Session Log - Goals & Strategies (Desktop) | `1ae7c98f7c73480f9dec8810c4ccbba4` | Primary session log evidence panel |
| Session Log - Mobile Accordion | `682589d689af43a4bf67573430ad0f96` | Mobile goal card collapse |
| Session Log - Observation Phase (Desktop) | `c22700e2aa1d4546bee5bedb262d7d9f` | Activity / observation context |
| Goal & Strategy Engine - Clinical Workspace | `dc07d41613fd41a0a5e2e1cab365bec4` | Case profile goals/strategies |
| Create Goal - Overlay | `0fa5fd559a15480c800e5fde5b223b8b` | Custom goal modal |
| Add Strategy - Overlay | `e9d2511311f94d1d8a38b0b4e56364c0` | Custom strategy modal |
| AI Strategy Lab - Generation Workspace | `9de68072ad0f4bc99bbe32d053be4b45` | Deferred — gateway hooks only |

Implementation uses Forest Light / clinical-ui parity, not raw Stitch HTML.
