"""Offline handoff contracts; deterministic fixtures are not character art."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from fractions import Fraction

from PIL import Image

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "other_handoff.py"
SPEC = importlib.util.spec_from_file_location("other_handoff", MODULE_PATH)
handoff = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handoff)


class OtherHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "workspace"
        self.root.mkdir()
        Image.new("RGBA", (13, 29), (12, 87, 200, 123)).save(self.root / "pose.png")
        self.brief = {
            "schema": "other.sprite-brief/v1", "character": "Fixture", "study_id": "TEST-001",
            "revision": "v001", "deliverable": "transition-study", "treatment": "mannequin",
            "action_kind": "nonattack", "purpose": "Test export", "usage": "diagnostic",
            "references": [{"role": "identity", "path": "private/brief.md", "status": "proposed", "decision": "TBD"}],
            "stances": {}, "canvas": {"width": 13, "height": 29, "anchor": [6, 28], "facing": "right"},
            "poses": [{"id": "P01", "image": "pose.png", "phase": "origin", "from": None,
                       "notes": "Fixture", "review": {"anatomy": "unverified", "hands": "unverified"}},
                      {"id": "P02", "image": "pose.png", "phase": "step", "from": "P01",
                       "notes": "Fixture", "review": {"anatomy": "unverified", "hands": "unverified"}}],
            "exposure_rate": 60, "exposures": [{"pose_id": "P01", "duration_ticks": 1},
                                               {"pose_id": "P02", "duration_ticks": 4}],
            "move_card": None, "user_acceptance": {"status": "unreviewed", "decision": "TBD"},
            "constraints": ["NO SQUASH", "Keep <hands> unverified & poses diagnostic"],
        }

    def export(self, brief=None, name="packet"):
        return handoff.export_handoff(brief or self.brief, self.root, self.root / name)

    def test_unchanged_images_hashes_and_exact_unequal_holds(self):
        original = (self.root / "pose.png").read_bytes()
        result = self.export()
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["brief"], self.brief)
        for frame in manifest["frames"]:
            self.assertEqual((Path(result["output_dir"]) / frame["file"]).read_bytes(), original)
            self.assertEqual(frame["sha256"], hashlib.sha256(original).hexdigest())
        timing = manifest["visual_timing"]
        self.assertEqual(timing["total_seconds"], {"numerator": 1, "denominator": 12})
        self.assertEqual([row["start_tick"] for row in timing["exposures"]], [0, 1])
        self.assertEqual([row["duration_ticks"] for row in timing["exposures"]], [1, 4])
        self.assertEqual(timing["exposures"][1]["start_seconds"], {"numerator": 1, "denominator": 60})
        self.assertFalse(manifest["gameplay_authority"])
        self.assertIn("1/60", Path(result["exposure_csv"]).read_text(encoding="utf-8"))
        self.assertFalse((Path(result["output_dir"]) / "private").exists())

    def test_visible_complete_move_card_and_escaped_text(self):
        brief = copy.deepcopy(self.brief)
        hostile = "<script>alert('bad')</script> & \"quoted\""
        brief["character"] = hostile
        brief["poses"][0]["notes"] = hostile
        brief["poses"][0]["id"] = "../../unsafe<script>"
        brief["exposures"][0]["pose_id"] = brief["poses"][0]["id"]
        brief["move_card"] = {key: {"value": hostile if key == "input" else "TBD", "status": "TBD"}
                              for key in handoff.CARD_LABELS}
        result = self.export(brief)
        markup = Path(result["review"]).read_text(encoding="utf-8")
        self.assertNotIn("<script>", markup)
        self.assertIn("&lt;script&gt;", markup)
        for label in handoff.CARD_LABELS.values():
            self.assertIn(f"<th>{label}</th>", markup)
        self.assertIn("Static review packet", markup)
        self.assertIn("<li>NO SQUASH</li>", markup)
        self.assertIn("Keep &lt;hands&gt; unverified &amp; poses diagnostic", markup)
        self.assertTrue((Path(result["output_dir"]) / "frames/pose-0001.png").is_file())

    def test_bridge_requires_explicit_timing_and_loop_policy(self):
        result = self.export()
        self.assertIsNone(result["forge_selection"])
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["upstream_bridge"]["status"], "omitted")
        brief = copy.deepcopy(self.brief)
        brief.update(loop_policy="oneshot", exposures=[])
        untimed = self.export(brief, "untimed")
        self.assertIsNone(untimed["forge_selection"])
        for policy in ("pingpong", "once", "loop", ""):
            brief["loop_policy"] = policy
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                self.export(brief, "invalid")

    def test_bridge_loads_in_actual_upstream_exporter(self):
        engine_path = MODULE_PATH.parents[1] / "skills/video2dsprite/scripts/engine_export.py"
        spec = importlib.util.spec_from_file_location("other_handoff_upstream_engine", engine_path)
        engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine)
        for policy in ("oneshot", "cycle"):
            brief = copy.deepcopy(self.brief)
            brief["loop_policy"] = policy
            brief["exposures"].append({"pose_id": "P01", "duration_ticks": 1})
            result = self.export(brief, policy)
            selection_path = Path(result["forge_selection"])
            selection = json.loads(selection_path.read_text(encoding="utf-8"))
            self.assertEqual(selection["sourceIndices"], [0, 1, 0])
            self.assertEqual(selection["ticks"], [1, 4, 1])
            self.assertEqual(selection["durations_ms"], [17, 66, 17])
            self.assertEqual(selection["tickHz"], 60)
            self.assertEqual(selection["sourceDirectory"], "frames")
            self.assertEqual(selection["events"], [])
            def actual_frame_hash(index):
                frame_path = Path(result["output_dir"]) / f"frames/pose-{index + 1:04d}.png"
                return hashlib.sha256(frame_path.read_bytes()).hexdigest()
            loaded = engine.load_selection(selection_path, 2, actual_frame_hash, None)
            self.assertEqual(loaded["loopPolicy"], policy)
            self.assertEqual(loaded["tickHz"], 60)
            self.assertEqual(loaded["timeline"].total_ms, Fraction(100))
            self.assertIsNone(loaded["impactMs"])
            self.assertIsNone(loaded["holdMs"])
            self.assertEqual(loaded["summary"]["status"], "selected-needs-visual-review")

    def test_untimed_diagnostic_packet_does_not_invent_timing(self):
        brief = copy.deepcopy(self.brief)
        brief["exposures"] = []
        result = self.export(brief)
        self.assertEqual(result["timing_status"], "untimed")
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        self.assertIsNone(manifest["visual_timing"]["total_seconds"])
        self.assertIn("Untimed study", Path(result["review"]).read_text(encoding="utf-8"))

    def test_output_escape_and_overwrite_preserve_files(self):
        outside = self.root.parent / "outside"
        with self.assertRaises(ValueError):
            handoff.export_handoff(self.brief, self.root, outside)
        self.assertFalse(outside.exists())
        output = self.root / "packet"
        output.mkdir()
        (output / "keep.txt").write_text("preserve", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual((output / "keep.txt").read_text(), "preserve")

    def test_source_escape_rejected(self):
        brief = copy.deepcopy(self.brief)
        brief["poses"][0]["image"] = "../outside.png"
        with self.assertRaises(ValueError):
            self.export(brief)
        self.assertFalse((self.root / "packet").exists())

    def test_protected_output_destinations_rejected(self):
        for destination in (self.root, self.root / "BrazBrue/packet", self.root / "Game/packet",
                            self.root / ".git/packet", self.root / "nested/.git/packet"):
            with self.subTest(destination=destination):
                with self.assertRaises(ValueError):
                    handoff.export_handoff(self.brief, self.root, destination)

    def test_render_failure_cleans_only_created_staging_directory(self):
        brief = copy.deepcopy(self.brief)
        brief["move_card"] = {"input": {"value": "TBD", "status": "TBD"}}
        unrelated = self.root / ".other-handoff-existing"
        unrelated.mkdir()
        (unrelated / "keep.txt").write_text("preserve", encoding="utf-8")
        with self.assertRaises(KeyError):
            self.export(brief)
        self.assertFalse((self.root / "packet").exists())
        self.assertEqual(list(self.root.glob(".other-handoff-*")), [unrelated])
        self.assertEqual((unrelated / "keep.txt").read_text(), "preserve")

    def test_symlink_parent_escape_rejected(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        link = self.root / "escape"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            try:
                import _winapi
                _winapi.CreateJunction(str(outside), str(link))
            except (ImportError, AttributeError, OSError):
                self.skipTest("Directory symlinks and junctions unavailable on this host")
        with self.assertRaises(ValueError):
            handoff.export_handoff(self.brief, self.root, link / "packet")
        self.assertFalse((outside / "packet").exists())
        (outside / "pose.png").write_bytes((self.root / "pose.png").read_bytes())
        brief = copy.deepcopy(self.brief)
        brief["poses"][0]["image"] = "escape/pose.png"
        with self.assertRaises(ValueError):
            self.export(brief)

    def test_invalid_holds_leave_no_output(self):
        for bad in (0, -1, 0.5, True):
            with self.subTest(hold=bad):
                brief = copy.deepcopy(self.brief)
                brief["exposures"][0]["duration_ticks"] = bad
                with self.assertRaises(ValueError):
                    self.export(brief)
                self.assertFalse((self.root / "packet").exists())


if __name__ == "__main__":
    unittest.main()
