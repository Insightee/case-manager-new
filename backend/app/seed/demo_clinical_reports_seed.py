"""Demo observation + IEP reports for Aarav (IC-2026-041) and Ira (IC-2026-053)."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.clinical_evidence import IepGoalCard, SessionGoalEntry
from app.models.clinical_report import ClinicalReportSection, ClinicalReportStatus
from app.models.goal_repository import GoalRepositoryItem, StrategyRepositoryItem
from app.models.daily_log import DailyLog
from app.models.iep_plan import IepPlan, IepPlanStatus
from app.models.session import Session as TherapySession
from app.models.user import User
from app.services import iep_report_service, observation_report_service, report_engine_service, report_status_service


def _patch_obs(db, report, key: str, text: str, structured: dict | None = None) -> None:
    report_engine_service.patch_section(
        db,
        report,
        key,
        narrative_text=text,
        structured_data=structured,
    )


def _seed_observation_case(
    db: Session,
    case: Case,
    therapist: User,
    cm: User,
    *,
    sections: dict[str, str],
    structured: dict[str, dict],
    goals: list[dict],
    strategies: list[dict],
) -> None:
    obs = report_engine_service.get_or_create_observation_report(db, case, therapist)
    report_engine_service.seed_observation_sections(db, obs.id)
    if obs.status in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value):
        return

    for key, text in sections.items():
        struct = structured.get(key)
        _patch_obs(db, obs, key, text, struct)

    goal_rows = []
    for g in goals:
        existing = db.scalars(
            select(GoalRepositoryItem).where(
                GoalRepositoryItem.source_clinical_report_id == obs.id,
                GoalRepositoryItem.label == g["label"],
            )
        ).first()
        if existing:
            goal_rows.append(existing)
            continue
        row = observation_report_service.create_goal_candidate(
            db,
            obs,
            therapist,
            label=g["label"],
            domain_key=g["domain_key"],
            baseline_note=g.get("baseline", ""),
            desired_direction=g.get("desired", ""),
        )
        row.goal_statement = g.get("statement") or g["label"]
        goal_rows.append(row)

    for s in strategies:
        if db.scalars(
            select(StrategyRepositoryItem).where(
                StrategyRepositoryItem.source_clinical_report_id == obs.id,
                StrategyRepositoryItem.label == s["label"],
            )
        ).first():
            continue
        observation_report_service.create_strategy_candidate(
            db,
            obs,
            therapist,
            label=s["label"],
            description=s.get("description", ""),
            domain_key=s.get("domain_key"),
        )

    if obs.status != ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value:
        report_status_service.submit_report(db, obs, therapist, readiness_ok=True)
    if obs.status == ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value:
        report_status_service.approve_report(db, obs, cm)


def _seed_session_log_goals(db: Session, case: Case, therapist: User, entries: list[dict]) -> None:
    logs = list(
        db.scalars(
            select(DailyLog)
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .where(TherapySession.case_id == case.id)
            .order_by(TherapySession.scheduled_date.desc())
            .limit(3)
        ).all()
    )
    if not logs:
        return
    for i, spec in enumerate(entries):
        log = logs[i % len(logs)]
        session = db.get(TherapySession, log.session_id)
        exists = db.scalars(
            select(SessionGoalEntry).where(
                SessionGoalEntry.daily_log_id == log.id,
                SessionGoalEntry.goal_label == spec["label"],
            )
        ).first()
        if exists:
            continue
        db.add(
            SessionGoalEntry(
                daily_log_id=log.id,
                session_id=session.id if session else None,
                case_id=case.id,
                child_id=case.child_id,
                created_by_user_id=therapist.id,
                goal_label=spec["label"],
                domain_key=spec.get("domain_key"),
                participation="emerging_participation",
                independence_support_needed="moderate_support",
                goal_achievement="emerging",
                visibility="INTERNAL_ONLY",
            )
        )
    db.flush()


def _seed_iep_draft(db: Session, case: Case, therapist: User) -> None:
    iep = report_engine_service.get_active_iep_report(db, case.id)
    if not iep:
        iep = iep_report_service.start_iep(db, case, therapist)
    if iep.status in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value):
        return
    iep_report_service.generate_iep_draft_from_observation(db, iep, therapist)

    plan = db.scalars(select(IepPlan).where(IepPlan.case_id == case.id)).first()
    if not plan:
        plan = IepPlan(
            case_id=case.id,
            version="v1",
            status=IepPlanStatus.DRAFT.value,
            created_by_user_id=therapist.id,
        )
        db.add(plan)
        db.flush()

    sec = db.scalars(
        select(ClinicalReportSection).where(
            ClinicalReportSection.report_id == iep.id,
            ClinicalReportSection.section_key == "goals_plan",
        )
    ).first()
    if not sec:
        return
    data = json.loads(sec.structured_data_json or "{}")
    for i, g in enumerate(data.get("goals", [])):
        label = g.get("title") or g.get("goal_statement")
        if not label:
            continue
        card = db.scalars(
            select(IepGoalCard).where(IepGoalCard.case_id == case.id, IepGoalCard.label == label)
        ).first()
        if card:
            continue
        db.add(
            IepGoalCard(
                iep_plan_id=plan.id,
                case_id=case.id,
                domain_key=g.get("domain") or "general",
                label=label,
                goal_statement=g.get("goal_statement") or label,
                baseline=g.get("baseline_current_state"),
                status="active",
                sort_order=i,
                settings_json=json.dumps({"iep_goal_id": g.get("iep_goal_id"), "clinical_report_id": iep.id}),
            )
        )
    db.flush()



def seed_demo_clinical_reports(
    db: Session,
    case_aarav: Case,
    case_ira: Case,
    therapist: User,
    case_mgr: User,
) -> None:
    """Idempotent demo clinical data for therapist + parent portals."""
    aarav_sections = {
        "child_snapshot": (
            "Aarav is a curious 9-year-old who engages warmly one-to-one and shows strong visual memory. "
            "He participates best when transitions are previewed and sensory load is managed."
        ),
        "referral_background": (
            "Referred for shadow support to build classroom participation, peer connection, and regulation "
            "during unstructured times."
        ),
        "strengths_interests": (
            "Enjoys drawing, puzzles, and structured games. Remembers visual schedules and responds well to "
            "positive reinforcement."
        ),
        "communication": (
            "Uses short phrases to request and comment. Benefits from wait time and visual conversation supports."
        ),
        "regulation_sensory": (
            "Sensitive to loud cafeteria noise. Calms with quiet corner breaks and predictable countdown timers."
        ),
        "participation": (
            "Joins circle time with a peer buddy. Needs a visual cue before whole-group transitions."
        ),
        "learning_access": (
            "Accesses grade-level tasks with modified instructions and chunked worksheets."
        ),
        "peer_interaction": (
            "Initiates play with one familiar peer. Working on maintaining back-and-forth during group games."
        ),
        "strategies_tried": (
            "Visual schedule with tactile countdown, peer buddy introduction, and first-then boards showed positive response."
        ),
        "support_needs": (
            "Emerging barrier: high auditory load in cafeteria and assembly. Needs preview before transitions."
        ),
        "clinical_summary": (
            "Aarav shows meaningful participation with structure, visual supports, and regulated environments. "
            "Priority areas: social initiation, transitions, and sensory regulation."
        ),
        "recommendations_iep": (
            "Develop IEP goals for peer interaction, classroom transitions, and communication initiation with "
            "linked visual and social strategies."
        ),
        "environment_notes": (
            "General classroom, cafeteria, and playground each need distinct accommodation notes."
        ),
    }
    aarav_structured = {
        "strengths_interests": {
            "strengths": ["Visual learning", "Strong memory", "Creative play"],
            "interests": ["Drawing", "Puzzles", "Board games"],
        },
        "support_needs": {
            "support_needs": ["Transition previews", "Quiet sensory breaks", "Peer scaffolding"],
        },
    }
    aarav_goals = [
        {
            "label": "Social interaction: initiation with peers",
            "domain_key": "peer_interaction",
            "statement": "During structured play, Aarav will initiate interaction with a peer using a greeting or question in 3 of 5 opportunities.",
            "baseline": "Initiates with familiar peer 1:1; rarely in group.",
            "desired": "Initiate with peer in small group twice per week.",
        },
        {
            "label": "Classroom transitions with visual support",
            "domain_key": "regulation_sensory",
            "statement": "Aarav will transition between classroom activities using a visual countdown with moderate support in 4 of 5 transitions.",
            "baseline": "Needs verbal and physical prompting for transitions.",
            "desired": "Independent transition with visual cue only.",
        },
    ]
    aarav_strategies = [
        {
            "label": "Visual countdown timer",
            "description": "Show 3-minute visual countdown before transitions; pair with calm verbal preview.",
            "domain_key": "regulation_sensory",
        },
        {
            "label": "Peer buddy introduction",
            "description": "Structured greeting script with assigned peer before group activities.",
            "domain_key": "peer_interaction",
        },
    ]

    ira_sections = {
        "child_snapshot": (
            "Ira is an energetic 7-year-old who thrives in familiar home routines and responds to playful coaching."
        ),
        "referral_background": "Homecare support for daily living skills, emotional regulation, and family routines.",
        "strengths_interests": "Loves music, water play, and helping in the kitchen with step-by-step tasks.",
        "communication": "Uses sentences to express needs. Benefits from choices offered visually.",
        "regulation_sensory": "Regulates with movement breaks and deep-pressure activities after high stimulation.",
        "participation": "Participates in home routines when tasks are broken into small steps.",
        "learning_access": "Learns new routines through modeling and repetition in natural settings.",
        "strategies_tried": "First-then boards and song-based routines improved mealtime and bedtime cooperation.",
        "support_needs": "Needs support when routines change unexpectedly or when tired.",
        "clinical_summary": "Ira makes steady gains with predictable home routines and regulation strategies.",
        "recommendations_iep": "Focus goals on mealtime independence, emotional regulation, and family routine participation.",
        "environment_notes": "Home kitchen, play area, and bedtime routine are primary environments.",
    }
    ira_structured = {
        "strengths_interests": {
            "strengths": ["Musical learning", "Routine memory"],
            "interests": ["Music", "Water play", "Cooking"],
        },
        "support_needs": {
            "support_needs": ["Routine previews", "Movement breaks", "Visual choices"],
        },
    }
    ira_goals = [
        {
            "label": "Mealtime self-feeding independence",
            "domain_key": "participation",
            "statement": "During family meals, Ira will use utensils independently for 10 minutes with minimal prompts.",
            "baseline": "Needs hand-over-hand for most of meal.",
            "desired": "Self-feed for full meal with 2 verbal prompts.",
        },
        {
            "label": "Emotional regulation during routine changes",
            "domain_key": "regulation_sensory",
            "statement": "When a routine changes, Ira will use a chosen calming strategy within 5 minutes.",
            "baseline": "Distress lasts 15+ minutes without support.",
            "desired": "Self-select strategy with one adult cue.",
        },
    ]
    ira_strategies = [
        {
            "label": "First-then routine board",
            "description": "Show first-then before mealtime and bedtime routines.",
            "domain_key": "participation",
        },
        {
            "label": "Movement break menu",
            "description": "Offer 3 regulation choices: wall push, breathing, or music break.",
            "domain_key": "regulation_sensory",
        },
    ]

    _seed_observation_case(
        db,
        case_aarav,
        therapist,
        case_mgr,
        sections=aarav_sections,
        structured=aarav_structured,
        goals=aarav_goals,
        strategies=aarav_strategies,
    )
    _seed_observation_case(
        db,
        case_ira,
        therapist,
        case_mgr,
        sections=ira_sections,
        structured=ira_structured,
        goals=ira_goals,
        strategies=ira_strategies,
    )

    _seed_session_log_goals(
        db,
        case_aarav,
        therapist,
        [{"label": "Communication and social skills during play", "domain_key": "communication_aac"}],
    )
    _seed_session_log_goals(
        db,
        case_ira,
        therapist,
        [{"label": "Mealtime routine participation", "domain_key": "participation"}],
    )

    _seed_iep_draft(db, case_aarav, therapist)
    _seed_iep_draft(db, case_ira, therapist)
    _seed_org_clinical_brain_library(db, case_mgr)


def _seed_org_clinical_brain_library(db: Session, approver: User) -> None:
    """Organisation goal bank + strategy pool with metadata for Clinical Brain UI."""
    from datetime import datetime, timezone

    from app.models.goal_repository import RepositoryItemStatus
    from app.services.clinical_brain_metadata import dump_metadata

    org_goals = [
        {
            "label": "Request a break using AAC or gesture",
            "domain_key": "communication_aac",
            "goal_statement": "During structured activities, the child will request a break using AAC or an agreed gesture.",
            "metadata": {
                "support_need": "transitions",
                "parent_friendly_explanation": "Your child can ask for a pause when things feel busy.",
                "parent_safe": True,
                "service_type": "shadow_support",
                "age_group": "primary",
            },
        },
        {
            "label": "Initiate peer interaction with visual support",
            "domain_key": "peer_social",
            "goal_statement": "With visual support, the child will initiate a brief peer interaction during group activities.",
            "metadata": {
                "support_need": "peer_participation",
                "parent_friendly_explanation": "Your child is practising ways to join play with a friend.",
                "parent_safe": True,
            },
        },
    ]
    for spec in org_goals:
        exists = db.scalars(
            select(GoalRepositoryItem).where(
                GoalRepositoryItem.case_id.is_(None),
                GoalRepositoryItem.label == spec["label"],
            )
        ).first()
        if exists:
            continue
        row = GoalRepositoryItem(
            case_id=None,
            created_by_user_id=approver.id,
            approved_by_user_id=approver.id,
            approved_at=datetime.now(timezone.utc),
            domain_key=spec["domain_key"],
            label=spec["label"],
            goal_statement=spec["goal_statement"],
            status=RepositoryItemStatus.APPROVED.value,
            scope="organization",
            metadata_json=dump_metadata(spec["metadata"]),
        )
        db.add(row)

    org_strategies = [
        {
            "label": "Visual countdown before transition",
            "domain_key": "emotional_regulation",
            "when_to_use": "Gives predictable time before changing activities",
            "how_to_use": "Show countdown card\nGive verbal preview\nOffer co-regulation if needed",
            "avoid": "May need longer countdown in noisy settings",
            "metadata": {
                "support_need": "transitions",
                "support_level": "visual_support",
                "environments": ["school_classroom", "home"],
                "parent_friendly_explanation": "A visual timer helps your child know when a change is coming.",
            },
        },
        {
            "label": "First-then board",
            "domain_key": "communication_aac",
            "when_to_use": "Shows what happens now and what comes next",
            "how_to_use": "Place preferred activity on then\nUse simple pictures\nKeep language brief",
            "metadata": {
                "support_need": "task_initiation",
                "support_level": "visual_support",
                "environments": ["school_classroom"],
            },
        },
    ]
    for spec in org_strategies:
        exists = db.scalars(
            select(StrategyRepositoryItem).where(
                StrategyRepositoryItem.case_id.is_(None),
                StrategyRepositoryItem.label == spec["label"],
            )
        ).first()
        if exists:
            continue
        row = StrategyRepositoryItem(
            case_id=None,
            created_by_user_id=approver.id,
            approved_by_user_id=approver.id,
            approved_at=datetime.now(timezone.utc),
            domain_key=spec["domain_key"],
            label=spec["label"],
            when_to_use=spec["when_to_use"],
            how_to_use=spec["how_to_use"],
            avoid=spec.get("avoid"),
            status=RepositoryItemStatus.APPROVED.value,
            scope="organization",
            metadata_json=dump_metadata(spec["metadata"]),
        )
        db.add(row)
    db.commit()


def ensure_clinical_brain_phase_seed(db: Session) -> None:
    """Idempotent demo rows for Clinical Brain phases 2B–5 (E2E + local QA)."""
    from datetime import datetime, timezone

    from app.models.goal_repository import RepositoryItemStatus
    from app.models.parent_goal_input import ParentGoalInput
    from app.models.strategy_recommendation_feedback import FeedbackStatus, StrategyRecommendationFeedback

    case = db.scalars(select(Case).where(Case.case_code == "IC-2026-041")).first()
    if not case:
        case = db.scalars(select(Case).limit(1)).first()
    if not case:
        return

    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    parent = db.scalars(select(User).where(User.email == "parent@demo.com")).first()

    pending = db.scalars(
        select(StrategyRepositoryItem).where(
            StrategyRepositoryItem.case_id == case.id,
            StrategyRepositoryItem.status == RepositoryItemStatus.CANDIDATE.value,
        )
    ).first()
    if not pending and therapist:
        db.add(
            StrategyRepositoryItem(
                case_id=case.id,
                created_by_user_id=therapist.id,
                label="Quiet corner break before lunch",
                when_to_use="Before cafeteria transitions",
                status=RepositoryItemStatus.CANDIDATE.value,
                scope="case",
            )
        )

    exists_fb = db.scalars(
        select(StrategyRecommendationFeedback).where(
            StrategyRecommendationFeedback.case_id == case.id,
            StrategyRecommendationFeedback.feedback_status == FeedbackStatus.NEEDS_CM_INPUT.value,
        )
    ).first()
    if not exists_fb and therapist:
        strat = db.scalars(select(StrategyRepositoryItem).limit(1)).first()
        db.add(
            StrategyRecommendationFeedback(
                case_id=case.id,
                child_id=case.child_id,
                strategy_repository_item_id=strat.id if strat else None,
                recommendation_source="library_match",
                feedback_status=FeedbackStatus.NEEDS_CM_INPUT.value,
                dismissal_reason="Unsure if this fits at home",
                created_by_user_id=therapist.id,
                created_by_role="THERAPIST",
            )
        )

    exists_pgi = db.scalars(select(ParentGoalInput).where(ParentGoalInput.case_id == case.id).limit(1)).first()
    if not exists_pgi and parent:
        db.add(
            ParentGoalInput(
                case_id=case.id,
                goal_ref="peer_play",
                input_type="see_at_home",
                comment="We practise turn-taking with siblings on weekends.",
                parent_user_id=parent.id,
            )
        )

    db.commit()


def ensure_org_clinical_brain_library(db: Session) -> None:
    """Idempotent org goal bank + strategy pool for Clinical Brain (dev/E2E)."""
    from app.models.user import User

    has_org_goal = db.scalars(
        select(GoalRepositoryItem.id).where(GoalRepositoryItem.case_id.is_(None)).limit(1)
    ).first()
    has_org_strategy = db.scalars(
        select(StrategyRepositoryItem.id).where(StrategyRepositoryItem.case_id.is_(None)).limit(1)
    ).first()
    if has_org_goal and has_org_strategy:
        return
    approver = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
    if not approver:
        approver = db.scalars(select(User).where(User.email == "casemanager@demo.com")).first()
    if not approver:
        return
    _seed_org_clinical_brain_library(db, approver)
