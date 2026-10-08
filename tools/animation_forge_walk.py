"""Editable, reference-only adapter for the preserved local Night Sky walk proof.

No source skeleton, motion or image assets are bundled here. This module reads
only four fixed project-local paths and verifies their pinned hashes before
loading them. The original proof renderer is executed only after its exact code
hash matches, with no bytecode/file writes. Unedited poses use the preserved
timed atlas pixels. Edits use source-anchored IK with fixed bone lengths, then
the same connected torso/foot geometry and fixed camera from the proof.

Controls are absolute component-space cm; wrist angles are local roll deltas.
Source sample timing, editable visual exposure and unassigned gameplay remain
separate. Local saved projects containing source-derived targets remain
reference-only and require the original pinned local source files on reopen.
"""
from __future__ import annotations

import copy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import threading
import types

import numpy as np
from PIL import Image, ImageOps

if __package__:
    from . import animation_forge_core as core
else:
    import animation_forge_core as core

SCHEMA = "other-animation-forge.walk.v1"
RIG_VERSION = "night-sky-local-source.v1"
RENDERER_VERSION = "night-sky-v002-edit.v1"
SIZE = 640
ANCHOR = (293, 567)
SCALE = 2.7
_WORKSPACE = Path(__file__).resolve().parents[4]
_STUDY = _WORKSPACE / "Game/Saved/ArtResearch/NightSkyWalk-20261008"
_PROOF = _WORKSPACE / "Documentation/Art/AnimationProofs/night-sky-walk/v002"
_PATHS = {"timeline": _STUDY / "walk-timeline.json", "poses": _STUDY / "walk-poses.json",
          "renderer": _PROOF / "render_proof.py", "atlas": _PROOF / "timed-mannequin-atlas.png"}
_HASHES = {"timeline": "03b27ec79b3bb04b5f06fe1316fc47a43396d83088ccb893408725f2eccc7574",
           "poses": "f488fa3550e26c6c4cb93fcf666eee449cc5343578ff60d70ca2c6f59bf6db9a",
           "renderer": "049234f99ca1b362063220865563ee6e6845472e46c15448d6b08bb01abf02fe",
           "atlas": "ed3098c19a1af17378308b9aa9cd4bb894c57cee664a7ea93ff33cb2f86c76b2"}
_SOURCE = {"kind": "reference-only", "id": "night-sky-walk-v002", "rate": 60,
           "description": "Preserved Night Sky source walk with local target edits; source-derived reference, not original choreography.",
           "repository": "https://github.com/WistfulHopes/NightSkyEngine",
           "revision": "f26e5a17de2d2de13ce9c3f1867170e2144f4cb0",
           "rights": "reference-only-not-cleared", "hashes": _HASHES,
           "timing_status": "Source-graph reconstructed 10-tick entry and 62-tick loop; full runtime phase/reset unverified."}
_LOCK = threading.RLock()
_POSE_IDS = tuple(f"walk-{i:02d}" for i in range(72))


def _signature():
    try:
        return tuple((str(path), path.stat().st_size, path.stat().st_mtime_ns) for path in _PATHS.values())
    except OSError as exc:
        raise ValueError(f"Local walk source is unavailable: {exc}") from exc


@lru_cache(maxsize=1)
def _load(signature):
    # The signature avoids rehashing ~9 MB for every UI evaluation. A changed
    # path/stat forces a new hash verification before any source code executes.
    raw = {}
    for name, path in _PATHS.items():
        try:
            raw[name] = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"Missing local walk {name}: {path}") from exc
        if hashlib.sha256(raw[name]).hexdigest() != _HASHES[name]:
            raise ValueError(f"Pinned local walk {name} hash mismatch; preserved reference was changed")
    timeline = json.loads(raw["timeline"])
    if len(timeline.get("frames", [])) != 72 or timeline.get("entry_ticks") != 10 or timeline.get("loop_ticks") != 62:
        raise ValueError("Pinned local walk timeline has unexpected structure")
    renderer = types.ModuleType("_other_preserved_walk_v002")
    renderer.__file__ = str(_PATHS["renderer"])
    # compile/exec avoids importlib creating __pycache__ in the immutable proof.
    exec(compile(raw["renderer"], str(_PATHS["renderer"]), "exec"), renderer.__dict__)
    with Image.open(_PATHS["atlas"]) as source_image:
        atlas = source_image.convert("RGBA")
    if atlas.size != (SIZE*8, SIZE*9):
        raise ValueError("Pinned local walk atlas must be 8 × 9 frames")
    poses = []
    bounds = []
    for i, frame in enumerate(timeline["frames"]):
        controls = {}
        for side, suffix in (("right", "r"), ("left", "l")):
            for end in ("hand", "foot"):
                controls[f"{side}_{end}"] = copy.deepcopy(frame["bones"][f"{end}_{suffix}"]["position"])
            controls[f"{side}_wrist"] = 0.0
        poses.append({"id": _POSE_IDS[i], "label": f"{'Entry' if i < 10 else 'Loop'} {i:02d}",
                      "source_sample": i, "source_frame": frame["source_frame"], "controls": controls})
        x, y = (i % 8)*SIZE, (i // 8)*SIZE
        bounds.append(list(atlas.crop((x, y, x+SIZE, y+SIZE)).getbbox()))
    exposures = [{"pose_id": pose_id, "duration_ticks": 1} for pose_id in _POSE_IDS]
    baseline = {"poses": poses, "exposures": exposures, "loop_start": 10}
    return {"timeline": timeline, "renderer": renderer, "atlas": atlas, "baseline": baseline, "bounds": bounds}


def _resources():
    with _LOCK:
        return _load(_signature())


def availability() -> dict:
    """Return usable status without downloading, rewriting or relocating data."""
    try:
        _resources()
        return {"available": True, "error": None, "source_id": _SOURCE["id"]}
    except (ValueError, OSError) as exc:
        return {"available": False, "error": str(exc), "source_id": _SOURCE["id"]}


def default_project() -> dict:
    baseline = copy.deepcopy(_resources()["baseline"])
    return {"schema": SCHEMA, "name": "Preserved walk — editable local reference",
            "rig_version": RIG_VERSION, "renderer_version": RENDERER_VERSION,
            "source": copy.deepcopy(_SOURCE), "gameplay": {"status": "unassigned", "rate": 60},
            "exposure_rate": 60, "loop_policy": "cycle", "loop_start": 10,
            "poses": copy.deepcopy(baseline["poses"]), "exposures": copy.deepcopy(baseline["exposures"]),
            "baseline": baseline}


def validate_project(project) -> None:
    resources = _resources()
    if not isinstance(project, dict) or project.get("schema") != SCHEMA:
        raise ValueError(f"Expected schema {SCHEMA}")
    core._text(project.get("name"), "name", 160)
    if project.get("rig_version") != RIG_VERSION or project.get("renderer_version") != RENDERER_VERSION:
        raise ValueError("Walk rig and renderer versions must match the pinned local source")
    if project.get("source") != _SOURCE or type(project["source"].get("rate")) is not int:
        raise ValueError("Walk source provenance must remain exactly pinned; arbitrary source paths are unsupported")
    gameplay = project.get("gameplay")
    if gameplay != {"status": "unassigned", "rate": 60} or type(gameplay.get("rate")) is not int:
        raise ValueError("Gameplay remains unassigned at 60 Hz; visual holds are not gameplay timing")
    if type(project.get("exposure_rate")) is not int or project["exposure_rate"] != 60:
        raise ValueError("exposure_rate must be integer 60")
    if project.get("loop_policy") not in ("cycle", "oneshot"):
        raise ValueError("loop_policy must be cycle or oneshot")
    if type(project.get("loop_start")) is not int or project["loop_start"] != 10:
        raise ValueError("The preserved source loop starts at exposure index 10")
    core._timeline(project.get("poses"), project.get("exposures"), "walk")
    if [pose["id"] for pose in project["poses"]] != list(_POSE_IDS):
        raise ValueError("Keep all 72 pinned source pose IDs in source order")
    if [item["pose_id"] for item in project["exposures"]] != list(_POSE_IDS):
        raise ValueError("The walk requires one exposure per pinned source sample in source order")
    for pose, source in zip(project["poses"], resources["baseline"]["poses"]):
        core._number(pose.get("source_frame"), "source_frame", 0, 50)
        if type(pose.get("source_sample")) is not int or pose["source_sample"] != source["source_sample"] or pose.get("source_frame") != source["source_frame"]:
            raise ValueError("A pose's source sample and fractional source frame are immutable")
    baseline = project.get("baseline")
    if not isinstance(baseline, dict) or type(baseline.get("loop_start")) is not int:
        raise ValueError("Walk baseline must preserve its exposure-index loop start")
    core._timeline(baseline.get("poses"), baseline.get("exposures"), "walk baseline")
    if project.get("baseline") != resources["baseline"]:
        raise ValueError("The walk baseline is immutable and must equal the pinned original targets and exposure")


def total_ticks(project: dict) -> int:
    validate_project(project)
    return sum(item["duration_ticks"] for item in project["exposures"])


def pose_at_tick(project: dict, tick: int) -> str:
    validate_project(project)
    if type(tick) is not int or not 0 <= tick <= 2**53-1:
        raise ValueError("tick must be a nonnegative safe integer")
    exposures = project["exposures"]
    total = sum(item["duration_ticks"] for item in exposures)
    entry = sum(item["duration_ticks"] for item in exposures[:project["loop_start"]])
    if project["loop_policy"] == "oneshot":
        local = min(tick, total-1)
    else:
        local = tick if tick < total else entry+(tick-entry) % (total-entry)
    for exposure in exposures:
        if local < exposure["duration_ticks"]:
            return exposure["pose_id"]
        local -= exposure["duration_ticks"]
    raise AssertionError("Validated walk exposure did not resolve")


def _rotation_between(before, after):
    before, after = core._unit(before), core._unit(after)
    cosine = float(np.clip(np.dot(before, after), -1., 1.))
    axis = np.cross(before, after)
    sine = float(np.linalg.norm(axis))
    if sine < 1e-10:
        if cosine > 0:
            return np.eye(3)
        fallback = np.eye(3)[int(np.argmin(np.abs(before)))]
        axis = core._unit(np.cross(before, fallback))
        return 2*np.outer(axis, axis)-np.eye(3)
    axis /= sine
    return _axis_angle(axis, math.atan2(sine, cosine))


def _axis_angle(axis, angle):
    x, y, z = core._unit(np.asarray(axis))
    cross = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
    return np.eye(3)+math.sin(angle)*cross+(1-math.cos(angle))*(cross@cross)


def _quaternion(matrix):
    # Stable matrix-to-xyzw quaternion without adding a dependency to the proof.
    trace = float(np.trace(matrix))
    if trace > 0:
        s = math.sqrt(trace+1)*2
        q = np.array([(matrix[2, 1]-matrix[1, 2])/s, (matrix[0, 2]-matrix[2, 0])/s,
                      (matrix[1, 0]-matrix[0, 1])/s, .25*s])
    else:
        i = int(np.argmax(np.diag(matrix)))
        j, k = (i+1) % 3, (i+2) % 3
        s = math.sqrt(max(0., 1+matrix[i, i]-matrix[j, j]-matrix[k, k]))*2
        q = np.zeros(4)
        q[i] = .25*s
        q[j], q[k] = (matrix[j, i]+matrix[i, j])/s, (matrix[k, i]+matrix[i, k])/s
        q[3] = (matrix[k, j]-matrix[j, k])/s
    q /= np.linalg.norm(q)
    return q.tolist()


def _transform_bone(bone, delta, old_origin, new_origin, renderer):
    result = copy.deepcopy(bone)
    result["position"] = (delta@(np.asarray(bone["position"])-old_origin)+new_origin).tolist()
    result["rotation"] = _quaternion(delta@renderer.qmatrix(bone["rotation"]))
    return result


def _resolve(project, pose_id, baseline=False):
    validate_project(project)
    if type(baseline) is not bool:
        raise ValueError("baseline must be boolean")
    if pose_id not in _POSE_IDS:
        raise ValueError(f"Unknown walk pose: {pose_id}")
    index = _POSE_IDS.index(pose_id)
    resources = _resources()
    original = resources["baseline"]["poses"][index]
    pose = original if baseline else project["poses"][index]
    controls = pose["controls"]
    renderer = resources["renderer"]
    source_bones = resources["timeline"]["frames"][index]["bones"]
    bones = copy.deepcopy(source_bones)
    diagnostics, lengths, resolved = [], {}, {}
    edited = controls != original["controls"]
    for side, suffix in (("right", "r"), ("left", "l")):
        for limb, root_name, mid_name, end_name in (("arm", "upperarm", "lowerarm", "hand"), ("leg", "thigh", "calf", "foot")):
            names = [f"{name}_{suffix}" for name in (root_name, mid_name, end_name)]
            root, middle, end = [np.asarray(source_bones[name]["position"], dtype=float) for name in names]
            a, b = float(np.linalg.norm(middle-root)), float(np.linalg.norm(end-middle))
            control = f"{side}_{end_name}"
            target = np.asarray(controls[control], dtype=float)
            endpoint_changed = controls[control] != original["controls"][control]
            roll = controls[f"{side}_wrist"] if limb == "arm" else 0.
            new_middle, new_end = middle, end
            upper_delta = lower_delta = np.eye(3)
            if endpoint_changed:
                pole = middle-root
                new_middle, new_end, error = core._ik(root, target, a, b, pole)
                upper_delta = _rotation_between(middle-root, new_middle-root)
                lower_delta = _rotation_between(end-middle, new_end-new_middle)
                bones[names[0]] = _transform_bone(source_bones[names[0]], upper_delta, root, root, renderer)
                bones[names[1]] = _transform_bone(source_bones[names[1]], lower_delta, middle, new_middle, renderer)
                if error > 1e-6:
                    diagnostics.append({"code": "unreachable_target", "control": control,
                                        "message": f"{control}: clamped {error:.3f} cm; source limb lengths preserved.",
                                        "error_cm": error, "requested": target.tolist(), "resolved": new_end.tolist()})
            if endpoint_changed or roll:
                delta = _axis_angle(new_end-new_middle, math.radians(roll))@lower_delta if roll else lower_delta
                # The proof reads palm/finger/foot/toe bones directly. Apply a
                # rigid descendant transform, retaining original local shape.
                descendants = [names[2]]
                if limb == "arm":
                    descendants += [name for name in source_bones if name.endswith("_"+suffix)
                                    and name.startswith(("thumb_", "index_", "middle_", "ring_", "pinky_", "wrist_", "weapon_"))]
                else:
                    descendants += [name for name in source_bones if name.endswith("_"+suffix) and name.startswith(("ball_", "ankle_"))]
                for name in descendants:
                    bones[name] = _transform_bone(source_bones[name], delta, end, new_end, renderer)
            lengths[f"{side}_{limb}_upper"] = float(np.linalg.norm(new_middle-root))
            lengths[f"{side}_{limb}_lower"] = float(np.linalg.norm(new_end-new_middle))
            resolved[control] = new_end.tolist()
            if limb == "leg" and endpoint_changed:
                sole_min = float(renderer.articulated_foot(bones, suffix)[0][:, 2].min())
                if sole_min < -.01:
                    diagnostics.append({"code": "foot_below_ground", "control": control,
                                        "message": f"{control}: edited foot surface penetrates ground by {-sole_min:.3f} cm; no contact correction applied.",
                                        "depth_cm": -sole_min})
    if edited:
        vertices = np.concatenate([shape[0] for shape in renderer.geometry(bones)])
        projected = renderer.project(vertices)
        bounds = [float(projected[:, 0].min()), float(projected[:, 1].min()), float(projected[:, 0].max()), float(projected[:, 1].max())]
        if min(bounds[:2]) < 3 or max(bounds[2:]) > SIZE-3:
            diagnostics.append({"code": "outside_canvas", "message": "Edited pose extends outside the preserved camera; no auto-fit or squash applied.", "bounds_px": bounds})
    else:
        bounds = resources["bounds"][index]
    joints = {name: copy.deepcopy(bone["position"]) for name, bone in bones.items()}
    state = {"pose_id": pose_id, "source_sample": index, "source_frame": original["source_frame"],
             "source_id": _SOURCE["id"], "source_hashes": copy.deepcopy(_HASHES),
             "rig_version": RIG_VERSION, "renderer_version": RENDERER_VERSION,
             "joints": joints, "controls": copy.deepcopy(controls), "resolved_targets": resolved,
             "segment_lengths": lengths, "diagnostics": diagnostics, "projected_bounds": copy.deepcopy(bounds),
             "edited": edited, "reference_only": True}
    return state, bones


def evaluate_pose(project: dict, pose_id: str, baseline: bool = False) -> dict:
    return _resolve(project, pose_id, baseline)[0]


def render_pose(project: dict, pose_id: str, baseline: bool = False, facing: str = "right") -> Image.Image:
    if facing not in ("right", "left"):
        raise ValueError("facing must be right or left")
    state, bones = _resolve(project, pose_id, baseline)
    resources = _resources()
    if state["edited"]:
        image = resources["renderer"].render(bones)
    else:
        index = state["source_sample"]
        x, y = (index % 8)*SIZE, (index // 8)*SIZE
        image = resources["atlas"].crop((x, y, x+SIZE, y+SIZE))
    return ImageOps.mirror(image) if facing == "left" else image
