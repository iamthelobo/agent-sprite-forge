"""Real renderer -> Other handoff -> upstream review/PNG transport integration."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import animation_forge_core as core
from tools import animation_forge_export as exporter
from tools import animation_forge_backends as backends
from tools import animation_forge_walk as walk


class AnimationForgeExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.project = core.default_project()
        a, b = (pose["id"] for pose in cls.project["poses"][:2])
        cls.project["exposures"] = [{"pose_id": a, "duration_ticks": 1},
                                    {"pose_id": b, "duration_ticks": 4},
                                    {"pose_id": a, "duration_ticks": 1}]
        cls.packet = cls.root / "packet"
        cls.original = copy.deepcopy(cls.project)
        cls.result = exporter.export_project(cls.project, cls.packet)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def read(self, path):
        return json.loads((self.packet / path).read_text(encoding="utf-8"))

    def test_immutable_pngs_exact_holds_source_and_reviews_survive_handoff(self):
        self.assertEqual(self.project, self.original)
        self.assertEqual(self.read("project.json"), self.project)
        exported = self.read("export.json")
        source = (self.packet / "project.json").read_bytes()
        self.assertEqual(exported["project"]["sha256"], hashlib.sha256(source).hexdigest())
        self.assertEqual(exported["renderer"]["id"], core.RENDERER_VERSION)
        self.assertEqual(exported["pose_diagnostics"], {
            pose["id"]: core.evaluate_pose(self.project, pose["id"])["diagnostics"]
            for pose in self.project["poses"]})
        self.assertFalse(exported["gameplay_authority"])
        self.assertEqual(exported["review"]["user_acceptance"], "unreviewed")
        handoff = self.read("handoff/manifest.json")
        self.assertEqual(handoff["brief"]["source_motion"], self.project["source"])
        self.assertEqual(handoff["brief"]["gameplay"], self.project["gameplay"])
        self.assertEqual(handoff["brief"]["user_acceptance"]["status"], "unreviewed")
        self.assertEqual(handoff["visual_timing"]["total_ticks"], 6)
        self.assertEqual(handoff["visual_timing"]["total_seconds"], {"numerator": 1, "denominator": 10})
        self.assertEqual([row["start_tick"] for row in handoff["visual_timing"]["exposures"]], [0, 1, 5])
        self.assertEqual([row["duration_ticks"] for row in handoff["visual_timing"]["exposures"]], [1, 4, 1])
        for frame, pose in zip(handoff["frames"], handoff["brief"]["poses"]):
            delivered = (self.packet / "handoff" / frame["file"]).read_bytes()
            self.assertEqual(delivered, (self.packet / frame["source"]).read_bytes())
            self.assertEqual(hashlib.sha256(delivered).hexdigest(), frame["sha256"])
            self.assertEqual(set(pose["review"].values()), {"unverified"})
        selection = self.read("handoff/forge-selection.json")
        self.assertEqual(selection["sourceIndices"], [0, 1, 0])
        self.assertEqual(selection["ticks"], [1, 4, 1])
        self.assertEqual(selection["durations_ms"], [17, 66, 17])
        self.assertEqual(selection["events"], [])
        for field in ("review", "forge_selection", "project", "manifest", "handoff_manifest", "index"):
            self.assertFalse(Path(self.result[field]).is_absolute())
            self.assertTrue((self.packet / self.result[field]).is_file())

    def test_both_facing_transparent_untrimmed_pixels(self):
        for right in sorted((self.packet / "renders/right").glob("*.png")):
            with Image.open(right) as source, Image.open(self.packet / "renders/left" / right.name) as mirror:
                self.assertEqual(source.mode, "RGBA")
                self.assertEqual(source.size, (640, 640))
                self.assertEqual(source.getchannel("A").getextrema(), (0, 255))
                self.assertTrue(source.getchannel("A").getbbox())
                self.assertEqual(ImageOps.mirror(source).tobytes(), mirror.tobytes())

    def test_repeat_export_is_byte_deterministic_and_relocatable(self):
        output = self.root / "repeat"
        exporter.export_project(self.project, output)
        first = {path.relative_to(self.packet).as_posix(): path.read_bytes()
                 for path in self.packet.rglob("*") if path.is_file()}
        second = {path.relative_to(output).as_posix(): path.read_bytes()
                  for path in output.rglob("*") if path.is_file()}
        self.assertEqual(first, second)
        for name, data in first.items():
            if name.endswith((".json", ".html")):
                self.assertNotIn(b".animation-forge-", data)
                self.assertNotIn(str(self.root).encode(), data)

    def test_actual_upstream_review_repeats_exact_bytes_and_selection_cut_works(self):
        self.assertEqual(self.result["playback_status"], "generated-needs-visual-review")
        review = self.read("playback/review.json")
        self.assertEqual(review["fps"], 60)
        self.assertEqual(review["diagnostics"]["frameCount"], 6)
        self.assertEqual(review["sourceDirectory"], "../review-ticks")
        unique = sorted((self.packet / "handoff/frames").glob("*.png"))
        sequence = [0, 1, 1, 1, 1, 0]
        for row, source_index in zip(review["frames"], sequence):
            referenced = (self.packet / "playback" / row["source"]).resolve()
            self.assertEqual(referenced.read_bytes(), unique[source_index].read_bytes())
            self.assertEqual(row["sha256"], hashlib.sha256(referenced.read_bytes()).hexdigest())
        # Same v1 payload the existing browser's Save Selection produces.
        selection = {"schema": "forge-frame-selection/v1", "sourceDirectory": "review-ticks",
                     "start": 1, "endExclusive": 5, "fps": 60,
                     "sourceHashes": [frame["sha256"] for frame in review["frames"][1:5]],
                     "status": "selected-needs-visual-review"}
        selected = self.root / "review-selection.json"
        selected.write_text(json.dumps(selection), encoding="utf-8")
        cut = self.root / "review-cut"
        completed = subprocess.run([sys.executable, str(exporter.REVIEW_SCRIPT), "cut",
                                    "--frames-dir", str(self.packet / "review-ticks"),
                                    "--out-dir", str(cut), "--selection", str(selected)],
                                   capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(list(cut.glob("*.png"))), 4)
        for path in cut.glob("*.png"):
            self.assertEqual(path.read_bytes(), unique[1].read_bytes())

    def test_real_engine_png_transport_preserves_canvas_anchor_and_colors(self):
        script = ROOT / "skills/video2dsprite/scripts/engine_export.py"
        destination = self.root / "engine-png"
        command = [sys.executable, str(script), "package", "--clean-dir", str(self.packet / "handoff/frames"),
                   "--selection", str(self.packet / "handoff/forge-selection.json"),
                   "--output-dir", str(destination), "--name", "mannequin", "--formats", "png",
                   "--key", "none", "--art-source", "existing", "--placeholder",
                   "--max-side", "640", "--source-size", "640,640", "--source-anchor", "320,584"]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        manifest = json.loads((destination / "animation.json").read_text(encoding="utf-8"))
        provenance = json.loads((destination / manifest["provenanceFile"]).read_text(encoding="utf-8"))
        self.assertEqual(provenance["params"]["sourceSize"], [640, 640])
        self.assertEqual(provenance["params"]["sourceAnchor"], [320, 584])
        self.assertFalse(provenance["params"]["cropUnion"])
        self.assertIsNone(provenance["params"]["key"])
        self.assertEqual(manifest["reviewStatus"], "needs-visual-review")
        self.assertEqual(manifest["sourceIndices"], [0, 1, 0])
        self.assertEqual(manifest["durationsMs"], [17, 66, 17])
        spec = importlib.util.spec_from_file_location("forge_export_engine_test", script)
        engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine)
        atlas = engine.atlas_frames(destination, manifest)
        source_paths = sorted((self.packet / "handoff/frames").glob("*.png"))
        for actual, index in zip(atlas, manifest["sourceIndices"]):
            with Image.open(source_paths[index]) as expected:
                self.assertEqual(actual.shape, (640, 640, 4))
                expected_pixels = np.array(expected)
                self.assertTrue(np.array_equal(actual[..., 3], expected_pixels[..., 3]))
                visible = expected_pixels[..., 3] != 0
                self.assertTrue(np.array_equal(actual[visible], expected_pixels[visible]))
                # Existing transport intentionally zeros invisible RGB; handoff PNG
                # bytes stay identical, and no alpha/visible color is changed.
                self.assertTrue(np.all(actual[~visible, :3] == 0))

    def test_existing_output_and_cli_refusal_preserve_result(self):
        before = (self.packet / "export.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "new directory"):
            exporter.export_project(self.project, self.packet)
        completed = subprocess.run([sys.executable, str(ROOT / "tools/animation_forge_export.py"),
                                    "--project", str(self.packet / "project.json"), "--output", str(self.packet)],
                                   capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("never overwritten", completed.stderr)
        self.assertEqual((self.packet / "export.json").read_bytes(), before)

    def test_render_failure_cleans_only_owned_stage(self):
        unrelated = self.root / ".animation-forge-existing"
        unrelated.mkdir()
        (unrelated / "keep.txt").write_text("preserve")
        output = self.root / "failed"
        with mock.patch.object(core, "render_pose", side_effect=ValueError("fixture render failure")):
            with self.assertRaisesRegex(ValueError, "fixture render failure"):
                exporter.export_project(self.project, output)
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.glob(".animation-forge-*")), [unrelated])
        self.assertEqual((unrelated / "keep.txt").read_text(), "preserve")

    def test_source_clip_and_bad_hold_rejected_without_export(self):
        for name, change in [("clip", {"source": {"kind": "captured", "description": "reference", "rate": 120}}),
                             ("hold", {"exposures": [{"pose_id": self.project["poses"][0]["id"], "duration_ticks": True}]})]:
            project = copy.deepcopy(self.project)
            project.update(change)
            with self.subTest(name=name), self.assertRaises(ValueError):
                exporter.export_project(project, self.root / name)
            self.assertFalse((self.root / name).exists())

    def test_core_warnings_survive_diagnostic_brief_without_pose_repair(self):
        project = copy.deepcopy(self.project)
        target_pose = project["poses"][0]
        target_pose["controls"]["right_foot"] = [0., 10., -10.]
        target_pose["controls"]["right_hand"] = [0., 18., 210.]
        original = copy.deepcopy(project)
        diagnostics = exporter._pose_diagnostics(project)
        expected = core.evaluate_pose(project, target_pose["id"])["diagnostics"]
        self.assertEqual(diagnostics[target_pose["id"]], expected)
        self.assertEqual({item["code"] for item in expected},
                         {"unreachable_target", "foot_below_ground", "outside_canvas"})
        frames = [{"file": f"renders/right/pose-{index:04d}.png", "sha256": "fixture"}
                  for index, pose in enumerate(project["poses"], 1)]
        brief = exporter._brief(project, frames, "fixture-project-hash", {}, diagnostics)
        pose = brief["poses"][0]
        self.assertEqual(pose["diagnostics"], expected)
        for warning in expected:
            self.assertIn(warning["code"], pose["notes"])
            self.assertIn(warning["message"], pose["notes"])
        self.assertEqual(set(pose["review"].values()), {"unverified"})
        self.assertEqual(brief["user_acceptance"]["status"], "unreviewed")
        self.assertEqual(project, original)


@unittest.skipUnless(walk.availability()["available"], "Pinned local reference data is not bundled with this tool")
class ReferenceWalkExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.project = walk.default_project()
        cls.project["exposures"][0]["duration_ticks"] = 3
        cls.project["exposures"][10]["duration_ticks"] = 2
        cls.packet = cls.root / "walk"
        cls.result = exporter.export_project(cls.project, cls.packet)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def read(self, path):
        return json.loads((self.packet / path).read_text(encoding="utf-8"))

    def test_reference_provenance_dynamic_camera_and_original_bytes(self):
        manifest = self.read("export.json")
        self.assertEqual(manifest["project"]["source"], self.project["source"])
        self.assertEqual(manifest["project"]["source"]["rights"], "reference-only-not-cleared")
        self.assertEqual(manifest["renderer"]["id"], walk.RENDERER_VERSION)
        self.assertEqual(manifest["renderer"]["anchor"], [293, 567])
        self.assertEqual(manifest["renderer"]["facing_anchors_pixel_centers"],
                         {"right": [293, 567], "left": [346, 567]})
        self.assertEqual(self.read("project.json"), self.project)
        brief = self.read("brief.json")
        self.assertEqual(brief["canvas"]["anchor"], [293, 567])
        self.assertIsNone(brief["source_capture_fps"])
        self.assertEqual(brief["source_motion"]["rate"], 60)
        self.assertIn("not original", brief["poses"][0]["notes"])
        self.assertEqual(brief["user_acceptance"]["status"], "unreviewed")
        self.assertEqual(manifest["renderer"]["module"], "tools/animation_forge_walk.py")
        for frame in manifest["renders"]["right"]:
            with Image.open(self.packet / frame["file"]) as exported:
                self.assertEqual(exported.tobytes(), walk.render_pose(self.project, frame["pose_id"]).tobytes())
        # Only editable target data and derived PNGs travel; original skeleton,
        # raw extracted motion and executable reference renderer do not.
        self.assertFalse(list(self.packet.rglob("walk-timeline.json")))
        self.assertFalse(list(self.packet.rglob("walk-poses.json")))
        self.assertFalse(list(self.packet.rglob("render_proof.py")))

    def test_entry_once_tail_cycle_timing_and_real_upstream_selections(self):
        manifest = self.read("export.json")
        timing = manifest["visual_timing"]
        self.assertEqual(timing["loop_start_exposure"], 10)
        self.assertEqual(timing["loop_start_tick"], 12)
        self.assertEqual(timing["total_ticks"], 75)
        self.assertEqual(timing["loop_ticks"], 63)
        self.assertTrue(timing["entry_then_loop"])
        self.assertEqual(self.result["playback"], "authored-playback.html")
        self.assertEqual(self.result["loop_selection"], "handoff/forge-loop-selection.json")
        full = self.read("handoff/forge-selection.json")
        loop = self.read("handoff/forge-loop-selection.json")
        self.assertEqual(full["loopPolicy"], "oneshot")
        self.assertEqual(loop["loopPolicy"], "cycle")
        self.assertEqual(loop["sourceIndices"], list(range(10, 72)))
        self.assertEqual(loop["ticks"], [2] + [1]*61)
        self.assertEqual(sum(loop["durations_ms"]), 1050)
        self.assertEqual(self.read("handoff/manifest.json")["brief"]["authored_visual_timing"], timing)
        script = ROOT / "skills/video2dsprite/scripts/engine_export.py"
        spec = importlib.util.spec_from_file_location("forge_walk_export_engine_test", script)
        engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine)
        paths = sorted((self.packet / "handoff/frames").glob("*.png"))
        hashes = lambda index: hashlib.sha256(paths[index].read_bytes()).hexdigest()
        for filename, policy, length in (("forge-selection.json", "oneshot", 75),
                                          ("forge-loop-selection.json", "cycle", 63)):
            loaded = engine.load_selection(self.packet / "handoff" / filename, 72, hashes, None)
            self.assertEqual(loaded["loopPolicy"], policy)
            self.assertEqual(loaded["tickHz"], 60)
            self.assertEqual(loaded["timeline"].total_ms, length*1000//60)
        # Exact player has no source filesystem or ephemeral staging dependency.
        page = (self.packet / "authored-playback.html").read_text(encoding="utf-8")
        self.assertIn("REFERENCE ONLY", page)
        self.assertIn("entry+(absolute-entry)%(length-entry)", page)
        self.assertNotIn(".animation-forge-", page)
        self.assertEqual(backends.pose_at_tick(self.project, 75), "walk-10")


if __name__ == "__main__":
    unittest.main()
