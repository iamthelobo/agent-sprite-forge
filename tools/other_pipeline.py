#!/usr/bin/env python3
"""Offline Other planning and review handoff. Never generates media or imports a game asset."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

SCHEMA = "other.sprite-brief/v1"
AUTHORITY_PATHS = (
    "AGENTS.md", "Documentation/ArtStyleGuide.md", "Documentation/CharacterSheetGuide.md",
    "Documentation/DesignTemplates.md", "Documentation/Research/FightingAnimationBible.md",
    "Documentation/Research/AnimationPipelineSpecification.md",
)
DELIVERABLES = (
    "character-concept-sheet", "proportion-sheet", "turnaround-sheet", "pose-study",
    "stance-sheet", "transition-study", "key-pose-sheet", "move-concept-proof",
    "expression-detail-sheet", "deformation-study", "rendering-comparison", "rough-motion-proof",
)
TREATMENTS = ("mannequin", "rough-character", "finished-character")
CARD_FIELDS = (
    "input", "purpose", "action", "properties", "startup", "active", "recovery",
    "on_hit", "on_block", "context", "recovery_destination",
)
REVIEW_FIELDS = ("anatomy", "hands", "identity", "rendering")
STATUS_FIELDS = ("Approved", "Proposed", "Measured", "TBD")


def nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_file(workspace: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("reference/image path must be a workspace-relative file")
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError("reference/image paths must be relative to the workspace")
    root = workspace.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"missing file or path outside workspace: {value}")
    return path


def plan_brief(workspace: Path, character_brief: str, study_id: str, character: str,
               deliverable: str, treatment: str, action_kind: str) -> dict:
    if deliverable not in DELIVERABLES or treatment not in TREATMENTS:
        raise ValueError("Resolve the sheet type and treatment with the user; do not guess.")
    if action_kind not in ("attack", "nonattack"):
        raise ValueError("action_kind must explicitly identify attack or nonattack")
    if deliverable == "move-concept-proof" and action_kind != "attack":
        raise ValueError("a move-concept-proof requires action_kind=attack")
    documents = list(dict.fromkeys((*AUTHORITY_PATHS, character_brief)))
    snapshots = [{"path": name, "sha256": sha256(local_file(workspace, name))}
                 for name in documents]
    return {
        "schema": SCHEMA, "study_id": study_id, "character": character, "revision": "v001",
        "character_brief": character_brief, "deliverable": deliverable, "treatment": treatment,
        "action_kind": action_kind, "purpose": "TBD", "usage": "diagnostic",
        "authority_documents": snapshots, "references": [], "stances": {}, "poses": [],
        "canvas": None, "exposure_rate": 60, "exposures": [], "source_capture_fps": None,
        "loop_policy": None,
        "move_card": ({key: {"value": "TBD", "status": "TBD"} for key in CARD_FIELDS}
                      if deliverable == "move-concept-proof" else None),
        "user_acceptance": {"status": "unreviewed", "decision": ""},
        "source_motion": "unverified", "runtime": "unverified",
        "constraints": [
            "NO SQUASH: preserve character-appropriate anatomy; add pages before compressing it.",
            "Mannequin colors track anatomical sides, not screen sides; mark support separately.",
            "Permitted mutation and explicit age exceptions come from the supplied character brief.",
            "Keep pose IDs, visual exposures, captured-video FPS and gameplay frame data separate.",
            "Reference roles and written corrections must enter any later artist/provider prompt.",
            "Credentials are capability, not authorization; this adapter makes no provider calls.",
        ],
    }


def validate_brief(brief: dict, workspace: Path, require_images: bool = False,
                   require_reference_ready: bool = False) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(brief, dict) or brief.get("schema") != SCHEMA:
        return {"valid": False, "errors": [f"schema must be {SCHEMA}"], "warnings": []}
    declared_acceptance = brief.get("user_acceptance")
    require_images = require_images or require_reference_ready or (
        isinstance(declared_acceptance, dict) and declared_acceptance.get("status") == "accepted")

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    def missing(message: str) -> None:
        (errors if require_images else warnings).append(message)

    def bound_record(record: object, label: str, accepted: bool = False) -> None:
        if not isinstance(record, dict):
            errors.append(f"{label}: missing reference record")
            return
        try:
            path = local_file(workspace, record.get("path"))
            check(record.get("sha256") == sha256(path), f"{label}: missing/stale sha256")
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
        if accepted:
            check(record.get("status") == "accepted", f"{label}: accepted stance required")
        if accepted or record.get("status") == "accepted":
            check(nonempty_text(record.get("decision")),
                  f"{label}: acceptance needs a recorded decision")

    for key in ("study_id", "character", "revision", "character_brief"):
        check(isinstance(brief.get(key), str) and bool(brief[key].strip()), f"{key} is required")
    check(brief.get("deliverable") in DELIVERABLES, "resolve an explicit supported deliverable")
    check(brief.get("treatment") in TREATMENTS, "resolve an explicit supported treatment")
    check(brief.get("action_kind") in ("attack", "nonattack"), "action_kind must be attack/nonattack")
    check(brief.get("usage") in ("diagnostic", "reference-candidate"), "usage must be diagnostic/reference-candidate")
    check(brief.get("loop_policy") in (None, "oneshot", "cycle"),
          "loop_policy must be explicit oneshot/cycle or null; no inferred/reversed recovery")
    if not isinstance(brief.get("purpose"), str) or brief["purpose"].strip() in ("", "TBD"):
        missing("state the purpose/decision this study answers")

    docs = brief.get("authority_documents", [])
    check(isinstance(docs, list), "authority_documents must be a list")
    doc_paths = set()
    for record in docs if isinstance(docs, list) else []:
        bound_record(record, "authority document")
        if isinstance(record, dict) and isinstance(record.get("path"), str):
            doc_paths.add(record["path"])
    required_docs = set(AUTHORITY_PATHS)
    if isinstance(brief.get("character_brief"), str):
        required_docs.add(brief["character_brief"])
    check(required_docs <= doc_paths, "missing current authority/character document snapshots")

    refs = brief.get("references", [])
    check(isinstance(refs, list), "references must be a list")
    roles = set()
    for record in refs if isinstance(refs, list) else []:
        bound_record(record, "reference")
        if isinstance(record, dict):
            role = record.get("role")
            check(isinstance(role, str) and bool(role), "reference role is required")
            check(record.get("status") in ("proposed", "accepted", "unverified", "diagnostic", "rejected"),
                  "reference status must distinguish proposed/accepted/unverified/diagnostic/rejected")
            if require_images and role in ("identity", "rendering"):
                check(record.get("status") not in ("diagnostic", "rejected"),
                      "diagnostic/rejected material cannot supply positive identity/rendering authority")
            if isinstance(role, str):
                roles.add(role)
    for role in ("identity", "rendering"):
        if role not in roles:
            missing(f"missing {role} reference with explicit role")

    is_move = brief.get("deliverable") == "move-concept-proof"
    check(not is_move or brief.get("action_kind") == "attack", "move-concept-proof must identify an attack")
    if brief.get("action_kind") == "attack" or is_move:
        stances = brief.get("stances", {})
        for name in ("idle", "crouch"):
            bound_record(stances.get(name) if isinstance(stances, dict) else None,
                         f"{name} stance", accepted=True)

    card = brief.get("move_card")
    if is_move or card is not None:
        check(isinstance(card, dict), "move concept proof needs a visible move_card")
        for name in CARD_FIELDS:
            field = card.get(name) if isinstance(card, dict) else None
            check(isinstance(field, dict), f"move_card.{name} is required (TBD is valid)")
            if not isinstance(field, dict):
                continue
            value, status = field.get("value"), field.get("status")
            check(isinstance(value, str) and bool(value.strip()), f"move_card.{name}.value is required")
            check(status in STATUS_FIELDS, f"move_card.{name} needs field-level status")
            if isinstance(value, str) and value.strip().upper() == "TBD":
                check(status == "TBD", f"move_card.{name}: TBD cannot be approved/measured")
            if status in ("Approved", "Measured"):
                check(nonempty_text(field.get("evidence")),
                      f"move_card.{name}: {status} needs decision/test evidence")

    canvas = brief.get("canvas")
    size = None
    if canvas is None:
        missing("declare common untrimmed canvas, root anchor and facing")
    elif not isinstance(canvas, dict):
        errors.append("canvas must be an object")
    else:
        w, h, anchor = canvas.get("width"), canvas.get("height"), canvas.get("anchor")
        if type(w) is int and type(h) is int and w > 0 and h > 0:
            size = (w, h)
        else:
            errors.append("canvas dimensions must be positive integers")
        check(isinstance(anchor, list) and len(anchor) == 2 and
              all(type(v) in (int, float) and math.isfinite(v) for v in anchor),
              "canvas anchor must contain two finite coordinates")
        check(canvas.get("facing") in ("left", "right"), "declare left/right facing")

    poses = brief.get("poses", [])
    check(isinstance(poses, list), "poses must be a list")
    if not poses:
        missing("add explicit pose records; there is no default pose count")
    ids = set()
    ready = require_reference_ready or (isinstance(brief.get("user_acceptance"), dict) and
                                       brief["user_acceptance"].get("status") == "accepted")
    for pose in poses if isinstance(poses, list) else []:
        if not isinstance(pose, dict):
            errors.append("each pose must be an object")
            continue
        pid = pose.get("id")
        if not isinstance(pid, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", pid):
            errors.append("pose id must be a safe stable identifier")
        elif pid in ids:
            errors.append(f"duplicate pose id: {pid}")
        else:
            ids.add(pid)
        image_path = pose.get("image")
        if not image_path:
            missing(f"{pid}: pose image is missing")
        else:
            try:
                path = local_file(workspace, image_path)
                if path.suffix.lower() != ".png":
                    raise ValueError("pose images must be PNG")
                from PIL import Image
                with Image.open(path) as image:
                    check(image.format == "PNG", f"{pid}: file is not a PNG")
                    check(size is not None and image.size == size,
                          f"{pid}: image must match common canvas; do not resize poses to fit")
                    image.verify()
                if "sha256" in pose or ready:
                    check(pose.get("sha256") == sha256(path), f"{pid}: missing/stale image hash")
            except (ValueError, OSError, ImportError) as exc:
                errors.append(f"{pid}: {exc}")
        review = pose.get("review", {})
        for name in REVIEW_FIELDS:
            result = review.get(name) if isinstance(review, dict) else None
            allowed = ("pass", "fail", "unverified", "deferred") if name == "rendering" else ("pass", "fail", "unverified")
            check(result in allowed, f"{pid}: record {name} review result")
            required = name != "rendering" or brief.get("treatment") == "finished-character"
            if ready and required:
                check(result == "pass", f"{pid}: {name} must pass for positive reference readiness")
            elif required and result != "pass":
                warnings.append(f"{pid}: {name} is {result}; diagnostic material only")
    for pose in poses if isinstance(poses, list) else []:
        if isinstance(pose, dict) and pose.get("from") is not None:
            check(isinstance(pose["from"], str) and pose["from"] in ids,
                  f"{pose.get('id')}: unknown source pose/branch")

    check(type(brief.get("exposure_rate")) is int and brief["exposure_rate"] == 60,
          "visual exposure_rate must be the explicit integer 60")
    exposures = brief.get("exposures", [])
    check(isinstance(exposures, list), "exposures must be a list")
    total = 0
    for entry in exposures if isinstance(exposures, list) else []:
        if not isinstance(entry, dict):
            errors.append("each exposure must be an object")
            continue
        check(isinstance(entry.get("pose_id"), str) and entry["pose_id"] in ids,
              "exposure references an unknown pose")
        ticks = entry.get("duration_ticks")
        check(type(ticks) is int and ticks > 0, "exposure duration_ticks must be a positive integer")
        if type(ticks) is int and ticks > 0:
            total += ticks
    if not exposures:
        warnings.append("untimed: no visual exposure schedule; no motion/timing pass")
    acceptance = brief.get("user_acceptance", {})
    check(isinstance(acceptance, dict) and acceptance.get("status") in ("unreviewed", "accepted"),
          "user_acceptance must be separately recorded")
    if ready:
        check(bool(poses), "reference readiness requires pose images")
        check(isinstance(acceptance, dict) and acceptance.get("status") == "accepted" and
              nonempty_text(acceptance.get("decision")),
              "reference readiness needs explicit user acceptance and decision record")
    return {"valid": not errors, "errors": errors, "warnings": warnings,
            "total_visual_ticks": total, "gameplay_authority": False,
            "visual_review_performed": False, "runtime_importer": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="write an offline draft; unresolved fields remain explicit")
    plan.add_argument("--workspace", type=Path, required=True)
    plan.add_argument("--character-brief", required=True)
    plan.add_argument("--study-id", required=True)
    plan.add_argument("--character", required=True)
    plan.add_argument("--deliverable", choices=DELIVERABLES, required=True)
    plan.add_argument("--treatment", choices=TREATMENTS, required=True)
    plan.add_argument("--action-kind", choices=("attack", "nonattack"), required=True)
    plan.add_argument("--out", type=Path, required=True)
    reference = commands.add_parser("reference", help="print a hashed reference record; no acceptance is inferred")
    reference.add_argument("--workspace", type=Path, required=True)
    reference.add_argument("--path", required=True)
    reference.add_argument("--role", required=True)
    reference.add_argument("--status", choices=("proposed", "accepted", "unverified", "diagnostic", "rejected"), default="proposed")
    reference.add_argument("--decision", default="")
    for name in ("check", "handoff"):
        sub = commands.add_parser(name)
        sub.add_argument("--workspace", type=Path, required=True)
        sub.add_argument("--brief", type=Path, required=True)
        sub.add_argument("--require-reference-ready", action="store_true")
        if name == "handoff":
            sub.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        workspace = args.workspace.resolve(strict=True)
        if args.command == "reference":
            if args.status == "accepted" and not nonempty_text(args.decision):
                raise ValueError("accepted reference needs the existing user decision, not an inferred approval")
            path = local_file(workspace, args.path)
            print(json.dumps({"path": args.path, "sha256": sha256(path), "role": args.role,
                              "status": args.status, "decision": args.decision}, ensure_ascii=False))
            return 0
        if args.command == "plan":
            brief = plan_brief(workspace, args.character_brief, args.study_id, args.character,
                               args.deliverable, args.treatment, args.action_kind)
            out = (args.out if args.out.is_absolute() else workspace / args.out).resolve()
            if not out.is_relative_to(workspace) or out == workspace:
                raise ValueError("plan output must be inside workspace")
            parts = [part.casefold() for part in out.relative_to(workspace).parts]
            if parts[0] in ("brazbrue", "game") or ".git" in parts:
                raise ValueError("plan cannot write protected history, game content or Git internals")
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("x", encoding="utf-8") as file:
                json.dump(brief, file, indent=2, ensure_ascii=False)
                file.write("\n")
            print(json.dumps({"status": "draft-needs-input", "brief": str(out),
                              "provider_calls": 0, "generated_art": False}))
            return 0
        brief = json.loads(args.brief.read_text(encoding="utf-8-sig"))
        report = validate_brief(brief, workspace, args.command == "handoff", args.require_reference_ready)
        if args.command == "check" or not report["valid"]:
            print(json.dumps(report, ensure_ascii=False))
            return 0 if report["valid"] else 1
        from other_handoff import export_handoff
        result = export_handoff(brief, workspace, args.output_dir)
        result["validation"] = report
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
