"""Offline review exports for Other; no provider calls or game-engine imports."""
from __future__ import annotations

import copy
import csv
import hashlib
import html
import json
import shutil
import tempfile
from fractions import Fraction
from pathlib import Path


CARD_LABELS = {
    "input": "Input", "purpose": "Purpose", "action": "Action",
    "properties": "Properties", "startup": "Startup", "active": "Active",
    "recovery": "Recovery", "on_hit": "Advantage on hit",
    "on_block": "Advantage on block", "context": "Timing / action context",
    "recovery_destination": "Recovery destination",
}


def _text(value: object) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return html.escape(str(value), quote=True)


def _inside(path: Path, workspace: Path) -> Path:
    resolved = path.resolve()
    if resolved != workspace and workspace not in resolved.parents:
        raise ValueError("Path must resolve inside the workspace")
    return resolved


def _rational(value: Fraction) -> dict:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _review_html(brief: dict, frames: list[dict], rows: list[dict]) -> str:
    title = f"{brief['character']} — {brief['study_id']} — {brief['revision']}"
    parts = ["<!doctype html><html lang='en'><meta charset='utf-8'>",
             f"<title>{_text(title)}</title>", "<style>",
             "body{background:#e6e6e6;color:#202020;font:16px/1.5 system-ui;"
             "max-width:1400px;margin:32px auto;padding:0 24px}"
             ".poses{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px}"
             "figure{margin:0;background:white;padding:16px;border:1px solid #888}"
             "img{display:block;max-width:100%;height:auto;margin:auto}"
             "table{border-collapse:collapse;width:100%;background:white;margin:16px 0}"
             "th,td{border:1px solid #888;padding:8px;text-align:left;vertical-align:top}"
             "p,td,figcaption{overflow-wrap:anywhere;white-space:pre-wrap}"
             "h1{line-height:1.2}small{display:block}", "</style>",
             f"<h1>{_text(title)}</h1>",
             f"<p>{_text(brief['deliverable'])} / {_text(brief['treatment'])} / "
             f"{_text(brief.get('usage', 'diagnostic'))}</p>",
             f"<p>Question: {_text(brief.get('purpose', 'TBD'))}</p>",
             "<p><strong>Static review packet.</strong> This page is not a rough motion proof "
             "or runtime proof. Export success does not grant visual approval or user acceptance.</p>",
             f"<p>User acceptance: {_text(brief.get('user_acceptance', {'status': 'unreviewed'}))}</p>",
             f"<p>Source motion: {_text(brief.get('source_motion', 'unverified'))}\n"
             f"Runtime evidence: {_text(brief.get('runtime', 'unverified'))}</p>",
             f"<p>Canvas / anchor / facing: {_text(brief.get('canvas', {}))}</p>"]
    parts.append("<h2>Constraints</h2><ul>")
    parts.extend(f"<li>{_text(constraint)}</li>" for constraint in brief.get("constraints", []))
    parts.append("</ul>")
    parts.append(f"<p>Loop policy: {_text(brief.get('loop_policy') or 'Unspecified; no upstream selection emitted.')}</p>")
    card = brief.get("move_card")
    if card:
        parts.extend(["<h2>Move concept review card</h2>",
                      "<p>Gameplay frame-data fields use 60 Hz simulation ticks, under the "
                      "stated counting convention. They are independent of visual exposures.</p>",
                      "<table><tr><th>Field</th><th>Value</th><th>Status</th></tr>"])
        for key, label in CARD_LABELS.items():
            field = card[key]
            parts.append(f"<tr><th>{label}</th><td>{_text(field['value'])}</td>"
                         f"<td>{_text(field['status'])}</td></tr>")
        parts.append("</table>")
    parts.append("<h2>Poses</h2><div class='poses'>")
    for pose, frame in zip(brief["poses"], frames):
        holds = [str(row["duration_ticks"]) for row in rows if row["pose_id"] == pose["id"]]
        caption = (f"{pose['id']} — {pose.get('phase', '')}\n"
                   f"From: {pose.get('from') or 'origin / unspecified'}\n"
                   f"Notes: {pose.get('notes', '')}\n"
                   f"Review: {json.dumps(pose.get('review', {}), ensure_ascii=False)}\n"
                   f"Visual holds: {', '.join(holds) + ' ticks at 60 Hz' if holds else 'untimed / not exposed'}")
        parts.append(f"<figure><img src='{frame['file']}' alt='{_text(pose['id'])}'>"
                     f"<figcaption>{_text(caption)}</figcaption></figure>")
    parts.append("</div><h2>Visual exposure map</h2>")
    parts.append("<p>Explicit visual holds at 60 Hz; no gameplay timing, hitbox activity, "
                 "captured-video FPS or motion quality is inferred.</p>")
    if rows:
        parts.append("<table><tr><th>Pose</th><th>Start tick</th><th>Hold ticks</th>"
                     "<th>End tick (exclusive)</th></tr>")
        for row in rows:
            parts.append(f"<tr><td>{_text(row['pose_id'])}</td><td>{row['start_tick']}</td>"
                         f"<td>{row['duration_ticks']}</td><td>{row['end_tick']}</td></tr>")
        parts.append("</table>")
    else:
        parts.append("<p>Untimed study: no holds or motion playback supplied.</p>")
    parts.append("<h2>References and provenance</h2><p>Reference records are retained; "
                 "source guides and reference assets are not copied into this packet.</p>")
    parts.append(f"<p>{_text(brief.get('references', []))}</p>")
    parts.append(f"<p>{_text(brief.get('provenance', 'See manifest.json for the complete brief.'))}</p>")
    parts.append("<p>Pose PNG bytes are unchanged. Manifest hashes identify the exported files.</p></html>")
    return "\n".join(parts)


def export_handoff(brief: dict, workspace: Path, output_dir: Path) -> dict:
    """Export an already-validated brief atomically into a new workspace directory."""
    workspace = Path(workspace).resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError("Workspace must be a directory")
    requested = Path(output_dir)
    requested = requested if requested.is_absolute() else workspace / requested
    output = _inside(requested, workspace)
    if output == workspace or requested.exists() or requested.is_symlink() or output.exists():
        raise ValueError("Output must be a new directory; existing output is never overwritten")
    relative_parts = [part.casefold() for part in output.relative_to(workspace).parts]
    if relative_parts[0] in {"brazbrue", "game"} or ".git" in relative_parts:
        raise ValueError("Export cannot enter historical, runtime or Git metadata directories")
    poses = brief.get("poses", [])
    if not poses:
        raise ValueError("Export requires at least one pose PNG")
    rate = brief.get("exposure_rate")
    if type(rate) is not int or rate != 60:
        raise ValueError("Visual exposure rate must be 60 Hz")
    loop_policy = brief.get("loop_policy")
    if loop_policy not in (None, "oneshot", "cycle"):
        raise ValueError("Explicit loop_policy must be oneshot or cycle; otherwise leave it unset")
    sources = []
    pose_ids = set()
    for pose in poses:
        if pose["id"] in pose_ids:
            raise ValueError("Pose IDs must be unique")
        pose_ids.add(pose["id"])
        relative = Path(pose["image"])
        if relative.is_absolute():
            raise ValueError("Pose image must be workspace-relative")
        source = _inside(workspace / relative, workspace)
        if not source.is_file() or source.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Pose image must be an existing PNG")
        sources.append(source)
    rows, cursor = [], 0
    for index, exposure in enumerate(brief.get("exposures", []), 1):
        ticks, pose_id = exposure["duration_ticks"], exposure["pose_id"]
        if type(ticks) is not int or ticks <= 0 or pose_id not in pose_ids:
            raise ValueError("Each exposure needs a known pose and positive integer hold")
        rows.append({"index": index, "pose_id": pose_id, "start_tick": cursor,
                     "duration_ticks": ticks, "end_tick": cursor + ticks,
                     "start_seconds": _rational(Fraction(cursor, rate)),
                     "duration_seconds": _rational(Fraction(ticks, rate))})
        cursor += ticks
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".other-handoff-", dir=output.parent))
    try:
        (stage / "frames").mkdir()
        frames = []
        for index, (pose, source) in enumerate(zip(poses, sources), 1):
            filename = f"frames/pose-{index:04d}.png"
            data = source.read_bytes()
            (stage / filename).write_bytes(data)
            frames.append({"pose_id": pose["id"], "file": filename,
                           "source": pose["image"], "sha256": hashlib.sha256(data).hexdigest()})
        bridge = {"file": None, "status": "omitted", "reason": "Explicit visual holds and loop_policy are both required."}
        if rows and loop_policy:
            indices = {frame["pose_id"]: index for index, frame in enumerate(frames)}
            selection = {"schema": "forge-frame-selection/v2", "sourceDirectory": "frames",
                         "start": 0, "endExclusive": len(frames),
                         "sourceIndices": [indices[row["pose_id"]] for row in rows],
                         "sourceHashes": [frame["sha256"] for frame in frames],
                         "ticks": [row["duration_ticks"] for row in rows], "tickHz": rate,
                         "durations_ms": [((row["end_tick"] * 1000 + 30) // 60) -
                                          ((row["start_tick"] * 1000 + 30) // 60) for row in rows],
                         "loopPolicy": loop_policy, "events": [],
                         "status": "selected-needs-visual-review"}
            (stage / "forge-selection.json").write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")
            bridge = {"file": "forge-selection.json", "status": "selected-needs-visual-review",
                      "timing_note": "durations_ms rounds cumulative tick edges half up; exact visual ticks and rational seconds remain in this manifest. No gameplay events are inferred."}
        manifest = {"schema": "other-animation.v1", "purpose": "offline-review-handoff",
                    "brief": copy.deepcopy(brief), "frames": frames,
                    "visual_timing": {"rate_hz": rate, "status": "timed" if rows else "untimed",
                                      "exposures": rows, "total_ticks": cursor,
                                      "total_seconds": _rational(Fraction(cursor, rate)) if rows else None},
                    "evidence": {"export": "completed", "visual_review": "not-performed-by-exporter",
                                 "source_motion": "not-tested-by-exporter", "runtime": "not-tested-by-exporter"},
                    "upstream_bridge": bridge, "gameplay_authority": False}
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (stage / "review.html").write_text(_review_html(brief, frames, rows), encoding="utf-8")
        with (stage / "exposure.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["index", "pose_id", "file", "start_tick", "duration_ticks", "end_tick",
                             "visual_rate_hz", "start_seconds_exact", "duration_seconds_exact"])
            files = {frame["pose_id"]: frame["file"] for frame in frames}
            for row in rows:
                writer.writerow([row["index"], row["pose_id"], files[row["pose_id"]], row["start_tick"],
                                 row["duration_ticks"], row["end_tick"], rate,
                                 str(Fraction(row["start_tick"], rate)), str(Fraction(row["duration_ticks"], rate))])
        if output.exists() or output.is_symlink():
            raise ValueError("Output appeared during export; preserving it")
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {"output_dir": str(output), "manifest": str(output / "manifest.json"),
            "review": str(output / "review.html"), "exposure_csv": str(output / "exposure.csv"),
            "forge_selection": str(output / bridge["file"]) if bridge["file"] else None,
            "frame_count": len(frames), "total_visual_ticks": cursor,
            "timing_status": "timed" if rows else "untimed"}
