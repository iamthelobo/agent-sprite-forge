"""Optional local-reference tests; no copied source assets belong in the repo.

These tests skip when the exact project-local proof is unavailable. The local
Other implementation run must report actual passes separately from such skips.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import animation_forge_walk as walk


def png(image):
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


AVAILABILITY = walk.availability()


@unittest.skipUnless(AVAILABILITY["available"], AVAILABILITY["error"] or "Local proof unavailable")
class PreservedWalkTests(unittest.TestCase):
    def setUp(self):
        self.project = walk.default_project()

    def test_all_72_unedited_pixels_are_exact_preserved_atlas_crops(self):
        with Image.open(walk._PATHS["atlas"]) as source:
            atlas = source.convert("RGBA")
        for index, pose in enumerate(self.project["poses"]):
            x, y = (index % 8)*640, (index // 8)*640
            expected = atlas.crop((x, y, x+640, y+640))
            actual = walk.render_pose(self.project, pose["id"])
            self.assertEqual(actual.mode, "RGBA")
            self.assertEqual(actual.size, (640, 640))
            self.assertEqual(actual.tobytes(), expected.tobytes(), pose["id"])
            self.assertEqual(actual.getchannel("A").getextrema(), (0, 255))

    def test_pinned_renderer_reproduces_preserved_sample(self):
        # Independently exercise the renderer rather than only testing crop math.
        resources = walk._resources()
        for sample in (10, 34):
            expected = walk.render_pose(self.project, f"walk-{sample:02d}")
            actual = resources["renderer"].render(resources["timeline"]["frames"][sample]["bones"])
            self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_entry_runs_once_and_loop_boundary_tracks_changed_holds(self):
        self.assertEqual(walk.total_ticks(self.project), 72)
        for tick, expected in ((0, 0), (9, 9), (10, 10), (71, 71), (72, 10), (133, 71), (134, 10)):
            self.assertEqual(walk.pose_at_tick(self.project, tick), f"walk-{expected:02d}")
        self.project["exposures"][0]["duration_ticks"] = 4
        self.project["exposures"][34]["duration_ticks"] = 6
        self.assertEqual(walk.total_ticks(self.project), 80)
        self.assertEqual(walk.pose_at_tick(self.project, 12), "walk-09")
        self.assertEqual(walk.pose_at_tick(self.project, 13), "walk-10")
        self.assertEqual(walk.pose_at_tick(self.project, 80), "walk-10")
        self.assertEqual(walk.pose_at_tick(self.project, 147), "walk-10")
        self.project["loop_policy"] = "oneshot"
        self.assertEqual(walk.pose_at_tick(self.project, 80), "walk-71")

    def test_seek_reset_is_deterministic_and_baseline_is_unchanged(self):
        original = walk.evaluate_pose(self.project, "walk-34")
        original_png = png(walk.render_pose(self.project, "walk-34"))
        self.project["poses"][34]["controls"]["right_hand"][0] -= 5
        edited = walk.evaluate_pose(self.project, "walk-34")
        edited_png = png(walk.render_pose(self.project, "walk-34"))
        samples = list(range(72))
        random.Random(314).shuffle(samples)
        for sample in samples:
            walk.evaluate_pose(self.project, f"walk-{sample:02d}")
        self.assertEqual(walk.evaluate_pose(self.project, "walk-34"), edited)
        self.assertEqual(png(walk.render_pose(self.project, "walk-34")), edited_png)
        self.assertEqual(walk.evaluate_pose(self.project, "walk-34", baseline=True), original)
        self.assertEqual(png(walk.render_pose(self.project, "walk-34", baseline=True)), original_png)

    def test_hand_edit_is_local_fixed_length_and_rigid_for_fingers(self):
        before_state, before_bones = walk._resolve(self.project, "walk-34")
        self.project["poses"][34]["controls"]["right_hand"][0] += 8
        after_state, after_bones = walk._resolve(self.project, "walk-34")
        self.assertIn("unreachable_target", [item["code"] for item in after_state["diagnostics"]])
        for name, length in before_state["segment_lengths"].items():
            self.assertAlmostEqual(after_state["segment_lengths"][name], length, places=9)
        for name in ("pelvis", "head", "upperarm_r", "hand_l", "foot_l", "foot_r"):
            self.assertEqual(before_state["joints"][name], after_state["joints"][name])
        self.assertNotEqual(before_state["joints"]["lowerarm_r"], after_state["joints"]["lowerarm_r"])
        for name in ("thumb_01_r", "thumb_03_r", "middle_03_r", "pinky_03_r"):
            before = np.asarray(before_bones[name]["position"])-np.asarray(before_bones["hand_r"]["position"])
            after = np.asarray(after_bones[name]["position"])-np.asarray(after_bones["hand_r"]["position"])
            self.assertAlmostEqual(float(np.linalg.norm(before)), float(np.linalg.norm(after)), places=9)
        self.assertNotEqual(png(walk.render_pose(self.project, "walk-34")), png(walk.render_pose(self.project, "walk-34", baseline=True)))

    def test_wrist_roll_preserves_chain_and_changes_source_fingers(self):
        before, _ = walk._resolve(self.project, "walk-34")
        self.project["poses"][34]["controls"]["right_wrist"] = 45
        after, _ = walk._resolve(self.project, "walk-34")
        for name in ("upperarm_r", "lowerarm_r", "hand_r", "hand_l"):
            self.assertEqual(before["joints"][name], after["joints"][name])
        self.assertNotEqual(before["joints"]["middle_03_r"], after["joints"]["middle_03_r"])
        self.assertEqual(before["segment_lengths"], after["segment_lengths"])

    def test_foot_edit_rigidly_preserves_connected_foot_surface(self):
        renderer = walk._resources()["renderer"]
        before_state, before_bones = walk._resolve(self.project, "walk-34")
        self.project["poses"][34]["controls"]["right_foot"][0] -= 6
        after_state, after_bones = walk._resolve(self.project, "walk-34")
        before = renderer.articulated_foot(before_bones, "r")[0]
        after = renderer.articulated_foot(after_bones, "r")[0]
        self.assertFalse(np.allclose(before, after))
        for i, j in ((1, 17), (23, 135), (55, 88), (60, 150)):
            self.assertAlmostEqual(float(np.linalg.norm(before[i]-before[j])), float(np.linalg.norm(after[i]-after[j])), places=8)
        self.assertEqual(before_state["joints"]["foot_l"], after_state["joints"]["foot_l"])

    def test_hold_edits_do_not_change_geometry_or_pixels(self):
        before = walk.evaluate_pose(self.project, "walk-34")
        pixels = png(walk.render_pose(self.project, "walk-34"))
        self.project["exposures"][34]["duration_ticks"] = 6
        self.assertEqual(walk.evaluate_pose(self.project, "walk-34"), before)
        self.assertEqual(png(walk.render_pose(self.project, "walk-34")), pixels)
        self.assertEqual(self.project["poses"][34]["source_frame"], before["source_frame"])

    def test_save_reopen_and_both_facings_preserve_edited_result(self):
        self.project["poses"][34]["controls"]["left_foot"][2] += 5.25
        self.project["poses"][34]["controls"]["right_wrist"] = -25
        self.project["exposures"][34]["duration_ticks"] = 6
        reopened = json.loads(json.dumps(self.project, allow_nan=False))
        self.assertEqual(walk.evaluate_pose(self.project, "walk-34"), walk.evaluate_pose(reopened, "walk-34"))
        before = walk.render_pose(self.project, "walk-34")
        after = walk.render_pose(reopened, "walk-34")
        self.assertEqual(png(before), png(after))
        self.assertEqual(walk.render_pose(reopened, "walk-34", facing="left").tobytes(), ImageOps.mirror(before).tobytes())

    def test_baseline_provenance_sample_and_paths_are_immutable(self):
        changes = (
            lambda p: p["baseline"]["poses"][0]["controls"]["right_hand"].__setitem__(0, 0),
            lambda p: p["baseline"]["exposures"][0].update(duration_ticks=2),
            lambda p: p["baseline"]["poses"][0]["controls"].update(right_wrist=False),
            lambda p: p["baseline"].update(loop_start=9),
            lambda p: p["source"].update(kind="authored"),
            lambda p: p["source"].update(path="C:/arbitrary.py"),
            lambda p: p["source"]["hashes"].update(renderer="0"*64),
            lambda p: p["poses"][0].update(source_sample=1),
            lambda p: p["poses"][0].update(source_frame=False),
            lambda p: p["poses"][0].update(id="fake"),
            lambda p: p.update(loop_start=11),
        )
        for mutate in changes:
            candidate = copy.deepcopy(self.project)
            mutate(candidate)
            with self.assertRaises(ValueError):
                walk.validate_project(candidate)

    def test_missing_or_changed_source_fails_closed_before_code_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            bad_renderer = Path(temporary)/"render_proof.py"
            bad_renderer.write_text("raise RuntimeError('must never execute')", encoding="utf-8")
            paths = {**walk._PATHS, "renderer": bad_renderer}
            with patch.object(walk, "_PATHS", paths):
                status = walk.availability()
                self.assertFalse(status["available"])
                self.assertIn("hash mismatch", status["error"])
                with self.assertRaises(ValueError):
                    walk.default_project()
            bad_renderer.unlink()
            with patch.object(walk, "_PATHS", paths):
                self.assertFalse(walk.availability()["available"])
        self.assertTrue(walk.availability()["available"])

    def test_source_hashes_remain_pinned_after_edits_and_exports(self):
        self.project["poses"][34]["controls"]["right_hand"][0] -= 5
        walk.render_pose(self.project, "walk-34")
        for name, path in walk._PATHS.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), walk._HASHES[name])


if __name__ == "__main__":
    unittest.main()
