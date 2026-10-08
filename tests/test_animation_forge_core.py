"""Synthetic authoring-contract tests; no game assets or providers are loaded."""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import random
import sys
import unittest

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import animation_forge_core as core


def png(image):
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class AuthoringContractTests(unittest.TestCase):
    def setUp(self):
        self.project = core.default_project()

    def test_known_good_example_is_exact_default(self):
        example = json.loads((ROOT / "examples/animation-forge/neutral-reach.forge.json").read_text(encoding="utf-8"))
        self.assertEqual(example, self.project)
        self.assertIsNone(core.validate_project(example))

    def test_default_and_baseline_are_independent_values(self):
        self.project["poses"][0]["controls"]["right_hand"][0] += 3
        self.assertNotEqual(self.project["poses"], self.project["baseline"]["poses"])
        self.assertEqual(core.default_project()["poses"], self.project["baseline"]["poses"])

    def test_json_reopen_preserves_geometry_and_png(self):
        self.project["poses"][2]["controls"]["right_hand"][2] -= 9.25
        self.project["exposures"][2]["duration_ticks"] = 31
        reopened = json.loads(json.dumps(self.project, allow_nan=False))
        self.assertEqual(core.evaluate_pose(self.project, "reach"), core.evaluate_pose(reopened, "reach"))
        self.assertEqual(png(core.render_pose(self.project, "reach")), png(core.render_pose(reopened, "reach")))

    def test_shuffled_seek_and_reset_are_stateless(self):
        expected = ["neutral"]*24 + ["lift"]*8 + ["reach"]*18 + ["return"]*10
        self.assertEqual([core.pose_at_tick(self.project, i) for i in range(60)], expected)
        ticks = list(range(180))
        random.Random(46).shuffle(ticks)
        for tick in ticks + [0, 32, 24, 60, 0]:
            self.assertEqual(core.pose_at_tick(self.project, tick), expected[tick % 60])
        before = core.evaluate_pose(self.project, "neutral")
        core.evaluate_pose(self.project, "reach")
        self.assertEqual(before, core.evaluate_pose(self.project, "neutral"))

    def test_oneshot_and_boundary_ticks(self):
        self.project["loop_policy"] = "oneshot"
        self.assertEqual(core.total_ticks(self.project), 60)
        for tick, wanted in ((23, "neutral"), (24, "lift"), (31, "lift"), (32, "reach"),
                             (49, "reach"), (50, "return"), (59, "return"), (60, "return"), (2**53-1, "return")):
            self.assertEqual(core.pose_at_tick(self.project, tick), wanted)
        for value in (-1, .5, True, float("nan"), 2**53):
            with self.subTest(value=value), self.assertRaises(ValueError):
                core.pose_at_tick(self.project, value)

    def test_local_hand_edit_does_not_change_other_chains_or_baseline(self):
        baseline = core.evaluate_pose(self.project, "reach")
        unedited_pose = core.evaluate_pose(self.project, "neutral")
        self.project["poses"][2]["controls"]["right_hand"][2] -= 12
        result = core.evaluate_pose(self.project, "reach")
        changed = {key for key, position in result["joints"].items() if position != baseline["joints"][key]}
        self.assertEqual(changed, {"right_elbow", "right_hand"})
        self.assertEqual(core.evaluate_pose(self.project, "neutral"), unedited_pose)
        self.assertEqual(core.evaluate_pose(self.project, "reach", baseline=True), baseline)

    def test_exposure_edit_only_changes_visual_timeline(self):
        before_pose = core.evaluate_pose(self.project, "reach")
        before_png = png(core.render_pose(self.project, "reach"))
        before_poses = copy.deepcopy(self.project["poses"])
        self.project["exposures"][0]["duration_ticks"] = 30
        self.assertEqual(core.total_ticks(self.project), 66)
        self.assertEqual(core.pose_at_tick(self.project, 25), "neutral")
        self.assertEqual(core.evaluate_pose(self.project, "reach"), before_pose)
        self.assertEqual(png(core.render_pose(self.project, "reach")), before_png)
        self.assertEqual(self.project["poses"], before_poses)
        self.assertEqual(self.project["source"]["rate"], None)
        self.assertEqual(self.project["gameplay"], {"status": "unassigned", "rate": 60})

    def test_ik_invariants_at_singular_and_unreachable_targets(self):
        controls = self.project["poses"][0]["controls"]
        for target in ([0., 18., 146.], [-180., 180., 220.], [0., 18., 200.], [40., 18., 146.]):
            controls["right_hand"] = target
            state = core.evaluate_pose(self.project, "neutral")
            self.assertAlmostEqual(state["segment_lengths"]["right_arm_upper"], 31., places=9)
            self.assertAlmostEqual(state["segment_lengths"]["right_arm_lower"], 27., places=9)
            self.assertTrue(np.isfinite(list(state["joints"].values())).all())
        controls["right_hand"] = [-180., 180., 220.]
        state = core.evaluate_pose(self.project, "neutral")
        self.assertIn("unreachable_target", [item["code"] for item in state["diagnostics"]])
        self.assertEqual(controls["right_hand"], [-180., 180., 220.])

    def test_all_keys_preserve_adult_limb_lengths_and_fixed_torso(self):
        for pose in self.project["poses"]:
            state = core.evaluate_pose(self.project, pose["id"])
            self.assertEqual(state["diagnostics"], [])
            for side in ("right", "left"):
                for limb, upper, lower in (("arm", 31., 27.), ("leg", 47., 46.)):
                    self.assertAlmostEqual(state["segment_lengths"][f"{side}_{limb}_upper"], upper, places=10)
                    self.assertAlmostEqual(state["segment_lengths"][f"{side}_{limb}_lower"], lower, places=10)
            self.assertEqual(state["joints"]["head"], [0., 0., 170.])
            self.assertEqual(state["joints"]["pelvis"], [0., 0., 98.])

    def test_ground_and_canvas_errors_are_reported_not_corrected(self):
        controls = self.project["poses"][0]["controls"]
        controls["right_foot"] = [0., 10., -10.]
        controls["right_hand"] = [0., 18., 210.]
        result = core.evaluate_pose(self.project, "neutral")
        codes = [item["code"] for item in result["diagnostics"]]
        self.assertIn("unreachable_target", codes)
        self.assertIn("foot_below_ground", codes)
        self.assertIn("outside_canvas", codes)
        self.assertEqual(controls["right_foot"][2], -10.)

    def test_transparent_export_and_facing_are_exact_and_color_preserving(self):
        right = core.render_pose(self.project, "reach")
        left = core.render_pose(self.project, "reach", facing="left")
        self.assertEqual(right.mode, "RGBA")
        self.assertEqual(right.size, (640, 640))
        self.assertEqual(right.getpixel((0, 0))[3], 0)
        self.assertEqual(right.getchannel("A").getextrema(), (0, 255))
        self.assertEqual(left.tobytes(), ImageOps.mirror(right).tobytes())
        colors = np.asarray(right)
        for side_color in core.COLORS.values():
            color = tuple(int(side_color[i:i+2], 16) for i in (1, 3, 5))+(255,)
            self.assertTrue(np.any(np.all(colors == color, axis=-1)))
        reopened = Image.open(io.BytesIO(png(right)))
        self.assertEqual(reopened.tobytes(), right.tobytes())

    def test_wrist_roll_changes_hand_pixels_but_never_joint_lengths(self):
        before = core.evaluate_pose(self.project, "reach")
        pixels = png(core.render_pose(self.project, "reach"))
        self.project["poses"][2]["controls"]["right_wrist"] += 70
        after = core.evaluate_pose(self.project, "reach")
        self.assertEqual(before["joints"], after["joints"])
        self.assertEqual(before["segment_lengths"], after["segment_lengths"])
        self.assertNotEqual(pixels, png(core.render_pose(self.project, "reach")))

    def test_bad_numeric_and_extra_scale_channels_are_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf"), True, "12", 181, -181, 10**1000):
            candidate = copy.deepcopy(self.project)
            candidate["poses"][0]["controls"]["right_hand"][0] = value
            with self.subTest(value=repr(value)[:50]), self.assertRaises(ValueError):
                core.validate_project(candidate)
        self.project["poses"][0]["controls"]["scale"] = 1.1
        with self.assertRaises(ValueError):
            core.validate_project(self.project)

    def test_invalid_references_and_baseline_mismatch_are_rejected(self):
        for pose_id in ("missing", {}, [], None):
            candidate = copy.deepcopy(self.project)
            candidate["exposures"][0]["pose_id"] = pose_id
            with self.subTest(pose_id=pose_id), self.assertRaises(ValueError):
                core.validate_project(candidate)
        self.project["baseline"]["poses"][0]["id"] = "new-id"
        self.project["baseline"]["exposures"][0]["pose_id"] = "new-id"
        with self.assertRaisesRegex(ValueError, "IDs must match"):
            core.validate_project(self.project)

    def test_invalid_counts_timing_and_source_are_rejected(self):
        for value in (0, -1, True, 2.5, 3601, "24"):
            candidate = copy.deepcopy(self.project)
            candidate["exposures"][0]["duration_ticks"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                core.validate_project(candidate)
        mutations = (
            lambda p: p.update(exposure_rate=60.0),
            lambda p: p.update(loop_policy="pingpong"),
            lambda p: p["source"].update(kind="game-reference"),
            lambda p: p["source"].update(rate=120),
            lambda p: p["gameplay"].update(status="approved"),
            lambda p: p["gameplay"].update(rate=60.0),
            lambda p: p.update(poses=[]),
            lambda p: p.update(exposures=[]),
            lambda p: p.update(exposures=[{"pose_id": "neutral", "duration_ticks": 3600}]*61),
            lambda p: p.update(exposures=[{"pose_id": "neutral", "duration_ticks": 1}]*1025),
            lambda p: p["poses"][1].update(id="neutral"),
            lambda p: p["poses"][1].update(id="../pose"),
        )
        for mutate in mutations:
            candidate = copy.deepcopy(self.project)
            mutate(candidate)
            with self.assertRaises(ValueError):
                core.validate_project(candidate)

    def test_function_calls_leave_input_unchanged(self):
        before = json.dumps(self.project, sort_keys=True)
        core.validate_project(self.project)
        core.total_ticks(self.project)
        core.pose_at_tick(self.project, 53)
        core.evaluate_pose(self.project, "lift")
        core.render_pose(self.project, "lift", baseline=True, facing="left")
        self.assertEqual(json.dumps(self.project, sort_keys=True), before)
        for bad in ("", "absent"):
            with self.assertRaises(ValueError):
                core.evaluate_pose(self.project, bad)
        with self.assertRaises(ValueError):
            core.render_pose(self.project, "neutral", facing="front")


if __name__ == "__main__":
    unittest.main()
