from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import ai_audit_service, ai_cost_guard, ai_prompt_registry
from app.services.clinical_insight_prompt_builder import build_insight_prompt


def _input_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


MOCK_SNAPSHOT_OUTPUT = {
    "snapshot_summary": (
        "Visual preparation appeared helpful during familiar classroom transitions. "
        "Functional communication has emerging notes but needs stronger structured evidence. "
        "Playground transitions may need additional environmental support."
    ),
    "goal_recommendations": [
        {
            "goal_title": "Transition participation",
            "recommendation": "Continue with adaptation",
            "evidence_strength": "moderate",
            "why": "Visual preparation appeared helpful in familiar classroom transitions.",
            "suggested_next_step": "Observe playground-to-classroom transition and record support level.",
            "source_ids": [],
        },
        {
            "goal_title": "Functional communication",
            "recommendation": "Needs stronger evidence",
            "evidence_strength": "weak",
            "why": "Notes mention communication attempts, but mode and context were not consistently tagged.",
            "suggested_next_step": "Capture communication mode and context in the next sessions.",
            "source_ids": [],
        },
    ],
    "strategy_signals": [
        {
            "strategy": "Visual countdown",
            "signal": "appeared_helpful",
            "context": "Familiar classroom transitions",
            "recommendation": "Continue and observe in playground transitions.",
        },
        {
            "strategy": "Verbal prompting only",
            "signal": "mixed",
            "context": "Transitions without preparation",
            "recommendation": "Review and consider visual/environmental preparation first.",
        },
    ],
    "support_accommodations": [
        "Prepare transitions before the environment becomes crowded.",
        "Offer a choice of route where possible.",
        "Allow extra processing time before changing activities.",
    ],
    "what_may_not_be_working": [
        {
            "observation": "Verbal prompting alone showed mixed response.",
            "suggested_review": "Consider visual or environmental preparation before repeated verbal prompts.",
        }
    ],
    "evidence_gaps": [
        "Functional communication has weak structured tagging.",
        "Some logs may be missing child response.",
        "Parent input may not be updated this month.",
    ],
    "parent_safe_draft": (
        "The child responded well when transitions were predictable and there was time to prepare. "
        "The team will continue observing what supports work best during busier transitions."
    ),
    "limitations": [
        "This is a draft and requires clinical review.",
        "Some goals may have limited structured evidence.",
    ],
    "requires_review": True,
    "parent_safe": False,
}


class AIGatewayService:
    """Provider-neutral AI gateway — mock-first."""

    @staticmethod
    def is_enabled() -> bool:
        return bool(settings.AI_ENABLED)

    @staticmethod
    def provider() -> str:
        return settings.AI_PROVIDER or "mock"

    @staticmethod
    def insights_model() -> str:
        return getattr(settings, "INSIGHTS_MODEL", None) or settings.AI_DEFAULT_MODEL or "mock-v1"

    @classmethod
    def _resolve_provider(cls) -> tuple[str, str | None]:
        provider = cls.provider() if cls.is_enabled() else "mock"
        warning = None
        if provider == "openai" and not getattr(settings, "OPENAI_API_KEY", ""):
            provider, warning = "mock", "API key missing; mock provider used."
        elif provider == "gemini" and not getattr(settings, "GEMINI_API_KEY", ""):
            provider, warning = "mock", "API key missing; mock provider used."
        return provider, warning

    @classmethod
    def preview(
        cls,
        db: Session,
        *,
        user_id: int,
        case_id: int | None,
        action: str,
        context: dict[str, Any],
        target_type: str = "generic",
        target_id: int | None = None,
    ) -> dict[str, Any]:
        try:
            action = ai_prompt_registry.validate_action(action)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        compressed = ai_cost_guard.compress_context(context)
        ih = _input_hash({"action": action, "context": compressed})

        cached = ai_audit_service.find_cached(db, action=action, input_hash=ih)
        if cached:
            return cached

        ai_cost_guard.check_rate_limit(user_id, action)
        ai_cost_guard.check_budget(db)
        preview_count = ai_audit_service.count_previews_today(db, user_id)
        if not ai_cost_guard.within_daily_limit(preview_count):
            raise HTTPException(
                status_code=429,
                detail="Daily AI preview limit reached — try again tomorrow or edit manually.",
            )

        provider, _ = cls._resolve_provider()
        model = cls.insights_model() if provider != "mock" else "mock-v1"
        draft_text = ai_prompt_registry.mock_draft(action, compressed)

        return ai_audit_service.record_generation(
            db,
            user_id=user_id,
            case_id=case_id,
            action=action,
            provider=provider,
            model=model,
            input_hash=ih,
            draft_text=draft_text,
            target_type=target_type,
            target_id=target_id,
        )

    @classmethod
    def _mock_snapshot(cls, summary: dict[str, Any], insight_type: str) -> dict[str, Any]:
        out = dict(MOCK_SNAPSHOT_OUTPUT)
        child = summary.get("case", {}).get("child_name") or "the child"
        if insight_type == "parent_safe_draft":
            out["parent_safe"] = True
            out["parent_safe_draft"] = (
                f"{child} responded well when transitions were predictable and there was time to prepare. "
                "The team will continue observing what supports work best during busier transitions."
            )
        gaps = summary.get("evidence_gaps") or []
        if gaps:
            out["evidence_gaps"] = gaps[:5]
        return out

    @classmethod
    def _call_provider_json(
        cls,
        provider: str,
        prompt: dict[str, Any],
        summary: dict[str, Any] | None = None,
        insight_type: str = "full_snapshot",
    ) -> tuple[dict[str, Any], int, int]:
        """Returns output dict, input tokens, output tokens."""
        if provider == "mock":
            out = cls._mock_snapshot(summary or {}, insight_type)
            text = json.dumps(out)
            return out, len(prompt.get("user", "").split()), len(text.split())

        if provider == "openai":
            return cls._call_openai(prompt)

        if provider == "gemini":
            return cls._call_gemini(prompt)

        out = cls._mock_snapshot({}, prompt.get("insight_type", "full_snapshot"))
        return out, 0, 0

    @classmethod
    def _call_openai(cls, prompt: dict[str, Any]) -> tuple[dict[str, Any], int, int]:
        try:
            import urllib.request

            api_key = getattr(settings, "OPENAI_API_KEY", "")
            model = cls.insights_model()
            body = json.dumps(
                {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": prompt["system"]},
                        {"role": "user", "content": prompt["user"]},
                    ],
                    "response_format": {"type": "json_object"},
                }
            ).encode()
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=body,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            content = data["choices"][0]["message"]["content"]
            out = json.loads(content)
            usage = data.get("usage", {})
            return out, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        except Exception:
            out = cls._mock_snapshot({}, prompt.get("insight_type", "full_snapshot"))
            out["provider_warning"] = "OpenAI call failed; mock output returned."
            return out, 0, 0

    @classmethod
    def _call_gemini(cls, prompt: dict[str, Any]) -> tuple[dict[str, Any], int, int]:
        try:
            import urllib.request

            api_key = getattr(settings, "GEMINI_API_KEY", "")
            model = cls.insights_model() or "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            body = json.dumps(
                {
                    "contents": [{"parts": [{"text": prompt["system"] + "\n\n" + prompt["user"]}]}],
                    "generationConfig": {"responseMimeType": "application/json"},
                }
            ).encode()
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            out = json.loads(content)
            return out, len(prompt["user"].split()), len(content.split())
        except Exception:
            out = cls._mock_snapshot({}, prompt.get("insight_type", "full_snapshot"))
            out["provider_warning"] = "Gemini call failed; mock output returned."
            return out, 0, 0

    @classmethod
    def generate_clinical_snapshot(
        cls,
        db: Session,
        *,
        user_id: int,
        case_id: int,
        summary: dict[str, Any],
        insight_type: str,
        role: str,
        references: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        ai_cost_guard.check_budget(db)
        ai_cost_guard.check_rate_limit(user_id, "clinical_snapshot")

        provider, warning = cls._resolve_provider()
        if not cls.is_enabled() and provider != "mock":
            provider = "mock"
            warning = "AI disabled; mock provider used."

        prompt = build_insight_prompt(summary, insight_type, role, references)
        out, tok_in, tok_out = cls._call_provider_json(provider, prompt, summary, insight_type)
        if warning:
            out["provider_warning"] = warning

        model = cls.insights_model() if provider != "mock" else "mock-v1"
        ih = _input_hash({"summary": summary, "insight_type": insight_type, "refs": references or []})

        log_result = ai_audit_service.record_generation(
            db,
            user_id=user_id,
            case_id=case_id,
            action="clinical_snapshot",
            provider=provider,
            model=model,
            input_hash=ih,
            draft_text=out.get("snapshot_summary") or json.dumps(out)[:4000],
            target_type="clinical_snapshot",
            target_id=None,
        )

        cost = ai_cost_guard.estimate_cost(tok_in, tok_out, provider)
        return {
            "output": out,
            "provider": provider,
            "model": model,
            "input_hash": ih,
            "token_input_count": tok_in,
            "token_output_count": tok_out,
            "estimated_cost": cost,
            "generation_log_id": log_result.get("log_id"),
        }

    @classmethod
    def answer_snapshot_followup(
        cls,
        db: Session,
        *,
        user_id: int,
        case_id: int,
        question: str,
        snapshot_text: str = "",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ai_cost_guard.check_budget(db)
        provider, warning = cls._resolve_provider()
        ctx_json = json.dumps(context or {}, default=str)[:4000]
        snapshot_part = snapshot_text[:2000] if snapshot_text else "No weekly refresh snapshot yet."
        answer = (
            f"Based on structured case context"
            + (f" and your weekly refresh" if snapshot_text else "")
            + f": regarding \"{question[:120]}\" — review recent session evidence and goal/strategy tags. "
            "Say \"not enough evidence\" when logs are thin."
        )
        if provider == "mock":
            if warning:
                answer = f"{answer} ({warning})"
            return {"answer": answer, "provider": "mock", "model": "mock-v1"}

        prompt = {
            "system": (
                "You are a clinical documentation assistant for InsighteCase. "
                "Answer briefly using ONLY the structured context provided. "
                "No diagnosis. Use neuro-affirmative language. "
                "Prefer: appeared helpful, mixed evidence, needs review, not enough evidence. "
                "Avoid: failed, non-compliant, deficit framing."
            ),
            "user": (
                f"Structured context:\n{ctx_json}\n\n"
                f"Weekly refresh snapshot (if any):\n{snapshot_part}\n\n"
                f"Question: {question[:500]}\n\n"
                "Return JSON: {\"answer\": \"your brief reply\"}"
            ),
            "insight_type": "followup",
        }
        out, _, model = cls._call_provider_json(provider, prompt, {}, "followup")
        text = out.get("answer") or out.get("snapshot_summary") or answer
        return {"answer": text, "provider": provider, "model": model}

    @staticmethod
    def input_hash_for_payload(payload: dict[str, Any]) -> str:
        return _input_hash(payload)

    @classmethod
    def generate_parent_safe_draft(cls, db: Session, *, user_id: int, case_id: int, summary: dict[str, Any]) -> dict[str, Any]:
        result = cls.generate_clinical_snapshot(
            db,
            user_id=user_id,
            case_id=case_id,
            summary=summary,
            insight_type="parent_safe_draft",
            role="therapist",
        )
        return result

    @classmethod
    def improve_session_log_note(cls, db: Session, *, user_id: int, case_id: int, note: str, child_name: str) -> dict[str, Any]:
        return cls.preview(
            db,
            user_id=user_id,
            case_id=case_id,
            action="improve_session_note",
            context={"text": note, "child_name": child_name},
            target_type="session_log",
        )

    @classmethod
    def generate_report_section(
        cls, db: Session, *, user_id: int, case_id: int, section: str, summary: dict[str, Any]
    ) -> dict[str, Any]:
        return cls.generate_clinical_snapshot(
            db,
            user_id=user_id,
            case_id=case_id,
            summary=summary,
            insight_type="report_support",
            role="therapist",
        )

    @classmethod
    def suggest_iep_goal_supports(
        cls, db: Session, *, user_id: int, case_id: int, summary: dict[str, Any]
    ) -> dict[str, Any]:
        return cls.generate_clinical_snapshot(
            db,
            user_id=user_id,
            case_id=case_id,
            summary=summary,
            insight_type="iep_support",
            role="therapist",
        )
