"""Export authored Animation Forge poses through the existing offline Other handoff.

The unique RGBA drawings and integer visual exposures are authoritative. The
optional legacy reviewer receives a separate, byte-preserved 60 Hz expansion;
its playback and selection controls do not establish gameplay or art approval.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

import PIL
from PIL import Image

if __package__:
    from . import animation_forge_backends as core
    from .other_handoff import export_handoff
else:
    import animation_forge_backends as core
    from other_handoff import export_handoff


EXPORT_SCHEMA = "other-animation-forge-export.v1"
ROOT = Path(__file__).resolve().parents[1]
REVIEW_SCRIPT = ROOT / "skills/video2dsprite/scripts/animation_review.py"


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                       allow_nan=False) + "\n").encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _save_json(path: Path, value: object) -> None:
    path.write_bytes(_json_bytes(value))


def _pose_diagnostics(project: dict) -> dict[str, list[dict]]:
    """Retain the core's warnings verbatim; an empty list is not art acceptance."""
    return {pose["id"]: core.evaluate_pose(project, pose["id"])["diagnostics"]
            for pose in project["poses"]}


def _pose_notes(diagnostics: list[dict], reference_only: bool = False) -> str:
    notes = ("Local reference-motion diagnostic pose; not original or cleared for distribution."
             if reference_only else "Original authored diagnostic pose;")
    notes += " No contact or hand acceptance inferred."
    if diagnostics:
        return notes + "\nCore warnings:\n" + "\n".join(
            f"{item['code']}: {item['message']}" for item in diagnostics)
    return notes + "\nCore warnings: none reported. This is not visual acceptance."


def _visual_timing(project: dict) -> dict:
    total = sum(row["duration_ticks"] for row in project["exposures"])
    start_index = project.get("loop_start", 0) if project["schema"] == core.WALK_SCHEMA else 0
    start_tick = sum(row["duration_ticks"] for row in project["exposures"][:start_index])
    fraction = Fraction(total, 60)
    return {"rate_hz": 60, "exposures": copy.deepcopy(project["exposures"]),
            "total_ticks": total, "total_seconds": {"numerator": fraction.numerator, "denominator": fraction.denominator},
            "loop_policy": project["loop_policy"], "loop_start_exposure": start_index,
            "loop_start_tick": start_tick, "loop_ticks": total-start_tick,
            "entry_then_loop": project["loop_policy"] == "cycle" and start_index > 0}


def _brief(project: dict, frames: list[dict], project_hash: str, renderer: dict,
           diagnostics: dict[str, list[dict]]) -> dict:
    """Paths in this brief resolve against the export packet root, including after rename."""
    backend = core.backend_for(project)
    reference = project["source"]["kind"] == "reference-only"
    timing = _visual_timing(project)
    return {
        "schema": "other.sprite-brief/v1", "study_id": "ANIMATION-FORGE-REFERENCE" if reference else "ANIMATION-FORGE-AUTHORED",
        "character": "Local reference-motion mannequin" if reference else "Original neutral adult mannequin", "revision": project_hash[:12],
        "deliverable": "rough-motion-proof", "treatment": "mannequin", "action_kind": "nonattack",
        "purpose": f"Inspect authored poses and visual holds: {project['name']}", "usage": "diagnostic",
        "canvas": {"width": backend.SIZE, "height": backend.SIZE,
                   "anchor": list(backend.ANCHOR), "facing": "right"},
        "poses": [{"id": pose["id"], "image": frame["file"], "sha256": frame["sha256"],
                   "phase": pose["label"], "from": None,
                   "notes": _pose_notes(diagnostics[pose["id"]], reference),
                   "diagnostics": copy.deepcopy(diagnostics[pose["id"]]),
                   "review": {"anatomy": "unverified", "hands": "unverified",
                              "identity": "unverified", "rendering": "unverified"}}
                  for pose, frame in zip(project["poses"], frames)],
        "exposure_rate": 60, "exposures": copy.deepcopy(project["exposures"]),
        "loop_policy": "oneshot" if timing["entry_then_loop"] else project["loop_policy"],
        "authored_visual_timing": timing, "source_capture_fps": None,
        "source_motion": copy.deepcopy(project["source"]),
        "gameplay": copy.deepcopy(project["gameplay"]), "gameplay_authority": False,
        "runtime": "unverified; no Unreal import performed", "move_card": None,
        "references": [{"path": "project.json", "sha256": project_hash,
                        "role": "reference-motion-edit-project" if reference else "authored-pose-source", "status": "diagnostic", "decision": ""}],
        "user_acceptance": {"status": "unreviewed", "decision": ""},
        "constraints": [
            "NO SQUASH: fixed adult mannequin dimensions; no crop, scale or normalization in export.",
            "Right arm orange; left arm blue; right leg magenta; left leg teal. Colors follow anatomy.",
            "Pose review uses neutral #E6E6E6; delivered PNGs have transparent backgrounds.",
            "Source timing, authored 60 Hz visual exposure and gameplay timing are separate.",
            "Left output is an exact pixel mirror, not an authored alternate-facing rig.",
            "This is a diagnostic mannequin tool proof, not an approved fighter, stance or moveset.",
        ] + (["Reference-only source motion; local edit/export is not permission to distribute game-derived motion."] if reference else [])
          + (["The main Forge selection is one complete pass. Entry plays once, then forge-loop-selection.json repeats the tail; exact entry/loop playback is in authored-playback.html."] if timing["entry_then_loop"] else []),
        "provenance": {"editable_project": "project.json", "path_base": "export packet root",
                       "renderer": renderer, "paid_provider_calls": 0,
                       "review": "unverified", "source_motion_import": "pinned-local-reference-only" if reference else "none"},
    }


def _loop_selection(stage: Path, project: dict) -> str | None:
    """Keep the upstream one-pass derivative honest; emit a separate tail cycle."""
    timing = _visual_timing(project)
    if not timing["entry_then_loop"]:
        return None
    selection = json.loads((stage / "handoff/forge-selection.json").read_text(encoding="utf-8"))
    start = timing["loop_start_exposure"]
    selection["sourceIndices"] = selection["sourceIndices"][start:]
    selection["ticks"] = selection["ticks"][start:]
    edge = 0
    durations = []
    for ticks in selection["ticks"]:
        durations.append(((edge+ticks)*1000+30)//60 - (edge*1000+30)//60)
        edge += ticks
    selection.update(durations_ms=durations, loopPolicy="cycle",
                     method="Animation Forge explicit entry-once and repeating-tail derivative",
                     origin={"selection": "forge-selection.json", "loop_start_exposure": start,
                             "loop_start_tick": timing["loop_start_tick"],
                             "note": "Play the full one-shot selection once, then this loop-only selection. Exact authored visual ticks remain authoritative."})
    path = "handoff/forge-loop-selection.json"
    _save_json(stage / path, selection)
    return path


def _legacy_playback(stage: Path, project: dict, frames: list[dict]) -> dict:
    total = sum(row["duration_ticks"] for row in project["exposures"])
    if total > 600:
        return {"status": "omitted", "reason": "Legacy reviewer accepts at most 600 source frames; exact handoff is complete."}
    if importlib.util.find_spec("numpy") is None:
        return {"status": "omitted", "reason": "NumPy is unavailable in this Python runtime; exact handoff is complete."}
    tick_dir = stage / "review-ticks"
    tick_dir.mkdir()
    lookup = {item["pose_id"]: item["file"] for item in frames}
    tick = 0
    for exposure in project["exposures"]:
        for _ in range(exposure["duration_ticks"]):
            shutil.copyfile(stage / lookup[exposure["pose_id"]], tick_dir / f"frame-{tick:04d}.png")
            tick += 1
    command = [sys.executable, str(REVIEW_SCRIPT), "review", "--frames-dir", str(tick_dir),
               "--out-dir", str(stage / "playback"), "--fps", "60", "--min-cycle", "2",
               "--max-cycle", "48", "--preview-size", "512"]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120,
                               encoding="utf-8", errors="replace")
    if completed.returncode:
        raise ValueError(f"Existing animation_review CLI failed: {completed.stderr.strip() or completed.stdout.strip()}")
    return {"status": "generated-needs-visual-review", "page": "playback/index.html",
            "metadata": "playback/review.json", "source_directory": "review-ticks",
            "source_frames": total, "rate_hz": 60, "tool": "animation_review.py review",
            "script_sha256": _sha(REVIEW_SCRIPT.read_bytes()),
            "note": "Byte-identical authored drawings repeated by visual hold. Reviewer repeats selected intervals for inspection even for authored one-shots. Its saved v1 selection is a derivative; handoff/forge-selection.json retains exact authored ticks."}


def _authored_playback(stage: Path, project: dict, renders: dict) -> dict:
    """Small exact-tick player for the entry/loop contract absent from legacy review."""
    timing = _visual_timing(project)
    payload = {"name": project["name"], "timing": timing,
               "frames": {facing: {frame["pose_id"]: frame["file"] for frame in frames}
                          for facing, frames in renders.items()},
               "reference_only": project["source"]["kind"] == "reference-only"}
    inline = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    page = r'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Animation Forge exact visual playback</title>
<style>body{font:16px/1.5 system-ui;background:#e6e6e6;color:#222;max-width:900px;margin:24px auto;padding:0 20px}canvas{display:block;width:min(100%,640px);height:auto;margin:auto;background:#e6e6e6}button,select{font:inherit;padding:8px;margin:4px}input{width:min(100%,640px)}p{margin:8px 0}</style>
<h1 id="title"></h1><p id="source"></p><p>Exact authored visual ticks at 60 Hz. Entry plays once, then only the declared tail repeats. Gameplay, contact and visual acceptance remain unverified.</p>
<canvas id="view" width="640" height="640"></canvas><input id="seek" type="range" min="0" value="0" step="1" aria-label="Visual tick">
<div><button id="play">Play</button><button id="reset">Reset</button><select id="speed" aria-label="Playback speed"><option value="1">1×</option><option value="0.5">0.5×</option><option value="0.25">0.25×</option></select><select id="facing" aria-label="Facing"><option value="right">Right</option><option value="left">Left (pixel mirror)</option></select></div><p id="readout"></p>
<p><a href="handoff/review.html">Static review and warnings</a> __LEGACY_LINK__ · <a href="export.json">Source and exact timing</a></p>
<script>const data=__DATA__;
const $=id=>document.getElementById(id), timing=data.timing, ctx=$('view').getContext('2d');
let tick=0,running=false,origin=0,started=0,ready=false;
const images={right:{},left:{}};
const loading=[];
for(const side of ['right','left'])for(const[id,file]of Object.entries(data.frames[side])){const im=new Image();im.src=file;images[side][id]=im;loading.push(im.decode())}
function localTick(absolute){const length=timing.total_ticks,entry=timing.loop_start_tick;if(timing.loop_policy!=='cycle')return Math.min(absolute,length-1);return absolute<length?absolute:entry+(absolute-entry)%(length-entry)}
function poseAt(local){for(const row of timing.exposures){if(local<row.duration_ticks)return row.pose_id;local-=row.duration_ticks}throw Error('Invalid timeline')}
function draw(){if(!ready)return;const local=localTick(tick),id=poseAt(local);ctx.clearRect(0,0,640,640);ctx.drawImage(images[$('facing').value][id],0,0);$('seek').value=local;$('readout').textContent=`Visual tick ${local} / ${timing.total_ticks-1} · ${id} · ${local<timing.loop_start_tick?'entry':'loop range'} · loop begins at tick ${timing.loop_start_tick}`}
function stop(){running=false;$('play').textContent='Play'}
function restartClock(){origin=tick;started=performance.now()}
$('title').textContent=data.name;$('source').textContent=data.reference_only?'REFERENCE ONLY — local game-derived motion; not original or cleared for distribution.':'Original authored mannequin fixture.';$('seek').max=timing.total_ticks-1;
$('play').onclick=()=>{if(running){stop()}else{running=true;restartClock();$('play').textContent='Pause'}};
$('reset').onclick=()=>{stop();tick=0;draw()};$('seek').oninput=()=>{stop();tick=Number($('seek').value);draw()};$('speed').onchange=restartClock;$('facing').onchange=draw;
Promise.all(loading).then(()=>{ready=true;draw()}).catch(error=>{$('readout').textContent='Image loading failed: '+error.message});
function step(now){if(running&&ready){tick=origin+Math.floor(Math.max(0,now-started)*60*Number($('speed').value)/1000);if(timing.loop_policy!=='cycle'&&tick>=timing.total_ticks){tick=timing.total_ticks-1;stop()}draw()}requestAnimationFrame(step)}requestAnimationFrame(step);
</script></html>'''
    legacy_link = '· <a href="playback/index.html">Legacy interval reviewer</a>' if (stage / "playback/index.html").is_file() else ""
    (stage / "authored-playback.html").write_text(page.replace("__DATA__", inline).replace("__LEGACY_LINK__", legacy_link), encoding="utf-8")
    return {"status": "generated-needs-visual-review", "page": "authored-playback.html",
            "rate_hz": 60, "timing": timing,
            "note": "Entry once then repeating tail; direct unique PNG playback without smoothing, normalization or duplicated source motion."}


def _index(project: dict, playback: dict) -> str:
    escape = html.escape
    page = escape(playback.get("page", ""), quote=True)
    reference = project["source"]["kind"] == "reference-only"
    timing = _visual_timing(project)
    preview = (f"<p><a href='{page}'>Open playback and scrub controls</a></p>"
               f"<iframe title='Animation Forge playback' src='{page}'></iframe>"
               if playback.get("page") else f"<p>{escape(playback['reason'])}</p>")
    return ("<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(project['name'])} — Animation Forge export</title>"
            "<style>body{font:16px/1.5 system-ui;background:#e6e6e6;color:#222;max-width:1200px;margin:32px auto;padding:0 20px}"
            "iframe{width:100%;height:850px;border:1px solid #888}a{color:#17446d}</style>"
            f"<h1>{escape(project['name'])}</h1><p>" +
            ("Reference-only source-motion mannequin; not original or cleared for distribution. " if reference else "Diagnostic original adult mannequin. ") +
            "Anatomy, hands, contact, rendering and user acceptance remain unverified. "
            "This is not gameplay or an Unreal import.</p>"
            f"<p>Authored loop policy: <strong>{escape(project['loop_policy'])}</strong>. "
            f"Loop begins at exposure {timing['loop_start_exposure']} / visual tick {timing['loop_start_tick']}. "
            "The compatibility reviewer repeats the selected interval for inspection; "
            "the authoring preview retains the authored cycle or one-shot behavior. "
            "All holds are visual ticks at 60 Hz. Source motion and gameplay timing are separate.</p>"
            "<p><a href='handoff/review.html'>Static pose review</a> · "
            "<a href='handoff/manifest.json'>Exact visual timing and immutable PNG hashes</a> · "
            "<a href='handoff/forge-selection.json'>Forge selection</a> · "
            "<a href='project.json'>Reopen editable project</a> · "
            "<a href='export.json'>Renderer and source provenance</a></p>" + preview + "</html>")


def export_project(project: dict, output_dir: Path) -> dict:
    """Publish a new local packet atomically. Never edit an existing output or caller data.

    The caller confines output_dir to its allowed export root. All returned paths
    (and packet-internal source paths) are relative to the final packet directory.
    """
    snapshot = copy.deepcopy(project)
    core.validate_project(snapshot)
    backend = core.backend_for(snapshot)
    requested = Path(output_dir).absolute()
    if requested.exists() or requested.is_symlink():
        raise ValueError("Output must be a new directory; existing output is never overwritten")
    output = requested.resolve()
    if output.exists():
        raise ValueError("Output must be a new directory")
    project_data = _json_bytes(snapshot)
    project_hash = _sha(project_data)
    diagnostics = _pose_diagnostics(snapshot)
    renderer = {"id": backend.RENDERER_VERSION, "rig": backend.RIG_VERSION,
                "module": f"tools/{Path(backend.__file__).name}", "sha256": _sha(Path(backend.__file__).read_bytes()),
                "pillow_version": PIL.__version__, "canvas": [backend.SIZE, backend.SIZE],
                "anchor": list(backend.ANCHOR), "alpha": "straight RGBA", "png_compress_level": 9,
                "facing_anchors_pixel_centers": {"right": list(backend.ANCHOR), "left": [backend.SIZE-1-backend.ANCHOR[0], backend.ANCHOR[1]]},
                "facing": "right plus exact pixel-mirrored left", "gameplay_authority": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".animation-forge-", dir=output.parent))
    try:
        (stage / "project.json").write_bytes(project_data)
        renders = {}
        for facing in ("right", "left"):
            folder = stage / "renders" / facing
            folder.mkdir(parents=True)
            records = []
            for index, pose in enumerate(snapshot["poses"], 1):
                image = core.render_pose(snapshot, pose["id"], facing=facing)
                if not isinstance(image, Image.Image) or image.mode != "RGBA" or image.size != (backend.SIZE, backend.SIZE):
                    raise ValueError("Renderer must return a common untrimmed RGBA canvas")
                if image.getchannel("A").getextrema()[0] != 0:
                    raise ValueError("Renderer must preserve transparent background pixels")
                relative = f"renders/{facing}/pose-{index:04d}.png"
                image.save(stage / relative, format="PNG", compress_level=9)
                records.append({"pose_id": pose["id"], "file": relative,
                                "sha256": _sha((stage / relative).read_bytes())})
            renders[facing] = records
        brief = _brief(snapshot, renders["right"], project_hash, renderer, diagnostics)
        _save_json(stage / "brief.json", brief)
        handoff = export_handoff(brief, stage, stage / "handoff")
        if handoff["forge_selection"] is None:
            raise ValueError("Authored project must provide visual holds and explicit loop policy")
        loop_selection = _loop_selection(stage, snapshot)
        legacy = _legacy_playback(stage, snapshot, renders["right"])
        playback = _authored_playback(stage, snapshot, renders) if _visual_timing(snapshot)["entry_then_loop"] else legacy
        manifest = {"schema": EXPORT_SCHEMA, "status": "diagnostic-unreviewed",
                    "project": {"file": "project.json", "sha256": project_hash,
                                "schema": snapshot["schema"], "source": snapshot["source"]},
                    "renderer": renderer, "renders": renders, "pose_diagnostics": diagnostics,
                    "visual_timing": _visual_timing(snapshot),
                    "handoff": {"manifest": "handoff/manifest.json", "review": "handoff/review.html",
                                "forge_selection": "handoff/forge-selection.json", "loop_selection": loop_selection},
                    "playback": playback, "legacy_playback": legacy, "gameplay_authority": False,
                    "review": {"anatomy": "unverified", "hands": "unverified", "contact": "unverified",
                               "rendering": "unverified", "runtime": "unverified", "user_acceptance": "unreviewed"}}
        _save_json(stage / "export.json", manifest)
        (stage / "index.html").write_text(_index(snapshot, playback), encoding="utf-8")
        if requested.exists() or requested.is_symlink() or output.exists():
            raise ValueError("Output appeared during export; preserving it")
        stage.rename(output)
    finally:
        if stage.exists():
            # stage is the exact directory created above, never a caller-supplied path.
            shutil.rmtree(stage)
    return {"index": "index.html", "project": "project.json", "manifest": "export.json",
            "review": "handoff/review.html", "handoff_manifest": "handoff/manifest.json",
            "forge_selection": "handoff/forge-selection.json", "playback": playback.get("page"),
            "loop_selection": loop_selection,
            "playback_status": playback["status"], "frame_count": len(snapshot["poses"]),
            "total_visual_ticks": handoff["total_visual_ticks"], "status": "diagnostic-unreviewed"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True, help="Saved Animation Forge JSON; reference projects retain local-source requirements")
    parser.add_argument("--output", type=Path, required=True, help="New local packet directory; never overwritten")
    args = parser.parse_args(argv)
    try:
        project = json.loads(args.project.read_text(encoding="utf-8-sig"))
        result = export_project(project, args.output)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"error: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
