# Animation Forge — general-purpose scope and authoring guide

October 8, 2026 · existing `codex/other-animation-workflow` checkout. The main editor now supports the preserved **Walk** as a local editable motion study, alongside the original four-key **Reach** fixture. Walk loads by default when its pinned local sources are available. It supports pose edits, visual holds, save/reopen and before/after playback in the same workspace. The separate original-walk viewer remains a reference comparison. The existing planar `codeart2d` backend is unchanged.

## General-purpose scope

User direction, October 8, 2026: **Asset Forge is for general use across characters and projects.** The 2.5D Animation Forge editor is its reusable pose, visual-timing, preview and export workflow. Louis is one potential consumer; his identity, stance, moveset and production schedule do not define the tool. The existing sprite, media and map workflows retain their own documented capabilities.

Other's Louis-first, 2D-playable-prototype-first sequence governs that game's character milestone. It does not gate parallel Forge development, 2.5D authoring experiments or neutral examples. Character briefs and project art direction apply to work for those characters/projects. Keep shared tool requirements separate from project adapters, sample content and asset acceptance.

General use is the intended scope, not a claim of arbitrary rig, style or engine support today. The current adult mannequins, anatomical colors, fixed cameras, unsquashed geometry and 60 Hz visual holds are implemented study/renderer constraints. They are not universal art requirements for every future Forge asset, nor newly configurable settings. Use each workflow's documented limits and the target project's brief when planning new content or extensions.

The [Other workflow](other-workflow.md) is a project-specific adapter. The current authoring exporter reuses its PNG/timing transport; identifiers such as `other-animation-forge.v1`, `other-animation.v1` and `other_handoff` remain real compatibility names. That implementation dependency does not require a Louis brief or impose Other's roster, art direction or Unreal integration on all Forge uses. Other projects keep their own asset requirements and acceptance decisions.

## Open and use

Double-click `Animation Forge.cmd` in the repository, or run:

```powershell
& ./Start-AnimationForge.ps1
```

Open **http://127.0.0.1:8794/**. The launcher uses the existing `.venv` with NumPy and Pillow, starts a hidden loopback-only server, and reuses that server on subsequent launches. It refuses another application's port; use `-Port` to select a different one. No Node build, account or provider service is required. On another installation, supply Python 3.10+ with NumPy and Pillow and run `python tools/animation_forge.py`; requirements-dev.txt supplies the additional upstream test dependencies. Automatic package installation is not part of launching.

Use the **Animation** selector and **Load animation** to switch between **Walk · 72 editable poses** and **Reach · four authored poses**. If Walk's local evidence is missing or fails its integrity checks, the editor reports its unavailability and still offers Reach. A downloaded walk project requires the same pinned local source files; it does not contain a portable replacement for them.

1. Pause Walk, then choose a sample in **Pose**, on the visual timeline, or by scrubbing. Choose a hand or foot target.
2. Edit X (forward), Y (depth), Z (height) or the wrist angle. Each edit affects only that selected sample. Limb lengths stay fixed; unreachable targets report their actual clamping. Sliders apply on release; numeric targets update while entering valid values. Engaging pose controls pauses playback.
3. Change **Hold this exposure**, an integer number of visual ticks at 60 Hz. Geometry and source metadata do not change.
4. Use Play/Pause, reset, single-tick steps, scrub, speed and facing. **Before: Same pose** isolates a geometry change; **Original timing** compares baseline and edited exposure schedules on a shared absolute preview clock. Walk plays entry samples 0–9 once, then repeats samples 10–71. Each comparison follows its own holds and loop boundary. The selected end policy applies to both schedules; Reset returns to the entry.
5. **Save revision** creates a new local file. Choose it under Saved revisions and **Reopen revision**. Download/Import JSON carries controls, holds, baseline and provenance. Reach is portable; Walk remains a local source-dependent study. Undo/redo preserves the previous project when loading another animation or revision. A late load/import response cannot replace edits made while it was pending.
6. **Export PNG handoff** writes a new immutable packet. Open its review link for existing Forge playback/scrub, the static pose review, editable project and provenance.

All preview images are loaded before playback is enabled. Seek and reset select complete states from integer visual ticks, with no accumulated skeletal simulation or newly synthesized inbetweens. Playback speed is a viewing control, not a project edit. Baseline comparison and left/right preview are view settings; saved project data preserves the animation rather than browser panel state.

**Original walk viewer ↗** opens `http://127.0.0.1:8794/reference-walk`, the preserved V001/V002 comparison with source-joint overlays. That viewer does not show current Forge edits. Its `--reference-walk <path>` server option selects the preserved viewer directory; it does not repoint the editable backend's pinned source dependencies.

## Editable data and renderer

| Study | Source and editable data | Timing |
|---|---|---|
| Walk | `other-animation-forge.walk.v1`; 72 locally reconstructed source samples, IDs `walk-00`…`walk-71`; four absolute component-space hand/foot targets in cm plus wrist roll relative to source orientation | Initially one 60 Hz visual tick per sample; `loop_start: 10` is an exposure index. Holds before it set entry duration; remaining holds set loop duration. Source indices/fractional times stay unchanged. |
| Reach | `other-animation-forge.v1`; [neutral-reach.forge.json](../examples/animation-forge/neutral-reach.forge.json), equal to the authored core's `default_project()` | Neutral/Lift/Reach/Return hold **24/8/18/10 ticks**; a 60-tick loop with no entry. Original authoring fixture, not an approved stance. |

Walk resolves edits against each source sample's roots, limb lengths and bend direction. Hand/finger and foot descendants follow the affected endpoint as rigid groups; wrist roll is relative to the original hand orientation. Unedited states reuse the preserved V002 atlas pixels. Edited states use the pinned V002 renderer and fixed construction. Its source-driven torso and articulated feet remain animated; those source motions are not independent torso/toe authoring controls.

Reach uses the original fixed analytic two-bone IK, static connected torso and fixed foot envelope. Both studies render 640×640 straight-alpha RGBA, anatomical orange/blue/magenta/teal limbs, a fixed camera and a `#E6E6E6` review background. Walk preserves V002's 2.7 px/cm projection and ground line at y567; Reach uses 3 px/cm and y584. Exports retain the chosen backend's declared camera/canvas/anchor. No automatic fitting, source smoothing, animated scaling or squash is applied.

The schema-dispatch facade keeps the two backends distinct. Walk's `source` record identifies `reference-only`, `night-sky-walk-v002`, rate 60, the NightSkyEngine pin, `reference-only-not-cleared` rights and hashes for timeline, integer poses, renderer and atlas. Its baseline sample controls/exposures and loop-start index are checked against the pinned source. Authored edits and holds stay in the local project; original source files remain untouched. This is one adapter for an existing local reference, not a general BVH/retargeting importer. Both studies leave gameplay unassigned. [Sources and provenance](animation-forge-sources.md) records exact paths, hashes and all six reference groups.

## Local files and export

Default data directory: `.forge/animation-forge/` within the checkout (ignored by Git). The current local installation is `D:/Other/Tools/Local/AgentSpriteForge`.

| Directory | Contents |
|---|---|
| `projects/` | New, atomically published `.forge.json` revisions; existing saves are never overwritten |
| `cache/` | Content-addressed PNGs, including renderer-code identity; visual hold changes reuse the same images |
| `exports/<revision>/` | New diagnostic packets; authoring source, both facings, exact handoff and existing Forge review |
| `server.log`, `server-error.log`, `server.pid` | Local helper diagnostics |

Export uses the real `other_handoff.export_handoff`, preserving unique source PNG bytes, integer 60 Hz holds, rational timing and hash-bound `forge-frame-selection/v2`. `export.json.visual_timing` records the authored loop policy, exposure-index loop start, cumulative loop-start tick and total duration. Changing an entry hold updates that cumulative boundary without moving the source loop sample.

| Export file | Walk timing behavior |
|---|---|
| `authored-playback.html` | Exact authored entry-once, then repeating-tail playback at 60 Hz; use this to review the complete sequence |
| `handoff/forge-selection.json` | One-shot full first pass; the upstream selection format cannot encode entry plus a separate repeating range |
| `handoff/forge-loop-selection.json` | Cycle-only tail, starting at the authored loop exposure; carries exact ticks and cumulative rounded compatibility milliseconds |
| `playback/index.html` | Existing `animation_review.py` interval reviewer; repeats its selected interval and is not the entry/loop authority |

The existing interval reviewer receives a separate byte-identical, tick-expanded viewing derivative. Above 600 total visual ticks that legacy derivative is explicitly omitted; the exact handoff and authored playback remain available. The project/export timing records and integer ticks are authoritative; rounded milliseconds serve upstream compatibility. The separate loop selection applies to an entry-plus-loop project; a hold-last study remains one-shot.

Both-facing PNGs are delivered, with left facing an exact pixel mirror. Walk's pixel-center anchor is `(293,567)` facing right and `(346,567)` after mirroring. Optional downstream `engine_export.py` PNG packaging must use `--key none`, the selected facing's declared 640×640 canvas and anchor, `--max-side 640`, and no crop. Do not substitute Reach's anchor for Walk's. The earlier Reach transport check preserved alpha and visible RGBA while the existing exporter cleared RGB beneath fully transparent pixels; it is not a walk-export test. Immutable source/handoff PNGs remain separate. Neither route imports into Unreal or supplies gameplay events. See [the existing Other handoff](other-workflow.md).

Walk packets contain the editable project, rendered PNGs and provenance; they do not copy the original source arrays, skeleton or rig into the tool. A static exported packet can play its PNGs without those source files, but reopening for edits still requires the pinned local dependencies. The packet remains a reference-only derivative and is not cleared for distribution.

## Scope, authority and review

Milestone behavior: change one limb target and one visual hold, save/reopen without loss, deterministically preview before/after and export transparent frames. The user's October 8 correction makes the preserved Walk an editable study in the main tool. The local backends, facade, server, export bridge and UI implement that scope; no active Unreal/combat code is changed. Test results belong to the specific version and study in the validation record.

The current Walk and Reach studies were developed using the Other art-review skill and ArtStyleGuide v1.19, CharacterSheetGuide, FightingAnimationBible, craft guide and proposed AnimationPipelineSpecification. Their brief: adult construction mannequin; preserve full limb proportions and anatomical orange/blue/magenta/teal colors, fixed camera/scale and **NO SQUASH**; use neutral review background and transparent delivery. These record the studies' construction and review provenance; Other's guides govern Other assets, not all Forge projects. V002 supplies the local Walk's construction and source motion, not permission to redistribute it. STYLE-B-01 supplied graphic clarity context for these studies; finished character identity, costume, face and finish are deferred. Walk and Reach are nonattack studies; neither proposes a character move or gameplay frame card.

Current limits: sample-local endpoint/wrist edits, no edit interpolation across neighboring samples, no independent torso/finger/toe authoring controls, no foot locks/contact solver or surface-intersection corrections, triangle depth sorting rather than a z-buffer, and mirrored rather than independently authored left-facing motion. Walk retains its source-driven torso and feet, its simplified/unverified hand surfaces and the measured ~2.684 cm pelvis reset. Reach retains its static torso/head and fixed foot construction. Editing one walk sample can create a visible discontinuity; holds cannot repair pose continuity or contact. No general BVH import/retargeter, model training, finished character production asset or gameplay integration is implemented. Diagnostic warnings are not acceptance, and numeric tests do not establish aesthetic quality.

The original Reach fixture remains checked in as text. Walk's game-derived evidence remains in its existing local locations; edits, renders and exports stay under ignored `.forge`. V001/V002 and their source data remain unchanged. Walk saves/exports are local reference derivatives, not cleared production/distribution assets. Paid provider calls: **0**; new generation-service charges: **0**. Codex usage is not estimated here. No remote push, publication, account change or active Unreal mutation occurred.

## Reproduce checks

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_animation_forge_core.py tests/test_animation_forge_walk.py tests/test_animation_forge_backends.py tests/test_animation_forge_export.py tests/test_animation_forge_server.py tests/test_other_pipeline.py tests/test_other_handoff.py
node --test tests/js/animation-forge-editor.test.cjs
node --check tools/animation_forge_web/app.js
```

Confirmed for the editable Walk update: **12 backend tests passed**; all 72 unchanged RGBA samples match the preserved timed atlas. The facade/export suite passed **14 tests plus 10 subtests**, including an actual 72-pose packet and separate full-pass/tail selections after hold edits. The server suite passed **10 tests plus 3 subtests**, and the editor suite passed **7 tests**. These results cover the named suites, not every upstream tool.

The actual browser loaded and played Walk, edited sample 34 to right-hand X **25 cm** and a **6-tick** hold, then saved/reopened those values. The resulting 77-tick first pass wrapped **76 → 10** and Reset returned to **0**. Before remained unchanged while After showed the edited arm. Workspace and asset validation also passed. See [the milestone validation record](animation-forge-validation.md) for retained evidence and detailed scope; earlier Reach/viewer checks remain separate. Unreal builds, combat parity, editor/package smoke and runtime art quality are outside this local tool change and have not been reported as passes.
