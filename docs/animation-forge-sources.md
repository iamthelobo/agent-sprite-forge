# Animation Forge — sources and provenance

Checked October 8, 2026. This is a curated reference/test library for the local 2.5D authoring milestone within [Forge's general-purpose scope](animation-forge.md#general-purpose-scope). It is not a training corpus, permission for neural-model training, or approval of any target character, stance or move. The tool direction is authorized; individual artwork and production admission retain their own review status. Other supplies the current local examples and research context, not a restriction to one project or Louis.

## Preserve the local proof

The construction baseline is `D:/Other/Documentation/Art/AnimationProofs/night-sky-walk/v002`, with `render_proof.py`, `build_playback.py`, `index.html`, `README.md`, `validation.json` and `timing-validation.json`. V001 remains at the sibling `v001` directory. Treat both as preserved evidence; retain further experiments in new outputs.

V002 uses source component-space skeletal transforms, a connected skinned torso, connected ankle/toe foot geometry, tapered limbs and fixed projection. Its documented source is [NightSkyEngine at f26e5a17de2d2de13ce9c3f1867170e2144f4cb0](https://github.com/WistfulHopes/NightSkyEngine/tree/f26e5a17de2d2de13ce9c3f1867170e2144f4cb0):

- Animation: `Content/NightSkyEngine/CharacterAssets/Mannequins/Animations/AS_manny_fwalk.uasset`.
- Skeleton: `Content/ControlRig/Characters/Mannequins/Meshes/SK_Mannequin.uasset`.
- Timing evidence: `ST_MannyFWalk`, `DA_MannyCollision`, `ABP_Common`, `ABP_Manny`; detailed extraction/provenance is in `D:/Other/Documentation/Art/AnimationProofs/night-sky-walk/v001/README.md` and `timing-evidence.json`.
- Raw local source: `D:/Other/Game/Saved/ArtResearch/NightSkyWalk-20261008/walk-poses.json` (161 bones, 51 integer samples) and `walk-timeline.json` (72 fractional-time evaluations: 10 entry ticks and 62 repeating ticks).
- Isolated evaluator: `D:/Other/Game/Saved/ArtResearch/NightSkyWalk-20261008/Inspection/Inspection.uproject`; timing/foot evidence: sibling `TimingStudy/`. Extraction used Unreal 5.8.2, outside the active game project.

SHA-256 checked against current local files:

| File | SHA-256 |
|---|---|
| `walk-poses.json` | `f488fa3550e26c6c4cb93fcf666eee449cc5343578ff60d70ca2c6f59bf6db9a` |
| `walk-timeline.json` | `03b27ec79b3bb04b5f06fe1316fc47a43396d83088ccb893408725f2eccc7574` |
| V002 `render_proof.py` | `049234f99ca1b362063220865563ee6e6845472e46c15448d6b08bb01abf02fe` |
| V002 `build_playback.py` | `7cc3fdceeec4aef3583f6d3f1f75e63a4080659d8657f1b0f08e1b1cfefbe565` |
| V002 `timed-mannequin-atlas.png` | `ed3098c19a1af17378308b9aa9cd4bb894c57cee664a7ea93ff33cb2f86c76b2` |

The two data hashes match V002's recorded validation. Its source loop retains a measured ~2.684 cm pelvis reset. The static sole correction produced no penetration at the 72 tested samples; continuous contact, foot locking/sliding, hands and surface intersections remain unproven. Triangle depth sorting and a pixel-mirrored left facing are preview limitations. Source graph reconstruction is not a measured match to the running Night Sky game. No smoothing or pose correction is implied by this record.

NightSkyEngine's code license does not establish redistribution rights for these animation/skeleton assets. They and their motion derivatives remain local, reference-only material with uncleared per-asset release rights. Do not copy them into the portable original reach example or distribute them as original motion. This documentation adds no source motion, meshes or third-party rig package to the Forge repository.

### Editable local Walk project

The subsequent user correction requests the preserved walk in the main editor, with pose edits, exposure changes and save/reopen. A separate reference-player link did not satisfy that request. This authorizes a local editing adapter over the existing evidence; it does not change the source's identity, license status or appearance approval.

The preserved timing has a one-time entry at samples **0–9**, then repeats samples **10–71**. The 62 loop samples were evaluated by Unreal at source frames `10 + 40*j/62`, for `j=0…61`. They are not generated inbetweens or a simple interpolation between two endpoint poses. Source sample/time records, local authored edits and editable 60 Hz visual holds must remain distinct. A hold edit changes the display duration of a complete sample; it does not resample the original clip or set combat timing. The known reset discontinuity remains visible unless a later explicitly authored change is recorded.

Rechecked during this adapter work: the two source files and two scripts still match their previously recorded hashes; the timed atlas hash was also recorded above. The existing proof uses a 640×640 canvas, 2.7 px/cm and the fixed projection `x=320+2.7*(0.954*X-0.300*Y-10)`, `y=567-2.7*Z`. These differ from the original reach fixture's camera. Preserving those settings is necessary for an honest zero-edit comparison. Historical V002 validation remains evidence about V002; it does not establish correctness of the new editable adapter, its modified poses or its exports.

The adapter's project schema is `other-animation-forge.walk.v1`. It records `walk-00`…`walk-71`, immutable source-sample indices/fractional frames, baseline controls/exposures and `loop_start: 10` as an exposure index. Editable hand/foot targets are absolute component-space centimeters; wrist roll is relative to the source hand orientation. The source descriptor carries the NightSkyEngine pin, source/renderer/atlas hashes, `reference-only-not-cleared` rights and the source-graph timing limitation. Walk saves require those pinned local dependencies. Zero-edit images use the preserved atlas; edited images use the preserved renderer with local pose changes. Neither route makes the source choreography original or clears it for distribution.

Retain local walk saves and rendered derivatives under the ignored Forge data directory. Preserve the original transforms, rest construction and timing evidence in their existing locations. Portable original fixtures stay separate; a walk project remains a source-derived local study even after a hand or hold is edited. See [the authoring guide](animation-forge.md) for current controls, local dependencies and implemented delivery behavior.

The adapter's focused validation now confirms all 72 unchanged RGBA samples equal the preserved atlas, sampled independent renderer reproduction, isolated edits, fixed limb lengths, save/reopen and entry/tail timing. Export validation checks an actual 72-pose packet against the source backend and preserves reference-only provenance without copying raw source arrays or the renderer into it. These are reproducibility and transport results; the source's license, loop seam and unresolved anatomy/contact limits above are unchanged. Full results belong in [the milestone validation record](animation-forge-validation.md).

## Six reference groups

### 1. 100STYLE — small editable locomotion tests

The [author's dataset page](https://www.ianxmason.com/100style/) specifies unedited 60 fps BVH, a 28-bone hierarchy and 100 locomotion styles. Its table confirms the exact candidates `Neutral_FW.bvh`, `Neutral_ID.bvh` and `Neutral_TR1.bvh`; these are forward walk, idle and transition. Start with one file only when a BVH adapter has a concrete test. The hierarchy ends at the wrists, so articulated fingers need separate authored controls.

The page lists [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) and requests appropriate creative/commercial credit, for example **The 100STYLE Dataset - Ian Mason**. Preserve attribution, source link and modification notes with any admitted derivative. `Frame_Cuts.csv` is offered for removing leading/trailing setup and T-poses; its contents and the selected BVH bytes were not downloaded or inspected here. Confirm actual channel order, units, frame time and applicable file-level notices before import. Proposed tests: unit/axis conversion, frame seeking and exact timing preservation.

### 2. CMU Motion Capture — later attack stress test

The [CMU homepage](https://mocap.cs.cmu.edu/) permits inclusion in commercial products but prohibits selling the motion data itself, including converted data. Preserve that distinction even though the page also describes the collection as free for all uses. Its [FAQ](https://mocap.cs.cmu.edu/faqs.php) and [format information](https://mocap.cs.cmu.edu/info.php) describe ASF/AMC skeleton/motion data and C3D marker data; the site links external format conversions.

[Subject 135](https://mocap.cs.cmu.edu/search.php?subjectnumber=135) lists trial **4, Front Kick**, at **120 Hz**, with AMC and C3D links. This is a later proposed retargeting/contact test, not an Other move or current fixture. Capture frequency does not set gameplay timing. No selected file or converted BVH was downloaded; converter-specific terms, units, skeleton and quality remain unchecked. The handoff cautions that fingers/thumbs were not captured and hands/toes can be noisy; individual-file evidence for those limitations was not established in this pass. Do not treat these clips as proof of usable fingers or reliable contact.

### 3. MakeHuman / MPFB — body construction reference

The [character-generator FAQ](https://static.makehumancommunity.org/mpfb/faq/build_other_chargen.html) explicitly allows reuse of core base mesh, targets and system assets. The [license page](https://static.makehumancommunity.org/about/license.html) distinguishes **CC0 core assets**, **GPL MPFB source code** and **AGPL MakeHuman source code**. Asset permission does not permit silently relicensing their software or imply that every community asset is CC0.

Proposed use: inspect adult proportions, joint topology and parameterized shape targets for an original mannequin. No asset package or software source was downloaded or incorporated in this pass; exact file terms and any implementation reuse remain unverified.

### 4. Blender Studio Rain / Snow — control and corrective references

[Rain v3](https://studio.blender.org/characters/rain/v3/) and [Snow v2](https://studio.blender.org/characters/snow/v2/) describe limb IK/FK switching/snapping, parent controls and layered face controls with shape-key correctives. Both link **CC BY 4.0**. Their requested page credits are **Rain Rig (CC) Blender Foundation | studio.blender.org** and **Snow Rig © Blender Foundation | studio.blender.org**, respectively. They are references for control organization, hand posing and deformation correction, not Other's appearance. Their stretchy controls do not override this milestone's NO SQUASH rule.

Existing local evidence is in `D:/Other/Documentation/Research/AnimationModelLibrary.md` and `Evidence/AnimationModelManifest-20261006.json`. It records Rain page v3 / archive `Rain v3.3` / `rain_v3.2.blend`, but **Snow v4 / `snow_v4.2.blend`**, not the supplied Snow v2. Exact retained files are:

- `D:/Other/Tools/Local/AnimationReferences/2026-10-06/Rain-v3/Rain v3.3/rain_v3.2.blend`
- `D:/Other/Tools/Local/AnimationReferences/2026-10-06/Snow-v4/Snow/snow_v4.2.blend`

Those earlier records cover inventory and limited static previews, not tested snapping or motion/export behavior. No fresh download or Blender execution occurred here. Keep downloaded `.blend` scripts disabled unless separately inspected and deliberately authorized. A future one-joint corrective study can reuse the existing evidence without collecting another rig.

### 5. ASW Academy — fighting-specific modeling and rigging craft

The official [ASW Academy](https://www.arcsystemworks.jp/academy/) index includes bone placement, modeling for skinning, normal editing and toon-outline lessons. Proposed use: diagnose a wrist/elbow shape or contour failure, then implement and compare an original solution. The educational index is not an open motion-data license or an ML-training grant. Videos and downloadable handouts were not newly ingested in this pass. Existing project studies remain indexed in `D:/Other/Documentation/Research/AnimationSourceAtlas.md` and `AnimationResearchTooling.md`.

**Later October 8 acquisition, explicitly requested by the user:** a small local handout pack now lives at `D:/Other/Tools/Local/AnimationReferences/ASW-20261008/`, with three official PDFs (Skinning, Bone Placement, English Toon Lines) and a manifest. The already-retained Rigging Basics PDF is reused by reference. See `D:/Other/Documentation/Research/ASWAnimationForgeBaseline.md` for exact files, hashes, inspected pages and recommendations. This later acquisition does not change the earlier pass's recorded scope or bundle these handouts in the tool.

### 6. Cartwright / Skullgirls — animation principles

The [GDC 2014 handout](https://media.gdcvault.com/GDC2014/Presentations/Cartwright_Muriel_Animation_Bootcamp_Fluid.pdf), **Fluid and Powerful Animation within Frame Restrictions**, identifies its author as **Mariel Cartwright** (the URL spells the first name differently). This remains Other's selected primary principles reference. Relevant PDF pages (counted from 1) cover silhouettes (6), anticipation (7–8), keys (9), overshoot (13–14), unequal holds (21–22) and idle transitions (24).

Proposed test: compare one original pose sequence with even versus deliberately unequal exposure while preserving the geometry, then judge readability at playback size. The handout is educational evidence, not permission to bundle its game artwork or use it as training data. Local research authority: `D:/Other/Documentation/Research/FightingAnimationBible.md` and its craft/production-contract chapters. Those do not turn source-frame counts into approved gameplay data.

## Admission and timing rules

Keep three independent records: immutable source samples/rational source time, editable authored poses and integer visual holds at 60 Hz, and gameplay timing (outside this tool milestone). Editing a hold must not mutate source geometry; a source clip at 60 or 120 Hz must not silently populate combat events. Existing Other `CharacterFrame` artwork/collision coupling still matters if assets are later integrated.

For any later admitted reference, record the exact URL/version, retrieval date, source hash, file license/credit, role, transformations and review limits. Preserve source bytes and keep authored tracks/portable project data separate. An external reference can inform a test without being bundled. References do not approve a target character's anatomy, stances or mechanics.

The current neutral adult fixture's construction treatment comes from `D:/Other/Documentation/ArtStyleGuide.md`, `CharacterSheetGuide.md` and `.agents/skills/other-art-review/SKILL.md`: anatomical right arm orange, left arm blue, right leg magenta, left leg teal; fixed proportions; NO SQUASH; flat `#E6E6E6` review background. These describe the current fixture/renderer and Other's art requirements, not universal creative rules or configurable options for every Forge project. Transparent PNG exports have alpha rather than a baked review background. Preserve unfinished hands/contact/rendering as explicit limitations. See [the existing Other handoff contract](other-workflow.md) for the transport reused by the current exporter: immutable PNGs, review status and exact exposure timing.

Verification in this pass: primary page text and local provenance/validation records, plus hashes of the four proof inputs above. The web reader returned errors for CMU and Blender Studio; direct read-only HTTP returned their primary pages successfully. No new dataset/rig downloads, paid-provider calls, model training, active Unreal edits or publication occurred. Page-level license checks do not establish the contents or notices of an uninspected download. This document records sources and proposed tests; it does not report new animation-quality or runtime passes.
