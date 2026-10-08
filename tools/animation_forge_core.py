"""Deterministic, offline 2.5D construction mannequin, with original authored keys.

This backend extends the *geometry approach* of Other's 2026-10-08 v002
night-sky-walk proof: connected cross-section meshes, tapered limbs and clipped
two-band cel shading. No source skeleton, extracted transforms, motion, artwork,
or game assets from that reference are included or read. All dimensions and keys
below are an original synthetic authoring fixture, not a character/moveset.

Construction brief: adult proportions; fixed lengths; NO SQUASH; anatomical
orange right arm / blue left arm / magenta right leg / teal left leg; neutral
fixed light and orthographic camera. Torso is connected but static in v1. Hands
are simplified five-digit volumes, with wrist roll only; contact, corrective
skinning and surface intersections remain unverified. Triangle depth sorting
is a preview renderer limitation. Left-facing output mirrors the entire sprite.

There is no mutable scene, provider call, source clip clock or gameplay state.
Each pose fully resolves from its controls, independently of seek history.
"""
from __future__ import annotations

import copy
import math
import re
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

SCHEMA = "other-animation-forge.v1"
RIG_VERSION = "adult-mannequin.v1"
RENDERER_VERSION = "ortho-cel.v1"
SIZE = 640
ANCHOR = (320, 584)
SCALE = 3.0
AA = 2
INK = "#28313B"
COLORS = {"body": "#B7BEC7", "right_arm": "#DC8A47", "left_arm": "#609FD1",
          "right_leg": "#BA638D", "left_leg": "#58A79F"}
TARGETS = ("right_hand", "left_hand", "right_foot", "left_foot")
WRISTS = ("right_wrist", "left_wrist")
MAX_POSES = 128
MAX_EXPOSURES = 1024
MAX_TOTAL_TICKS = 216000
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


def default_project() -> dict:
    """Return a fresh editable original neutral/reach/return fixture."""
    controls = {"right_hand": [6.0, 23.0, 96.0],
                "left_hand": [1.0, -23.0, 96.0],
                "right_foot": [14.0, 12.0, 7.0],
                "left_foot": [-12.0, -12.0, 7.0],
                "right_wrist": 0.0, "left_wrist": 0.0}
    poses = []
    for pose_id, label, target, roll in (
        ("neutral", "Neutral", [6.0, 23.0, 96.0], 0.0),
        ("lift", "Lift", [29.0, 24.0, 124.0], 15.0),
        ("reach", "Reach", [49.0, 20.0, 145.0], 30.0),
        ("return", "Return", [25.0, 23.0, 115.0], 10.0),
    ):
        local = copy.deepcopy(controls)
        local["right_hand"] = target
        local["right_wrist"] = roll
        poses.append({"id": pose_id, "label": label, "controls": local})
    exposures = [{"pose_id": pose_id, "duration_ticks": hold} for pose_id, hold
                 in (("neutral", 24), ("lift", 8), ("reach", 18), ("return", 10))]
    return {"schema": SCHEMA, "name": "Neutral reach — original authoring fixture",
            "rig_version": RIG_VERSION, "renderer_version": RENDERER_VERSION,
            "source": {"kind": "authored", "description": "Original synthetic neutral reach/return keys; no imported motion or game rig.", "rate": None},
            "gameplay": {"status": "unassigned", "rate": 60},
            "exposure_rate": 60, "loop_policy": "cycle", "poses": poses,
            "exposures": exposures,
            "baseline": {"poses": copy.deepcopy(poses), "exposures": copy.deepcopy(exposures)}}


def _text(value: Any, field: str, limit: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} must be nonempty text of at most {limit} characters")


def _number(value: Any, field: str, low: float, high: float) -> None:
    if type(value) not in (int, float) or not low <= value <= high:
        raise ValueError(f"{field} must be a finite number in [{low}, {high}]")


def _timeline(poses: Any, exposures: Any, context: str) -> None:
    if not isinstance(poses, list) or not 1 <= len(poses) <= MAX_POSES:
        raise ValueError(f"{context}.poses must contain 1–{MAX_POSES} poses")
    ids = set()
    for pose in poses:
        if not isinstance(pose, dict):
            raise ValueError(f"{context}.pose must be an object")
        pose_id = pose.get("id")
        if not isinstance(pose_id, str) or not _ID.fullmatch(pose_id) or pose_id in ids:
            raise ValueError(f"{context}: pose IDs must be unique 1–64 character letters/numbers/hyphens/underscores")
        ids.add(pose_id)
        _text(pose.get("label"), f"{context}.{pose_id}.label", 120)
        controls = pose.get("controls")
        if not isinstance(controls, dict) or set(controls) != set(TARGETS + WRISTS):
            raise ValueError(f"{context}.{pose_id}: exactly four limb targets and two wrist rolls are required")
        for name in TARGETS:
            target = controls[name]
            if not isinstance(target, list) or len(target) != 3:
                raise ValueError(f"{pose_id}.{name} must be an [x, y, z] list in cm")
            for axis, value in enumerate(target):
                _number(value, f"{pose_id}.{name}[{axis}]", -180 if axis < 2 else -30, 180 if axis < 2 else 220)
        for name in WRISTS:
            _number(controls[name], f"{pose_id}.{name}", -180, 180)
    if not isinstance(exposures, list) or not 1 <= len(exposures) <= MAX_EXPOSURES:
        raise ValueError(f"{context}.exposures must contain 1–{MAX_EXPOSURES} entries")
    count = 0
    for exposure in exposures:
        if not isinstance(exposure, dict) or not isinstance(exposure.get("pose_id"), str) or exposure["pose_id"] not in ids:
            raise ValueError(f"{context}: every exposure must name an existing pose")
        ticks = exposure.get("duration_ticks")
        if type(ticks) is not int or not 1 <= ticks <= 3600:
            raise ValueError(f"{context}: duration_ticks must be an integer in [1, 3600]")
        count += ticks
    if count > MAX_TOTAL_TICKS:
        raise ValueError(f"{context}: timeline exceeds {MAX_TOTAL_TICKS} ticks")


def validate_project(project: Any) -> None:
    """Validate bounded portable data; return None, or raise ValueError."""
    if not isinstance(project, dict) or project.get("schema") != SCHEMA:
        raise ValueError(f"Expected schema {SCHEMA}")
    _text(project.get("name"), "name", 160)
    if project.get("rig_version", RIG_VERSION) != RIG_VERSION:
        raise ValueError("Unsupported rig_version")
    if project.get("renderer_version", RENDERER_VERSION) != RENDERER_VERSION:
        raise ValueError("Unsupported renderer_version")
    source = project.get("source")
    if not isinstance(source, dict) or source.get("kind") != "authored" or source.get("rate", 0) is not None:
        raise ValueError("v1 requires authored source with rate null; no source-motion importer exists")
    _text(source.get("description"), "source.description", 2000)
    gameplay = project.get("gameplay")
    if gameplay != {"status": "unassigned", "rate": 60} or type(gameplay.get("rate")) is not int:
        raise ValueError("Gameplay must remain unassigned with rate 60; visual holds are not gameplay data")
    if type(project.get("exposure_rate")) is not int or project["exposure_rate"] != 60:
        raise ValueError("exposure_rate must be integer 60")
    if project.get("loop_policy") not in ("cycle", "oneshot"):
        raise ValueError("loop_policy must be cycle or oneshot")
    _timeline(project.get("poses"), project.get("exposures"), "project")
    baseline = project.get("baseline")
    if not isinstance(baseline, dict):
        raise ValueError("baseline must preserve poses and exposures")
    _timeline(baseline.get("poses"), baseline.get("exposures"), "baseline")
    if {pose["id"] for pose in baseline["poses"]} != {pose["id"] for pose in project["poses"]}:
        raise ValueError("baseline and current pose IDs must match for before/after comparison")


def total_ticks(project: dict) -> int:
    validate_project(project)
    return sum(item["duration_ticks"] for item in project["exposures"])


def pose_at_tick(project: dict, tick: int) -> str:
    """Stateless integer visual-tick evaluation; oneshot holds the last pose."""
    validate_project(project)
    if type(tick) is not int or not 0 <= tick <= 2**53 - 1:
        raise ValueError("tick must be a nonnegative safe integer")
    total = sum(item["duration_ticks"] for item in project["exposures"])
    local = tick % total if project["loop_policy"] == "cycle" else min(tick, total - 1)
    for item in project["exposures"]:
        if local < item["duration_ticks"]:
            return item["pose_id"]
        local -= item["duration_ticks"]
    raise AssertionError("Validated exposure schedule did not resolve")


def _unit(vector: np.ndarray) -> np.ndarray:
    return vector / max(float(np.linalg.norm(vector)), 1e-12)


def _ik(root: np.ndarray, target: np.ndarray, a: float, b: float,
        pole: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    delta = target - root
    distance = float(np.linalg.norm(delta))
    direction = delta / distance if distance > 1e-9 else np.array([0., 0., -1.])
    reached = min(max(distance, abs(a-b) + 1e-5), a+b-1e-5)
    end = root + direction * reached
    bend = pole - direction * np.dot(pole, direction)
    if np.linalg.norm(bend) < 1e-8:
        fallback = np.eye(3)[int(np.argmin(np.abs(direction)))]
        bend = fallback - direction * np.dot(fallback, direction)
    axis_distance = (a*a - b*b + reached*reached) / (2*reached)
    height = math.sqrt(max(0.0, a*a - axis_distance*axis_distance))
    middle = root + direction*axis_distance + _unit(bend)*height
    return middle, end, abs(distance-reached)


def evaluate_pose(project: dict, pose_id: str, baseline: bool = False) -> dict:
    """Resolve all controls into fixed-length joints and explicit IK diagnostics."""
    validate_project(project)
    if type(baseline) is not bool:
        raise ValueError("baseline must be boolean")
    poses = project["baseline"]["poses"] if baseline else project["poses"]
    pose = next((item for item in poses if item["id"] == pose_id), None)
    if pose is None:
        raise ValueError(f"Unknown {'baseline ' if baseline else ''}pose: {pose_id}")
    controls = pose["controls"]
    joints = {"pelvis": [0., 0., 98.], "chest": [0., 0., 139.],
              "neck": [0., 0., 154.], "head": [0., 0., 170.]}
    diagnostics, lengths, resolved = [], {}, {}
    for side, sign in (("right", 1), ("left", -1)):
        for limb, endpoint, root_name, mid_name, root, a, b, pole in (
            ("arm", "hand", "shoulder", "elbow", [0., sign*18., 146.], 31., 27., [-1., sign*.15, 0.]),
            ("leg", "foot", "hip", "knee", [0., sign*10., 98.], 47., 46., [1., 0., 0.]),
        ):
            key = f"{side}_{endpoint}"
            root, target = np.asarray(root), np.asarray(controls[key], dtype=float)
            middle, end, error = _ik(root, target, a, b, np.asarray(pole))
            joints[f"{side}_{root_name}"] = root.tolist()
            joints[f"{side}_{mid_name}"] = middle.tolist()
            joints[key] = end.tolist()
            lengths[f"{side}_{limb}_upper"] = float(np.linalg.norm(middle-root))
            lengths[f"{side}_{limb}_lower"] = float(np.linalg.norm(end-middle))
            resolved[key] = end.tolist()
            if error > 1e-6:
                diagnostics.append({"code": "unreachable_target", "control": key,
                                    "message": f"{key}: target clamped by {error:.3f} cm; limb lengths unchanged.",
                                    "error_cm": error, "requested": target.tolist(), "resolved": end.tolist()})
            if endpoint == "foot" and end[2] < 7-1e-6:
                diagnostics.append({"code": "foot_below_ground", "control": key,
                                    "message": f"{key}: sole is {7-end[2]:.3f} cm below ground; no hidden contact correction.",
                                    "depth_cm": float(7-end[2])})
    state = {"pose_id": pose_id, "joints": joints, "controls": copy.deepcopy(controls),
             "resolved_targets": resolved, "segment_lengths": lengths, "diagnostics": diagnostics,
             "rig_version": RIG_VERSION}
    vertices = np.concatenate([shape[0] for shape in _geometry(state)])
    projected = np.stack((ANCHOR[0]+SCALE*(math.sqrt(.75)*vertices[:, 0]-.5*vertices[:, 1]),
                          ANCHOR[1]-SCALE*vertices[:, 2]), axis=-1)
    bounds = [float(projected[:, 0].min()), float(projected[:, 1].min()),
              float(projected[:, 0].max()), float(projected[:, 1].max())]
    state["projected_bounds"] = bounds
    if min(bounds[:2]) < 3 or max(bounds[2:]) > SIZE-3:
        diagnostics.append({"code": "outside_canvas", "message": "Pose extends beyond the fixed canvas; no auto-fit or squash is applied.",
                            "bounds_px": bounds})
    return state


def _mesh(vertices, faces, color):
    verts, faces = np.asarray(vertices, dtype=float), np.asarray(faces, dtype=int)
    face_normals = np.cross(verts[faces[:, 1]]-verts[faces[:, 0]], verts[faces[:, 2]]-verts[faces[:, 0]])
    normals = np.zeros_like(verts)
    for col in range(3):
        np.add.at(normals, faces[:, col], face_normals)
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    return verts, normals, color, faces


def _rings(rings, color, reverse=False):
    count = len(rings[0])
    faces = []
    for j in range(len(rings)-1):
        for i in range(count):
            a, b = j*count+i, j*count+(i+1) % count
            c, d = (j+1)*count+i, (j+1)*count+(i+1) % count
            faces.extend([(a, c, b), (b, c, d)] if reverse else [(a, b, c), (b, d, c)])
    return _mesh(np.concatenate(rings), faces, color)


def _ellipsoid(center, radii, color, rotation=None, divisions=16):
    rotation = np.eye(3) if rotation is None else rotation
    rings = []
    for j in range(9):
        phi = math.pi*j/8
        ring = np.array([[math.sin(phi)*math.cos(i*2*math.pi/divisions),
                          math.sin(phi)*math.sin(i*2*math.pi/divisions), math.cos(phi)]
                         for i in range(divisions)])
        rings.append((ring*np.asarray(radii)) @ rotation.T + center)
    # Latitude runs top-to-bottom, so reverse the ascending-ring winding.
    return _rings(rings, color, reverse=True)


def _limb(a, b, start_radius, end_radius, color, bulge=1.1, divisions=16):
    axis = _unit(b-a)
    u = np.cross(axis, [0., 0., 1.])
    if np.linalg.norm(u) < .01:
        u = np.cross(axis, [0., 1., 0.])
    u = _unit(u)
    v = np.cross(axis, u)
    length = float(np.linalg.norm(b-a))
    rings = []
    for t, multiplier in ((-.06, 0), (0, 1), (.18, bulge), (.4, bulge), (.7, 1), (1, 1), (1.06, 0)):
        radius = (start_radius + (end_radius-start_radius)*max(0, min(1, t))) * multiplier
        rings.append(np.array([a + axis*(length*t) + radius*(u*math.cos(i*2*math.pi/divisions)
                             + v*math.sin(i*2*math.pi/divisions)) for i in range(divisions)]))
    # Axis basis has cross(u,v)=axis; ascending rings face outward.
    return _rings(rings, color)


def _torso():
    rings = []
    # Fixed connected adult torso: x depth, y breadth, z height. No pose scaling.
    for z, width, depth_radius in ((86, 0, 0), (89, 11, 7), (96, 16, 9), (103, 15, 8),
                                  (113, 12, 8), (124, 16, 10), (136, 21, 11),
                                  (144, 19, 10), (149, 10, 7), (152, 5, 5), (153, 0, 0)):
        rings.append(np.array([[depth_radius*math.cos(i*math.pi/8), width*math.sin(i*math.pi/8), z] for i in range(16)]))
    return _rings(rings, COLORS["body"])


def _foot(ankle, color):
    rings = []
    # Original fixed flat sole with connected heel, instep and toe envelope.
    for x, width, top, sole in ((-6, 0, -3, -3), (-5, 3.5, -1, -6.7), (0, 4.4, 5, -7),
                                (6, 4.7, 2, -7), (12, 4.8, -2, -7), (17, 4.3, -3.2, -6.9),
                                (21, 2.6, -4.7, -6.6), (22, 0, -5.6, -5.6)):
        rings.append(np.array([ankle + np.array([x, width*math.cos(i*math.pi/8),
                            sole+(top-sole)*max(0, math.sin(i*math.pi/8))]) for i in range(16)]))
    return _rings(rings, color)


def _hand(wrist, elbow, roll, side, color):
    direction = _unit(wrist-elbow)
    across = np.array([0., 1., 0.])
    across = across-direction*np.dot(across, direction)
    if np.linalg.norm(across) < .1:
        across = np.array([1., 0., 0.])-direction*direction[0]
    across = _unit(across)
    normal = _unit(np.cross(across, direction))
    angle = math.radians(roll)
    across, normal = across*math.cos(angle)+normal*math.sin(angle), normal*math.cos(angle)-across*math.sin(angle)
    rotation = np.stack([across, normal, direction], axis=1)
    shapes = [_ellipsoid(wrist+direction*3.2, [3.9, 1.85, 4.3], color, rotation)]
    # Four fingers plus a separate thumb; thumb side follows anatomical chirality.
    for offset, length in ((-2.8, 4.5), (-.95, 5.5), (.95, 6.0), (2.8, 5.2)):
        base = wrist+direction*6.1+across*offset
        middle = base+direction*(length*.55)+normal*.3
        tip = base+direction*length+normal*1.0
        shapes += [_limb(base, middle, .9, .8, color, 1, 8), _limb(middle, tip, .8, .65, color, 1, 8)]
    sign = -1 if side == "right" else 1
    base = wrist+direction*2.5+across*(sign*3)
    middle = base+direction*2.2+across*(sign*2.2)+normal*.7
    tip = middle+direction*2.4+normal*.6
    shapes += [_limb(base, middle, 1.15, .9, color, 1, 8), _limb(middle, tip, .9, .7, color, 1, 8)]
    return shapes


def _geometry(evaluated):
    joints = {name: np.asarray(value) for name, value in evaluated["joints"].items()}
    body = COLORS["body"]
    shapes = [_torso(), _limb(np.array([0., 0., 149.]), np.array([0., 0., 161.]), 5, 4.8, body, 1),
              _ellipsoid(joints["head"], [8.6, 8.0, 11.7], body),
              _ellipsoid(joints["head"]+np.array([8.0, 0., -.3]), [3.1, 2.2, 3.0], body)]
    for side in ("right", "left"):
        arm, leg = COLORS[side+"_arm"], COLORS[side+"_leg"]
        for a, b, ra, rb, col, bulge in (("shoulder", "elbow", 5.9, 3.8, arm, 1.08),
                                        ("elbow", "hand", 3.8, 2.5, arm, 1.16),
                                        ("hip", "knee", 8.4, 4.9, leg, 1.08),
                                        ("knee", "foot", 4.9, 2.8, leg, 1.2)):
            shapes.append(_limb(joints[side+"_"+a], joints[side+"_"+b], ra, rb, col, bulge))
        for name, radius, color in (("shoulder", 5.5, arm), ("elbow", 3.5, arm), ("knee", 4.5, leg)):
            shapes.append(_ellipsoid(joints[side+"_"+name], [radius]*3, color))
        shapes.append(_foot(joints[side+"_foot"], leg))
        shapes += _hand(joints[side+"_hand"], joints[side+"_elbow"], evaluated["controls"][side+"_wrist"], side, arm)
    return shapes


def render_pose(project: dict, pose_id: str, baseline: bool = False, facing: str = "right") -> Image.Image:
    """Render a complete fixed-camera state as a transparent straight-alpha PNG image."""
    if facing not in ("left", "right"):
        raise ValueError("facing must be left or right")
    state = evaluate_pose(project, pose_id, baseline)
    image = Image.new("RGBA", (SIZE*AA, SIZE*AA), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    camera = np.array([.5, math.sqrt(.75), 0.])
    light = _unit(np.array([-.4, .35, 1.]))
    packets = []
    for verts, normals, color, faces in _geometry(state):
        xy = np.stack((ANCHOR[0]+SCALE*(math.sqrt(.75)*verts[:, 0]-.5*verts[:, 1]),
                       ANCHOR[1]-SCALE*verts[:, 2]), axis=-1)*AA
        depths = verts @ camera
        lighting = normals @ light + .04
        bases = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
        shadow, bright = tuple(int(v*.58) for v in bases)+(255,), bases+(255,)
        visible = (normals[faces].mean(axis=1) @ camera) >= 0
        for ids in faces[visible]:
            polygon = [(xy[k], lighting[k]) for k in ids]
            lit = []
            for index, (point, value) in enumerate(polygon):
                previous, previous_value = polygon[index-1]
                if (value >= 0) != (previous_value >= 0):
                    lit.append(previous+(point-previous)*(-previous_value/(value-previous_value)))
                if value >= 0:
                    lit.append(point)
            packets.append((float(depths[ids].mean()), [tuple(point) for point in xy[ids]], shadow,
                            [tuple(point) for point in lit], bright))
    for _, polygon, shadow, lit, bright in sorted(packets, key=lambda packet: packet[0]):
        draw.polygon(polygon, fill=shadow)
        if len(lit) > 2:
            draw.polygon(lit, fill=bright)
    outline = image.getchannel("A").filter(ImageFilter.MaxFilter(5))
    backing = Image.new("RGBA", image.size, INK)
    backing.putalpha(outline)
    backing.alpha_composite(image)
    result = backing.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    return ImageOps.mirror(result) if facing == "left" else result
