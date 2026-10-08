# Other workflow — offline planning and sprite handoff

This fork adds a bounded adapter to Agent Sprite Forge. It prepares and checks a project brief, then packages **existing PNG poses** into a reviewable handoff. It does not generate artwork, spend provider credits, approve a pose or import into Unreal. The existing MIT license and upstream tools remain intact.

## Commands

Run from this checkout with Python 3.10+ and Pillow. All reference paths in a brief are relative to the supplied project workspace; CLI output paths must stay inside that workspace. These examples use a placeholder character brief. Supply the real current brief, an explicitly requested deliverable and its treatment.

```powershell
python tools/other_pipeline.py plan --workspace D:/YourGame --character-brief Documentation/ExampleFighter.md --study-id EXAMPLE-STANCE-001 --character "Example Fighter" --deliverable stance-sheet --treatment mannequin --action-kind nonattack --out D:/YourGame/outputs/stance-v001/brief.json
python tools/other_pipeline.py reference --workspace D:/YourGame --path art/identity.png --role identity
python tools/other_pipeline.py check --workspace D:/YourGame --brief D:/YourGame/outputs/stance-v001/brief.json
python tools/other_pipeline.py handoff --workspace D:/YourGame --brief D:/YourGame/outputs/stance-v001/brief.json --output-dir D:/YourGame/outputs/stance-review-v001
```

`plan` creates a **draft**, with missing information explicit; it refuses to overwrite an existing file. It snapshots the supplied character brief plus AGENTS.md, ArtStyleGuide.md, CharacterSheetGuide.md, DesignTemplates.md, FightingAnimationBible.md and AnimationPipelineSpecification.md from the workspace's established Documentation layout. Missing or changed authorities require reconciliation with current direction. Hashes detect changed inputs; they do not interpret the guide or certify compliance.

`reference` prints a file hash and role for insertion into the brief. Its default status is proposed. Use `--status accepted --decision "existing decision and scope"` only to record a real prior acceptance. A configured credential or a successful generation never supplies that acceptance.

`check` checks structure, references and prerequisites. An untimed/incomplete planning brief may be valid with warnings; this is not generation readiness or visual acceptance. `handoff` requires real PNGs, explicit canvas/anchor/facing, purpose, identity/rendering references and the relevant gates. Add `--require-reference-ready` only when checking recorded positive-reference readiness; it requires per-pose checks, pixel hashes and an explicit user decision. The tool cannot perform anatomical or visual judgment.

## Complete a brief

Resolve purpose, treatment and status independently. If the requested sheet type is unclear from context, ask the user and wait before dependent generation/revision. This adapter has no automatic type selection, action batch or pose count. Supported types match the project's sheet vocabulary; `--help` lists them.

Each pose needs a stable ID, workspace-relative PNG, phase, explicit `from` pose or null, notes, and review results. Example fragment (the image and review are placeholders, not accepted artwork):

```json
{
  "purpose": "Compare how the ready stance enters a first step",
  "canvas": {"width": 1536, "height": 1024, "anchor": [768, 950], "facing": "right"},
  "poses": [{
    "id": "P01", "image": "art/poses/ready.png", "phase": "ready", "from": null,
    "notes": "Record support foot, pelvis path, hand surface and intended change",
    "review": {"anatomy": "unverified", "hands": "unverified", "identity": "unverified", "rendering": "deferred"}
  }],
  "exposure_rate": 60,
  "exposures": [{"pose_id": "P01", "duration_ticks": 3}],
  "loop_policy": "oneshot",
  "usage": "diagnostic",
  "user_acceptance": {"status": "unreviewed", "decision": ""}
}
```

- Preserve full, character-appropriate anatomy and intentional deformation. **NO SQUASH** means no layout-driven compression; it does not prohibit deliberate mutation or impose adult ratios on a character with an explicit child brief. Add pages instead of compressing bodies. Common pixel dimensions alone cannot prove this rule.
- Mannequin limb colors follow anatomical sides: right arm orange, left arm blue, right leg magenta, left leg teal. Use R/L labels and separate support-foot notes. Construction treatment does not adopt a new finished style.
- Record review results as `pass`, `fail` or `unverified`; rendering may be `deferred` for a construction study. Failed/unverified work can be handed off diagnostically, but not promoted to a positive stance/anatomy reference. For accepted/ready poses, `sha256` binds the review to the actual PNG bytes.
- References have `path`, `sha256`, `role`, `status` and `decision`. Roles identify what may be inherited. Rejected/diagnostic inputs must not serve as the positive identity or rendering authority.
- `action_kind: attack` requires both `stances.idle` and `stances.crouch` records with accepted status, current file hashes and decision text—even for a key-pose sheet. One accepted identity still cannot substitute. Earlier nonattack stance/transition studies can remain provisional.
- A move concept proof includes `move_card` fields: input, purpose, action, properties, startup, active, recovery, on_hit, on_block, context and recovery_destination. Each is `{ "value": "TBD", "status": "TBD" }` or recorded content with Approved/Proposed/Measured status. Approved/Measured fields require `evidence` text. The export makes this card visible alongside the art.
- Exposures use positive integer visual ticks at **60 Hz**. Unequal holds are preserved. They supply no gameplay startup, active window, hitstop, cancel or collision data. Source-video FPS is a separate record. No exposure schedule means an untimed study.
- Use an explicit `loop_policy` of `oneshot` or `cycle` when exporting a Forge selection. Null leaves loop intent unresolved and omits that derivative. No reverse/ping-pong recovery or forced return to idle is inferred.

## Outputs and upstream connection

`handoff` writes a new directory atomically, preserving existing outputs:

| File | Purpose |
|---|---|
| `review.html` | Escaped, static pose review with visible move card, review statuses, constraints and timing information. Not a motion proof. |
| `frames/pose-0001.png`, … | Unchanged source PNG bytes; no cropping, resizing, recoloring or keying. |
| `manifest.json` | `other-animation.v1`: source brief, hashes, common canvas/anchor and authoritative **visual** integer ticks with exact rational durations. Not the game's runtime schema. |
| `exposure.csv` | Editable exposure inspection table with cumulative tick boundaries. |
| `forge-selection.json` | Optional upstream `forge-frame-selection/v2` compatibility derivative, bound to exported image hashes. |

The selection records source indices, exact ticks and compatibility millisecond durations rounded from cumulative tick edges, with no inferred gameplay events. The Other manifest remains authoritative for authored visual ticks: upstream engine export validates tick types but constructs its base timeline from millisecond durations and does not establish the project's gameplay timing.

Optional PNG transport can use the existing exporter **after appropriate visual review**. Pass the explicit selection, declared canvas/root through `--source-size` and `--source-anchor`, `--formats png`, `--max-side` equal to the larger source dimension, no `--crop-union`, and `--art-source existing`. Native-alpha PNGs need `--key none`; default magenta detection can misclassify the mannequin's magenta limb as key residue. Do not apply chroma keying to a gray concept sheet as if it were a transparent runtime asset. Retain both manifests and inspect the PNG atlas, dimensions, anchor and timing against the source handoff. Upstream `verify` requires an encoded transport (WebM or packed video); it cannot verify a PNG-only package. This adapter does not invoke downstream packaging or claim that export check automatically.

## Defaults deliberately bypassed

Upstream `sprite_set.py run` is useful for a general video-first workflow, but its defaults include multiple actions, generated retakes, a 700 ms attack with inferred hit placement, action-specific canvases and master-frame pinning. Its agent acceptance is not the user's creative acceptance. Do not use that orchestration as this project's wrapper.

Likewise, authored PNGs bypass automatic registration locks and finishing normalization. Default packaging can downscale to 384 px; finishing can crop or shrink overflow and adjust rest-pose area. These utilities remain available for explicit experiments, not silent repairs to proportions, camera or timing.

The offline adapter imports no provider route and makes no account calls. This fork has not installed or rewritten any global skills. The upstream provider skills retain their own generic defaults, including their credential-consent language; those defaults do not authorize jobs for this project. Future provider integration needs explicit task scope, current project references and the same review boundaries.

## Tests and current limits

```powershell
python -m unittest discover -s tests -p test_other_pipeline.py
python -m unittest discover -s tests -p test_other_handoff.py
python -m pytest -q tests/test_other_pipeline.py tests/test_other_handoff.py tests/test_retime.py tests/test_engine_export_v3.py
```

The last command uses upstream test dependencies from requirements-dev.txt. Tests use synthetic images and briefs. They exercise conditional stance/move-card gates, exact tick holds, reference freshness, canvas consistency, unchanged pixels, HTML text/labels, real Forge selection loading, path/junction containment and refusal to overwrite outputs. They cannot prove anatomy, attractive animation, AI controllability or Unreal behavior. A generic original-character importer, full source-motion proof and actual character art validation remain separate work.
