# 14islands design audit → POLARIS X (15 Nov 2026, 20:40–21:50 EST, Penumbra session)

POLARIS X is not affiliated with 14islands. This applies lessons from the studio's public work and writing, using our own design and code. No 14islands code, assets or branded elements are used.

**Evidence labels:**
- *Doc* = stated in a 14islands publication.
- *Obs* = observed by us in a browser (built-in browser pane, 800 × 600, 15 Nov).
- *Hyp* = our engineering inference.

## 1. What was inspected

| Source (link) | What it gave us |
|---|---|
| https://www.14islands.com/ | *Obs:* a blank page, then a staged reveal of oversized display type set on offset baselines ("Design / & / Technology"), tiny uppercase micro-labels, a single 3D object on black with soft studio light and lots of negative space. *Doc:* lists 35 projects. Names no stack. |
| https://www.14islands.com/services | *Doc:* "3D & Motion", "WebGL & 3D", "Web Accessibility", XR. No method detail. |
| https://www.14islands.com/work/blobmixer and https://blobmixer.14islands.com/ | *Doc:* WebGL, Three.js, React/Next.js, Framer Motion; blobs generated from "multiple parameters" that drive shape, material and lighting; "born … using debug panels". *Obs:* the loader is the product object itself with a % counter; one object fills about half the frame; the headline sits over the object; chrome only in the four corners; scrolling morphs the object between presets while the next preset's name peeks in from the edge; going to `/remix` keeps the same canvas and object and moves it (persistent canvas). |
| https://www.14islands.com/work/goals-studio | *Doc:* React, Next.js, WebGL, Three.js/R3F, Sanity. The case page describes no motion detail. |
| https://www.14islands.com/work/pluto | *Doc:* R3F, GLSL, WebXR, "Progressive enhancement principles"; flat screens get 2D, XR devices "magically reveal 3D scenes". |
| Journal: "Using the Jaws-effect to transition between 2D and 3D" (v3.14islands.com/blog/…) | *Doc:* a dolly zoom (move back and zoom in by the same factor, e.g. 200 ÷ 5 = 40×) makes a perspective camera read as flat; used on Pluto for 2D → 3D on hover. |
| Journal: "Using trigonometry to animate direction" | *Doc:* pointer in refs, not state; `Math.atan2`; a `closestAngle` helper to avoid the 180°/−180° flip; lerp in a rAF loop; write the transform directly. |
| Journal: "Developing a performant custom cursor" | *Doc:* rAF loop, lerp "speed" between 0 and 1 (values near 0 lag), values written as CSS variables or inline styles, loop cancelled when idle. |
| Journal: "Progressive Enhancement with WebGL and React" | *Doc:* three layers (no JS / JS / WebGL); one global canvas that persists across pages; DOM proxies tracked by the canvas; eased WebGL updates; screen size as a rough capability proxy ("may or may not be true"); prefer the native scrollbar for accessibility. |
| Journal: "The secret behind designing creative websites" | *Doc:* "design and code together, from the start"; motion concepts settled before detailed layouts. |
| Journal: "Interactive marquee with Framer Motion" | *Doc:* wheel/drag become one velocity value kept in a ref; spring-damped motion values; `useTransform` maps interaction strength to overlay intensity. |
| Awwwards: "Behind the scenes … 365: A Year of Cartier" | *Doc:* scroll-driven per-component scenes, an internal debug UI to "fine tune scroll animations", KTX2 textures to avoid upload stalls, all content in HTML with WebGL as enhancement. |
| Journal "Lab experiments #1" (https://www.14islands.com/journal/lab-experiments-1) | *Doc:* triangle-wise "chaos to a sphere" morph, infinite WebGL marquee (r3f + troika), Perlin-noise overlay that reveals the scene behind it. |

More patterns from the verified references (directive: at least five):

| Pattern | Why it works | POLARIS X use | Cost / limit |
|---|---|---|---|
| Persistent global canvas (blog, *Obs* on `/remix`) | No teardown/rebuild between states; the object carries the story | Explore canvas already stays mounted across tabs; the demo now moves the camera instead of cutting | None new |
| Dolly zoom 2D ↔ 3D (Jaws post) | The meaning of "flat" vs "spatial" becomes a motion | **Overhead becomes a true map lens; entering or leaving it is a dolly zoom** (§3, item 2) | Far plane must grow; markers must scale with the lens |
| closestAngle + lerp in rAF, refs not state (trig + cursor posts) | Smooth, interruptible direction changes, zero React renders | **Heading tape** (§3, item 3) | A rAF loop runs while Explore is open (three transforms per frame) |
| Parameter → immediate visual response (Blobmixer) | The user feels the variable | **Mast pick grows the 3D mast outline and names the extra height** (§3, item 4) | Must not imply intermediate values: only the drawing eases |
| Staged typographic reveal (14islands home *Obs*) | Hierarchy is read in order; arrival feels authored | **Stage title, coordinates, meta and instrument arrive in sequence on load and on every site change** (§3, item 5) | Reduced motion: none (global rule) |
| One object owns the frame; chrome lives at the edges (home, Blobmixer *Obs*) | Focus; premium restraint | **Glass panels, lens vignette, Focus mode** (§3, item 1) | Text contrast over bright terrain: glass alpha kept at 0.82 |
| Debug panels for motion tuning (Blobmixer, Cartier *Doc*) | Designers tune timing in the running product | Rejected for the release (no hidden UI in a judged build); motion tokens are CSS variables instead | — |
| Velocity → intensity (marquee *Doc*) | Feedback scales with effort | Considered for timeline scrubbing; not done in this pass (time) | — |
| Noise-dissolve reveal (Lab *Doc*) | Loading becomes a transition | Rejected: a fragment-shader overlay would cover terrain while the science loads; the staged reveal is enough | — |
| Scroll-hijacked smooth scroll (Lenis, r3f-scroll-rig *Doc*) | Sync DOM and WebGL | Rejected: Explore is not a scrolling page; their own post notes the accessibility cost | — |

## 2. Screenshot audit of the live app (before)
Captured 15 Nov 20:45 from the Mac tree at the time of the release check, built and served locally. Screenshots: `web/docs/screenshots/penumbra/14islands/before/`.

Ten weaknesses, ranked by visual impact (H/M/L), then cost and release risk:

| # | Weakness | Impact | Cost | Risk |
|---|---|---|---|---|
| 1 | Explore panels are opaque cards; the terrain is a strip between them | H | L | L |
| 2 | Guided-demo scene 3 ("raise the mast") is a near-black mast-eye frame: the mast being raised is hidden, so the experiment is invisible | H | L | M (demo test) |
| 3 | No sense of where the Sun and Earth are relative to the camera, except a dot that may be off-screen | H | M | L |
| 4 | Changing the mast height changes numbers but nothing in 3D except a static outline | M | L | L |
| 5 | "Overhead" is a perspective view from above, not a map: perspective distorts the plan geometry | M | M | L |
| 6 | No arrival: the demo opens on the final Approach framing with no move | M | L | M (timing tests) |
| 7 | Stage title and meta appear at once; no hierarchy in time | M | L | L |
| 8 | No way to see the terrain alone | M | L | L |
| 9 | Phone header stacks five control rows above the stage | M | M | M (shared Header.tsx) — **not done** |
| 10 | Terrain lighting is flat in the mid-ground (session A's `TerrainSurface.tsx`) | M | H | H — **not touched** (session A's file; it is working on the mid-distance artifact) |

## 3. Implemented: observation → adaptation → implementation → screenshot → test

1. **Terrain-first composition.**
   - *Obs:* one object owns the frame and the interface sits lightly on it (14islands home, Blobmixer).
   - *Adaptation:* frosted-glass instrument, temporal panel and camera rail (`backdrop-filter`); a lens vignette on the canvas only; a **Focus** mode (button on the heading tape, key F, Esc to leave) that steps every panel aside.
   - *Implementation:* `styles.css` (creative-pass block), `store/ui.ts` (`focus`), `App.tsx` (class + key handler).
   - *Screenshots:* `after/03_explore_site04.png` and `after/22_focus.png` vs `before/03_explore_site04.png`.
   - *Test:* layout specs unchanged, since panel geometry is the same. Glass alpha 0.82 keeps `--ash` text at ≥ 5.4:1 over white terrain (computed).
2. **Overhead map lens with a dolly zoom.**
   - *Doc:* the Jaws effect (Pluto).
   - *Adaptation:* Overhead now uses a 6° lens from ~39 half-extents away, with the same footprint as before, so the crop reads as a plan. CameraRig interpolates log tan(fov/2) with the same ease as the log distance, so moving in or out of Overhead is a dolly zoom.
   - *Implementation:* `three/CameraRig.tsx` (`fov`, `BASE_FOV`, `MAP_FOV`, `dollyFactor`), `three/Scene3D.tsx` (overhead framing, far plane, lens-aware screen-sized markers via `lensScale`).
   - *Screenshots:* `after/20_overhead_*.png`, `after/21_overhead_to_approach_700ms.png`.
   - *Found and fixed:* screen-sized markers grew 7× under the long lens.
3. **Heading tape.**
   - *Doc:* closestAngle, lerp, rAF and direct transforms (trig and cursor posts).
   - *Adaptation:* a top-centre instrument strip that shows the camera heading in the site's local azimuth, the bundle Sun and Earth azimuths at the current sample, and a readout. It scrolls with the camera, takes the closest equivalent angle and eases (0.18 per frame); reduced motion snaps.
   - *Implementation:* `store/heading.ts`, `components/HeadingTape.tsx`, `HeadingProbe` in `Scene3D.tsx`.
   - *Screenshots:* `after/03`, `after/20`, `after/21` (the tape follows the camera from heading 356° to 318°).
   - *Science:* the marks are bundle values; no time interpolation.
4. **Mast experiment you can see.**
   - *Obs/Doc:* a parameter answers at once in the object (Blobmixer).
   - *Adaptation:* picking a sampled mast grows the outline from the bundle mast to the picked height (650 ms, ease-out). A bracket and a label name the difference ("1.75 m (+0.75 m vs bundle mast)"). The numbers in the instrument still switch between evaluated heights only. Guided-demo scene 3 now stays in the Ridge of Record profile with the Sun-blocking rise (R3) selected, so the raised mast is seen next to the rise that blocks it.
   - *Implementation:* `GhostMast` in `Scene3D.tsx`; `components/Guide.tsx` steps 2–3.
   - *Test change (recorded):* `guided-demo.spec.ts` now expects scene 3's view to be `ridge` (was `mast`) and also asserts that the ghost-mast label names the extra height. Same strictness, plus one check.
   - *Screenshots:* `after/13_demo_scene3.png` vs `before/13_demo_scene3.png`; `after/23_mast_grow_450ms.png`.
5. **Staged reveal and motion tokens.**
   - *Obs:* the 14islands home headline arrives line by line.
   - *Adaptation:* `--ease-out-expo` and `--dur-reveal` tokens. The stage label, title (clip reveal), coordinates, meta, instrument and tape arrive in sequence. The title block is keyed by site, so it replays on every site change. The global reduced-motion rule sets all durations to 0.
   - *Implementation:* `styles.css`, `App.tsx` (key).
6. **Arrival in the guided demo.**
   - *Obs:* persistent canvas, and the object is moved rather than replaced (Blobmixer `/remix`).
   - *Adaptation:* scene 1 starts on the whole-crop Regional framing and descends to Approach over 2.6 s (`useCamera.request(view, { from, ms })`); the final state is unchanged.
   - *Rejected variant:* starting from the 80 m South-pole context, which was too heavy to fly through under software GL (a screenshot timed out).
   - *Screenshots:* none. The `25_demo_entry_*` capture was the one that timed out on that rejected variant, and the 2.6 s version was not re-captured.

## 4. Not changed
- Science values, bundles, sidecars, solver code and the DEM.
- `TerrainSurface.tsx` (session A), `Header.tsx`, `siteDefaults.ts`.

The three-workspace architecture is kept, and no dependency was added.

## Change log
| When (EST) | Change |
|---|---|
| 15 Nov 21:50 | Created. |
