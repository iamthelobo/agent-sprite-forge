# Animation Forge — milestone validation

October 8, 2026 · local Windows · existing fork branch `codex/other-animation-workflow`, starting HEAD `c025701071122a3d505aefe895dd9daaf795c2f3`. The fork was clean before work. Implementation is saved locally and remains uncommitted/unpublished. Other's pre-existing workspace changes were preserved.

## Executed checks

| Check | Result and scope |
|---|---|
| Combined Python suite: core, export, server, existing Other planner/handoff | **79 passed, 131 subtests passed**, 14.48 s, before the final two targeted regression tests were added |
| Final affected export/server suite | **16 passed, 5 subtests passed**, 10.39 s; includes both added tests and current code |
| JavaScript editor regression suite | **4 passed**, zero skipped: stale load vs newer edit, competing loads, repeated/reverse seeks/reset, independent baseline timing after loop wrap |
| JavaScript syntax | `node --check tools/animation_forge_web/app.js` passed |
| Workspace validation | `Tools/Validation/Run-Validation.ps1 -Checks Workspace` passed; evidence `D:/Other/Game/Saved/Validation/20261008T161257033Z-ef6b9c4a/summary.md` |
| Existing source preservation | V002 render/playback scripts and the two extracted motion JSON hashes still match [the source record](animation-forge-sources.md) |

The final tested inventory comprises 81 Python test cases across the combined and subsequent affected runs, plus four JavaScript tests. Subtests are reported separately, not added to the case count. The existing `.venv` supplied NumPy 2.5.3, Pillow 12.1.1 and pytest 9.1.1; no new packages were installed.

Core coverage includes known-good fixture equality, full JSON round-trip and byte-identical PNGs, sequential/shuffled/reset seek, local hand edits, exposure changes without geometry changes, fixed segment lengths at singular/unreachable targets, wrist roll, ground/canvas diagnostics, RGBA alpha, exact pixel-mirrored facing, and invalid/NaN/source-clock inputs. Save tests include fresh revisions, reopen in a new store, baseline preservation, cache reuse and failed-save cleanup without publishing a partial project.

Integration uses real `other_handoff`, `animation_review.py review/cut`, and `engine_export.py package` calls. It checks exact rational holds, selection indices, relocated packet paths, unchanged handoff PNG bytes, mirrored canvases, preserved warning details, review-status separation, overwrite refusal and failed-stage cleanup. The existing PNG transport clears invisible RGB but preserves alpha and visible RGBA exactly; the upstream PNG-only route does not support its encoded-video verifier and no such pass is claimed.

Local HTTP tests cover actual save/load requests, static UI, rejected path escapes, malformed JSON data, wrong host, wrong token and cross-origin POSTs. The server binds only loopback with exclusive Windows port ownership. A first launch collided with a pre-existing viewer at port 8766; that other viewer was preserved, Forge's own attempted helper was stopped, and the final default moved to 8794 with explicit occupied-port refusal.

## Browser evidence

Tested the actual in-app browser at `http://127.0.0.1:8794/`:

1. Opened the original four-key fixture and inspected its full mannequin silhouette.
2. Selected Reach, changed right-hand forward target **49 → 42 cm**, and visual hold **18 → 27 ticks**. The clip changed from **60 to 69 ticks**; the baseline stayed at 60.
3. Saved `Neutral-reach-original-authoring-fixture-20261008T161218-e65887.forge.json`, loaded the known-good example, then reopened the revision. Target and hold recovered exactly; before/after geometry remained distinct.
4. Exercised normal-speed playback/pause, original-timing comparison, reset, +1 tick and right/left previews. Reset then step displayed tick 1; the saved edited Reach remained tick 32 with a 27-tick hold.
5. Exported and opened the actual Forge reviewer. Its checkerboard visibly showed transparent frames, four unique drawings and 69 viewing ticks / 1.15 seconds. The displayed repeat/loop suggestions are upstream diagnostic heuristics, not acceptance.

The first numeric-field browser attempt exposed a missing immediate input response; number fields now commit valid input without waiting for blur. Rendering is cached, so sliders apply on release and playback waits for all requested images. The independent code review also found and corrected asynchronous load replacement and edited-loop/baseline timing coupling.

Retained local evidence:

- `.forge/animation-forge/evidence/editor-before-after.png`: full editor screenshot after reopening the edited revision.
- `.forge/animation-forge/exports/20261008T161502-f98f0d/`: browser-exported edited packet, before the later addition of carried diagnostic warnings.
- `.forge/animation-forge/exports/known-good-v001/`: initial preserved original fixture packet.
- `.forge/animation-forge/exports/known-good-v002/`: final original fixture packet with carried pose diagnostics; all four right-facing PNG hashes remain identical to v001.

## Reproducible original fixture

Source: [neutral-reach.forge.json](../examples/animation-forge/neutral-reach.forge.json), schema `other-animation-forge.v1`, fixed rig `adult-mannequin.v1`, renderer `ortho-cel.v1`. Project hash in the canonical export: `98f61ee05411c3b3f13ebf7817d8b72523af27be959765fe7064a31deb365d89`. Core source SHA-256: `1a90087eb3f0577328d527a117ed1cea8b6989d5941455b816035ec2692ece72`.

PNG SHA-256, using the recorded runtime and export settings:

| Pose | SHA-256 |
|---|---|
| Neutral | `abbd39689f212d0a5555d4e889325545cde419dca31dab385fdc60482c680104` |
| Lift | `d03931eb75cc2145575471583668774df4fe94f9f2879cc3c0b4fe1b8cd7545b` |
| Reach | `42c0f56db51e3fc2be60dadd8ebb8ffe92fe26167268d2519feb97c41ac49b55` |
| Return | `e5ad021728b2d1b870da6b025609813c930350456f3711aaac005a09bfa7a42d` |

To reproduce without overwriting evidence:

```powershell
.venv/Scripts/python.exe tools/animation_forge_export.py --project examples/animation-forge/neutral-reach.forge.json --output .forge/animation-forge/exports/my-new-reproduction
```

Hash equality is established in this runtime. Cross-platform/library-version pixel identity is not tested. The original example is known-good for repeatability and editor operations, not artistically approved motion.

## Visual and production limits

Inspected static neutral/reach images and browser playback. Adult silhouette, anatomical colors, fixed camera, neutral background and visible before/after editing were present. Hands are simplified, the torso does not bend, feet have no authored rotation/toe hinge, some joint silhouettes remain angular, and triangle-sort overlaps can be wrong. There is no foot locking, continuous contact pass, corrective skinning, independent left-facing performance, final character identity, or user art acceptance. Numerical fixed-length checks do not prove anatomy or good motion.

No imported motion adapter, training run, paid generation, bulk download, Unreal/gameplay import, build/parity, editor/package smoke, multiplayer test or publication occurred. Source clip timing, authored visual holds and gameplay timing remain separate; the tool does not resolve the game's existing artwork/collision coupling. The accepted V002 walk and its documented pelvis reset/contact limits remain unchanged.

## Follow-up — preserved walk inside Forge, October 8

Added the **Reference walk** toolbar link and `/reference-walk` viewer at the user's request. The loopback server reads only eight allowlisted existing V001/V002 review files; the source proof is not copied into this repository or rewritten. Missing reference data returns an explicit unavailable result. This adds playback access, not source-motion pose editing, retargeting or export through the authoring schema.

Server suite: **8 passed, 3 subtests passed**, including the new reference-file allowlist, unchanged served bytes, traversal refusal and missing-reference behavior. Browser checks loaded all three actual atlases, paused, reset, stepped to tick 1, scrubbed to 71 and verified the next tick wrapped to **10**, compared source joints, toggled joint overlays, switched to mirrored left and back, and resumed playback. The original 10-tick entry / 62-tick repeating range remains intact. Screenshot: `.forge/animation-forge/evidence/reference-walk.png`. The viewer was left playing for the user.

## Follow-up — editable walk in the main editor, October 8

The viewer-only follow-up above did not satisfy the requested authoring workflow. The main editor now defaults to **Walk · 72 editable poses** when its pinned local source files are available. The original Reach fixture remains selectable. `other-animation-forge.walk.v1` preserves the exact baseline and source provenance, supports sample-local hand/foot targets and wrist roll, visual holds, save/reopen, mirrored preview and export. Source files are never rewritten or bundled into the portable tool. Entry exposures 0–9 play once, then 10–71 repeat; hold changes recompute the visual boundary without changing source sampling.

Executed final focused checks:

- Core/server: **26 passed, 26 subtests passed**. Walk save/reopen, pose-local image changes, hold-only cache reuse and bootstrap discovery are covered.
- Walk backend: **12 passed**. All 72 original RGBA frames equal preserved V002 atlas pixels; two samples independently rerender identically. Fixed source limb lengths, rigid hand/foot descendants, wrist edits, pinned baseline/provenance, safe source-code hash rejection, mirroring and retimed entry/loop are covered.
- Dispatch/export: **14 passed, 10 subtests passed**. Actual 72-pose PNG export, immutable pixels/provenance, camera anchors and exact entry/tail selections are covered.
- Browser-handler tests: **7 passed**, including retimed entry/loop, independent baseline timing, immediate name saving, stale load protection and concurrent request recovery after a local server restart.
- Workspace and Assets: **passed** in `D:/Other/Game/Saved/Validation/20261008T170643907Z-38ce5bfd/summary.md`. Unreal builds, parity and smoke were not selected for this local-tool-only change.

Real-browser evidence: main editor auto-loaded and played Walk; selected sample 34, changed right-hand X to 25 cm and its hold to 6 ticks, saved, opened Reach, reopened Walk and confirmed the same edit/hold with unchanged Before artwork. Named revision `Walk-hand-edit-and-hold-study-20261008T170631-f071bb.forge.json` remains under `.forge/animation-forge/projects/`. The edited total was 77 ticks; stepping the last exposure wrapped to tick 10 and Reset returned to 0. Both facings loaded. Browser export `.forge/animation-forge/exports/20261008T170943-c353dc/` was opened and its exact entry/tail playback ran. Screenshot: `.forge/animation-forge/evidence/editable-walk.png`.

The browser check caught and fixed immediate project-name saving and concurrent token-refresh recovery after a server restart. Original source/timeline/renderer/atlas hashes still match their pinned values. The preserved approximately 2.684 cm pelvis reset, unverified contact/hand quality and triangle-sorted occlusion remain; successful local editing is not animation or production-art acceptance.
