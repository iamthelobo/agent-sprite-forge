"""Explicit backend choice preserves original behavior and the local walk clock."""
import unittest
from unittest import mock

from tools import animation_forge_backends as backends
from tools import animation_forge_core as original
from tools import animation_forge_walk as walk


class AnimationForgeBackendTests(unittest.TestCase):
    def test_default_remains_original_and_no_unknown_schema_falls_back(self):
        project = backends.default_project()
        self.assertEqual(project, original.default_project())
        self.assertIs(backends.backend_for(project), original)
        self.assertIsNone(backends.validate_project(project))
        for value in (None, [], {}, {"schema": "untrusted-module-name"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                backends.backend_for(value)

    def test_original_operations_delegate_arguments_and_preserve_return_values(self):
        project = backends.default_project()
        for name, args, kwargs in (("evaluate_pose", (project, "reach"), {"baseline": True}),
                                   ("render_pose", (project, "lift"), {"baseline": True, "facing": "left"}),
                                   ("total_ticks", (project,), {}),
                                   ("pose_at_tick", (project, 73), {})):
            with self.subTest(name=name), mock.patch.object(original, name, return_value="sentinel") as call:
                self.assertEqual(getattr(backends, name)(*args, **kwargs), "sentinel")
                call.assert_called_once_with(*args, **kwargs)

    @unittest.skipUnless(walk.availability()["available"], "Pinned local reference data is not bundled with this tool")
    def test_walk_dispatch_preserves_entry_once_after_visual_hold_edit(self):
        project = walk.default_project()
        self.assertIs(backends.backend_for(project), walk)
        self.assertIsNone(backends.validate_project(project))
        project["exposures"][0]["duration_ticks"] = 3
        project["exposures"][10]["duration_ticks"] = 2
        self.assertEqual(backends.total_ticks(project), 75)
        expected = {0: "walk-00", 2: "walk-00", 3: "walk-01", 11: "walk-09",
                    12: "walk-10", 13: "walk-10", 74: "walk-71", 75: "walk-10",
                    76: "walk-10", 77: "walk-11", 138: "walk-10"}
        for tick, pose in expected.items():
            self.assertEqual(backends.pose_at_tick(project, tick), pose)
        state = backends.evaluate_pose(project, "walk-10", baseline=True)
        self.assertTrue(state["reference_only"])
        self.assertEqual(state["source_sample"], 10)
        self.assertEqual(backends.render_pose(project, "walk-10", facing="left").tobytes(),
                         walk.render_pose(project, "walk-10", facing="left").tobytes())
