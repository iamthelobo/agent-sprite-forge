"""Offline Other brief gates: art decisions are distinct from technical validity.

Every fixture is synthetic and temporary. No provider, real character art, or
working project file is needed to exercise these production-contract boundaries.
Run with ``python -m unittest discover -s tests -p test_other_pipeline.py``.
"""
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
from unittest.mock import patch

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("other_pipeline_under_test", TOOLS / "other_pipeline.py")
PIPELINE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PIPELINE
SPEC.loader.exec_module(PIPELINE)

GUIDES = (
    "AGENTS.md",
    "Documentation/ArtStyleGuide.md",
    "Documentation/CharacterSheetGuide.md",
    "Documentation/DesignTemplates.md",
    "Documentation/Research/FightingAnimationBible.md",
    "Documentation/Research/AnimationPipelineSpecification.md",
    "Documentation/ExampleFighter.md",
)
MOVE_FIELDS = (
    "input", "purpose", "action", "properties", "startup", "active", "recovery",
    "on_hit", "on_block", "context", "recovery_destination",
)


class OtherBriefContractTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="other-forge-test-")
        self.addCleanup(self.scratch.cleanup)
        self.workspace = Path(self.scratch.name) / "workspace"
        self.workspace.mkdir()
        for name in GUIDES:
            path = self.workspace / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# Synthetic test authority: {name}\n", encoding="utf-8")
        for name in ("identity", "rendering", "idle", "crouch", "pose"):
            path = self.workspace / "art" / f"{name}.png"
            path.parent.mkdir(exist_ok=True)
            Image.new("RGBA", (64, 64), (100, 110, 120, 255)).save(path)

    def plan(self, *, deliverable="transition-study", treatment="mannequin", action_kind="nonattack"):
        return PIPELINE.plan_brief(
            workspace=self.workspace, character_brief="Documentation/ExampleFighter.md",
            study_id="EXAMPLE-TEST-001", character="Example Fighter", deliverable=deliverable,
            treatment=treatment, action_kind=action_kind,
        )

    def reference(self, name, role=None):
        path = f"art/{name}.png"
        result = {
            "path": path,
            "sha256": hashlib.sha256((self.workspace / path).read_bytes()).hexdigest(),
            "status": "accepted",
            "decision": "Synthetic explicit acceptance for this test only.",
        }
        if role is not None:
            result["role"] = role
        return result

    def brief(self, *, deliverable="transition-study", treatment="mannequin", action_kind="nonattack"):
        brief = self.plan(deliverable=deliverable, treatment=treatment, action_kind=action_kind)
        brief.update({
            "purpose": "Study a first step without changing construction or gameplay.",
            "usage": "diagnostic",
            "references": [self.reference("identity", "identity"), self.reference("rendering", "rendering")],
            "canvas": {"width": 64, "height": 64, "anchor": [32, 60], "facing": "right"},
            "poses": [{
                "id": "P01", "image": "art/pose.png", "phase": "first step", "from": None,
                "notes": "Synthetic test pose; construction and hands not reviewed.",
                "review": {"anatomy": "unverified", "hands": "unverified", "identity": "unverified",
                           "rendering": "deferred" if treatment == "mannequin" else "unverified"},
            }],
            "exposure_rate": 60,
            "exposures": [{"pose_id": "P01", "duration_ticks": 3}],
            "user_acceptance": {"status": "unreviewed", "decision": ""},
        })
        return brief

    def attack(self, *, deliverable="key-pose-sheet"):
        brief = self.brief(deliverable=deliverable, action_kind="attack")
        brief["stances"] = {"idle": self.reference("idle"), "crouch": self.reference("crouch")}
        prototype = brief["poses"][0]
        brief["poses"] = []
        for index, phase in enumerate(("origin", "load", "acceleration", "contact", "follow-through"), start=1):
            pose = copy.deepcopy(prototype)
            pose.update(id=f"P{index:02d}", phase=phase)
            pose["from"] = None if index == 1 else f"P{index - 1:02d}"
            brief["poses"].append(pose)
        brief["exposures"] = [{"pose_id": pose["id"], "duration_ticks": 3} for pose in brief["poses"]]
        if deliverable == "move-concept-proof":
            brief["move_card"] = {field: {"value": "TBD", "status": "TBD"} for field in MOVE_FIELDS}
        return brief

    def reference_ready(self, *, treatment="mannequin"):
        brief = self.brief(treatment=treatment)
        brief["usage"] = "reference-candidate"
        brief["user_acceptance"] = {"status": "accepted", "decision": "User selected this synthetic test pose."}
        brief["poses"][0]["review"] = {
            "anatomy": "pass", "hands": "pass", "identity": "pass",
            "rendering": "deferred" if treatment == "mannequin" else "pass",
        }
        brief["poses"][0]["sha256"] = hashlib.sha256((self.workspace / "art/pose.png").read_bytes()).hexdigest()
        return brief

    def check(self, brief, *, images=False, ready=False):
        result = PIPELINE.validate_brief(
            brief, self.workspace, require_images=images, require_reference_ready=ready,
        )
        self.assertIn("valid", result)
        self.assertIn("errors", result)
        self.assertIn("warnings", result)
        return result

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(TOOLS / "other_pipeline.py"), *map(str, args)],
            cwd=self.workspace.parent, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )

    def cli_plan(self, output):
        return self.cli(
            "plan", "--workspace", self.workspace, "--character-brief", "Documentation/ExampleFighter.md",
            "--study-id", "EXAMPLE-TEST-001", "--character", "Example Fighter",
            "--deliverable", "transition-study", "--treatment", "mannequin",
            "--action-kind", "nonattack", "--out", output,
        )

    def assert_valid(self, brief, **kwargs):
        result = self.check(brief, **kwargs)
        self.assertTrue(result["valid"], json.dumps(result, indent=2))
        self.assertEqual(result["errors"], [])
        return result

    def assert_invalid(self, brief, **kwargs):
        result = self.check(brief, **kwargs)
        self.assertFalse(result["valid"], json.dumps(result, indent=2))
        self.assertTrue(result["errors"], "An invalid brief must explain its refusal.")
        return result

    def test_plan_snapshots_all_authorities_without_accepting_art(self):
        brief = self.plan()
        self.assertEqual(brief["schema"], "other.sprite-brief/v1")
        snapshots = {entry["path"]: entry["sha256"] for entry in brief["authority_documents"]}
        self.assertEqual(set(snapshots), set(GUIDES))
        for path, digest in snapshots.items():
            self.assertEqual(digest, hashlib.sha256((self.workspace / path).read_bytes()).hexdigest())
        self.assertNotEqual(brief["user_acceptance"]["status"], "accepted")

    def test_missing_authority_refuses_plan(self):
        (self.workspace / "Documentation/CharacterSheetGuide.md").unlink()
        with self.assertRaises(ValueError):
            self.plan()

    def test_nonattack_mannequin_can_remain_diagnostic_and_unverified(self):
        brief = self.brief()
        before = copy.deepcopy(brief)
        self.assert_valid(brief, images=True)
        self.assertEqual(brief, before, "Validation must not auto-accept or repair the caller's document.")

    def test_attack_requires_both_accepted_stances(self):
        original = self.attack()
        self.assert_valid(original, images=True)
        for stance in ("idle", "crouch"):
            with self.subTest(stance=stance):
                brief = copy.deepcopy(original)
                brief["stances"][stance]["status"] = "proposed"
                brief["stances"][stance]["decision"] = ""
                self.assert_invalid(brief, images=True)

    def test_accepted_identity_does_not_substitute_for_stance_acceptance(self):
        brief = self.attack()
        brief["stances"] = {}
        self.assert_invalid(brief, images=True)

    def test_accepted_stance_requires_decision_evidence(self):
        brief = self.attack()
        brief["stances"]["idle"]["decision"] = ""
        self.assert_invalid(brief)

    def test_acceptance_decisions_require_nonempty_text(self):
        for value in (None, False, True, 0, [], {}, ["decision"], " \n\t"):
            for record_kind in ("stance", "reference", "user"):
                with self.subTest(value=value, record_kind=record_kind):
                    if record_kind == "stance":
                        brief = self.attack()
                        brief["stances"]["idle"]["decision"] = value
                    elif record_kind == "reference":
                        brief = self.brief()
                        brief["references"][0]["decision"] = value
                    else:
                        brief = self.reference_ready()
                        brief["user_acceptance"]["decision"] = value
                    self.assert_invalid(brief)

    def test_move_proof_allows_explicit_tbd_but_not_missing_fields(self):
        original = self.attack(deliverable="move-concept-proof")
        self.assert_valid(original, images=True)
        for field in MOVE_FIELDS:
            with self.subTest(field=field):
                brief = copy.deepcopy(original)
                del brief["move_card"][field]
                self.assert_invalid(brief)

    def test_move_proof_rejects_name_only_or_unlabelled_tuning(self):
        brief = self.attack(deliverable="move-concept-proof")
        brief["move_card"] = {"name": "Synthetic move"}
        self.assert_invalid(brief)
        brief = self.attack(deliverable="move-concept-proof")
        brief["move_card"]["startup"] = {"value": "8", "status": "finished"}
        self.assert_invalid(brief)

    def test_approved_or_measured_move_fields_require_text_evidence(self):
        for status in ("Approved", "Measured"):
            brief = self.attack(deliverable="move-concept-proof")
            brief["move_card"]["startup"] = {
                "value": "8", "status": status, "evidence": "Synthetic decision/test record.",
            }
            self.assert_valid(brief)
            for value in (None, False, True, 0, [], {}, " \n\t"):
                with self.subTest(status=status, value=value):
                    brief["move_card"]["startup"]["evidence"] = value
                    self.assert_invalid(brief)

    def test_exposures_require_positive_integer_ticks(self):
        for value in (True, False, 1.5, 0, -1, "3"):
            with self.subTest(value=value):
                brief = self.brief()
                brief["exposures"][0]["duration_ticks"] = value
                self.assert_invalid(brief)

    def test_exposure_grid_is_exactly_60_hz(self):
        for rate in (24, 30, 59.94, True, "60"):
            with self.subTest(rate=rate):
                brief = self.brief()
                brief["exposure_rate"] = rate
                self.assert_invalid(brief)

    def test_unknown_pose_cannot_receive_an_exposure(self):
        brief = self.brief()
        brief["exposures"][0]["pose_id"] = "P99"
        self.assert_invalid(brief)

    def test_duplicate_pose_ids_are_rejected(self):
        brief = self.brief()
        brief["poses"].append(copy.deepcopy(brief["poses"][0]))
        self.assert_invalid(brief)

    def test_image_path_cannot_escape_workspace(self):
        outside = self.workspace.parent / "private.png"
        Image.new("RGBA", (64, 64)).save(outside)
        for path in ("../private.png", str(outside.resolve())):
            with self.subTest(path=path):
                brief = self.brief()
                brief["poses"][0]["image"] = path
                self.assert_invalid(brief, images=True)

    def test_reference_path_cannot_escape_workspace(self):
        outside = self.workspace.parent / "private.png"
        Image.new("RGBA", (64, 64)).save(outside)
        brief = self.brief()
        brief["references"][0].update(
            path="../private.png", sha256=hashlib.sha256(outside.read_bytes()).hexdigest(),
        )
        self.assert_invalid(brief)

    def test_reference_status_must_be_recognized(self):
        for value in ("aproved", "finished", None, True):
            with self.subTest(value=value):
                brief = self.brief()
                brief["references"][0]["status"] = value
                self.assert_invalid(brief)

    def test_rejected_or_diagnostic_refs_cannot_fill_positive_reference_roles(self):
        for role_index in (0, 1):
            for status in ("rejected", "diagnostic"):
                with self.subTest(role_index=role_index, status=status):
                    brief = self.brief()
                    brief["references"][role_index]["status"] = status
                    self.assert_invalid(brief, images=True)

    def test_diagnostic_reference_is_allowed_under_its_own_role(self):
        brief = self.brief()
        diagnostic = self.reference("pose", "diagnostic")
        diagnostic.update(status="diagnostic", decision="")
        brief["references"].append(diagnostic)
        self.assert_valid(brief, images=True)

    def test_strict_image_validation_requires_common_untrimmed_canvas(self):
        brief = self.brief()
        Image.new("RGBA", (63, 64)).save(self.workspace / "art/pose.png")
        self.assert_invalid(brief, images=True)

    def test_strict_image_validation_requires_real_png(self):
        brief = self.brief()
        (self.workspace / "art/pose.png").write_text("not image data", encoding="utf-8")
        self.assert_invalid(brief, images=True)

    def test_canvas_dimensions_reject_nonpositive_and_noninteger_values(self):
        for value in (0, -1, 64.5, True, "64"):
            with self.subTest(value=value):
                brief = self.brief()
                brief["canvas"]["width"] = value
                self.assert_invalid(brief)

    def test_canvas_anchor_requires_two_finite_coordinates(self):
        for anchor in ([32, float("nan")], [float("inf"), 60], [32, float("-inf")], [True, 60], [32], "32,60"):
            with self.subTest(anchor=anchor):
                brief = self.brief()
                brief["canvas"]["anchor"] = anchor
                self.assert_invalid(brief)

    def test_reference_ready_requires_pose_checks_not_only_user_selection(self):
        original = self.reference_ready()
        self.assert_valid(original, ready=True)
        for check in ("anatomy", "hands", "identity"):
            with self.subTest(check=check):
                brief = copy.deepcopy(original)
                brief["poses"][0]["review"][check] = "unverified"
                self.assert_invalid(brief, ready=True)

    def test_reference_ready_requires_explicit_user_decision(self):
        for acceptance in ({"status": "unreviewed", "decision": ""}, {"status": "accepted", "decision": ""}):
            with self.subTest(acceptance=acceptance):
                brief = self.reference_ready()
                brief["user_acceptance"] = acceptance
                self.assert_invalid(brief, ready=True)

    def test_claimed_acceptance_cannot_pass_without_an_image(self):
        brief = self.reference_ready()
        brief["poses"][0]["image"] = None
        self.assert_invalid(brief)

    def test_accepted_pose_requires_a_hash_binding_the_reviewed_pixels(self):
        brief = self.reference_ready()
        del brief["poses"][0]["sha256"]
        self.assert_invalid(brief)

    def test_editing_an_accepted_pose_invalidates_its_review_binding(self):
        brief = self.reference_ready()
        self.assert_valid(brief)
        Image.new("RGBA", (64, 64), (0, 255, 0, 255)).save(self.workspace / "art/pose.png")
        self.assert_invalid(brief)

    def test_finished_reference_requires_rendering_pass(self):
        brief = self.reference_ready(treatment="finished-character")
        self.assert_valid(brief, ready=True)
        brief["poses"][0]["review"]["rendering"] = "deferred"
        self.assert_invalid(brief, ready=True)

    def test_edited_authority_invalidates_existing_snapshot(self):
        brief = self.brief()
        self.assert_valid(brief)
        guide = self.workspace / "Documentation/ArtStyleGuide.md"
        guide.write_text(guide.read_text(encoding="utf-8") + "New direction.\n", encoding="utf-8")
        self.assert_invalid(brief)

    def test_edited_reference_invalidates_existing_snapshot(self):
        brief = self.brief()
        Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(self.workspace / "art/identity.png")
        self.assert_invalid(brief)

    def test_offline_plan_and_validation_never_spawn_or_connect(self):
        with patch.object(subprocess, "Popen", side_effect=AssertionError("Offline adapter spawned a child")), \
                patch("socket.socket.connect", side_effect=AssertionError("Offline adapter opened a socket")), \
                patch("socket.create_connection", side_effect=AssertionError("Offline adapter connected")), \
                patch("urllib.request.urlopen", side_effect=AssertionError("Offline adapter requested a URL")):
            brief = self.brief()
            self.assert_valid(brief, images=True)

    def test_cli_plan_relative_output_is_relative_to_workspace(self):
        result = self.cli_plan("packets/brief.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.workspace / "packets/brief.json").is_file())
        self.assertFalse((self.workspace.parent / "packets/brief.json").exists())
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "draft-needs-input")
        self.assertEqual(report["provider_calls"], 0)
        self.assertFalse(report["generated_art"])

    def test_cli_plan_refuses_nested_git_metadata(self):
        for output in ("tools/fork/.git/config", "tools/fork/.GiT/brief.json"):
            with self.subTest(output=output):
                result = self.cli_plan(output)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("Git internals", json.loads(result.stderr)["error"])
                self.assertFalse((self.workspace / "tools").exists())

    def test_cli_plan_preserves_existing_output_bytes(self):
        target = self.workspace / "brief.json"
        original = b"existing user material\n"
        target.write_bytes(original)
        result = self.cli_plan("brief.json")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(target.read_bytes(), original)

    def test_cli_reference_defaults_to_proposed_and_hashes_local_file(self):
        result = self.cli("reference", "--workspace", self.workspace,
                          "--path", "art/identity.png", "--role", "identity")
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)
        self.assertEqual(record["status"], "proposed")
        self.assertEqual(record["decision"], "")
        self.assertEqual(record["role"], "identity")
        self.assertEqual(record["sha256"], hashlib.sha256((self.workspace / "art/identity.png").read_bytes()).hexdigest())

    def test_cli_accepted_reference_requires_an_explicit_decision(self):
        arguments = ("reference", "--workspace", self.workspace,
                     "--path", "art/identity.png", "--role", "identity", "--status", "accepted")
        refused = self.cli(*arguments)
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("decision", json.loads(refused.stderr)["error"])
        decision = "Synthetic existing user decision for test identity."
        accepted = self.cli(*arguments, "--decision", decision)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        record = json.loads(accepted.stdout)
        self.assertEqual(record["status"], "accepted")
        self.assertEqual(record["decision"], decision)

    def test_cli_handoff_preserves_pixels_ticks_and_diagnostic_status(self):
        brief = self.brief()
        brief["loop_policy"] = "oneshot"
        brief_path = self.workspace / "brief.json"
        brief_path.write_text(json.dumps(brief), encoding="utf-8")
        original = (self.workspace / "art/pose.png").read_bytes()
        result = self.cli("handoff", "--workspace", self.workspace, "--brief", brief_path,
                          "--output-dir", "review/packet-v001")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["validation"]["valid"])
        output = self.workspace / "review/packet-v001"
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"], "other-animation.v1")
        self.assertEqual(manifest["visual_timing"]["rate_hz"], 60)
        self.assertEqual(manifest["visual_timing"]["total_ticks"], 3)
        self.assertEqual(manifest["visual_timing"]["exposures"][0]["duration_ticks"], 3)
        self.assertEqual(manifest["brief"]["user_acceptance"]["status"], "unreviewed")
        self.assertEqual(manifest["evidence"]["visual_review"], "not-performed-by-exporter")
        self.assertFalse(manifest["gameplay_authority"])
        self.assertEqual((output / manifest["frames"][0]["file"]).read_bytes(), original)
        self.assertEqual((self.workspace / "art/pose.png").read_bytes(), original)
        selection = json.loads((output / "forge-selection.json").read_text(encoding="utf-8"))
        self.assertEqual(selection["ticks"], [3])
        self.assertEqual(selection["tickHz"], 60)
        self.assertEqual(selection["events"], [])
        self.assertIn("P01", (output / "review.html").read_text(encoding="utf-8"))
        self.assertTrue((output / "exposure.csv").is_file())


if __name__ == "__main__":
    unittest.main()
