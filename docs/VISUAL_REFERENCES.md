# Visual references for Simple mode (S1 study, 16 Nov 2026)

Each site was opened with the Playwright MCP at 1440 × 900 and captured three or four times (loading, first view,
mid-scroll or mid-interaction, one click or hover). The captures are in `tmp/s1/refs/` (git-ignored: they show other
people's work and branding, so they are not committed). This note is about craft only. Nothing here is copied: no code,
models, textures, branding or layouts.

Our stack, for the "how it fits" lines: React + TypeScript, three.js with react-three-fiber (moving to `WebGPURenderer`
and TSL node materials in section R, with the WebGL2 backend as fallback), Zustand, one `styles.css` with every Simple
rule scoped under `.simple`. No new npm packages.

Fixed rule for everything below: light on the lunar terrain stays physically true. White sunlight, hard shadows, black
sky. No god rays, haze, fog or caustics on terrain. Cinematic effects (chromatic aberration, rays) are allowed in the
opening sequence only.

## What was and was not seen

| Reference | Address opened | Seen |
| --- | --- | --- |
| Planpoint (Anderson Mancini), WebGPU | planpoint-webgpu.vercel.app | First view, unit-search mode, hover label, click card. The loading sequence was not captured: the scene was already interactive 0.7 s after navigation. |
| Mancini's Three.js ArchiViz house | planpoint-house.vercel.app (found through the three.js forum) | Loader, first view, hotspots after a click |
| igloo.inc | www.igloo.inc | Loader, first view, mid-scroll, a project panel |
| oryzo.ai (Lusion) | oryzo.ai | Loader, first view, mid-scroll |
| Ivress brand site | brand.ivress.co.jp | Loader at two points, the "click to start" gate, first story line |
| Primland Residences | ownprimland.com | Loader, hero, aerial map (a privacy banner covers the lower left in every capture) |
| Cartier Watches & Wonders 2024 (Immersive Garden) | cartier-waw-dev-0224.dev.60fps.fr, linked as "Launch website" from immersive-g.com | Loader, curtain, curtain parting on scroll, first scene with a hotspot |
| makemepulse | www.makemepulse.com | Studio home page and one case-study transition. "enno's Light" and "Pulztronic" were not opened; they still need a look in S3. |

## 1. Planpoint WebGPU — the primary reference for how Simple mode works

What it does: one building owns the frame, with five small round icon buttons at the bottom centre and a compass in
the corner. Nothing else is on screen. In unit-search mode the clickable units tint, a small dark label follows the
pointer ("UNIT 4NE / Tap to see details"), and a click docks a card on the right while the scene stays live beside it.
The card has a title, a status badge, facts, one primary button and two secondary ones, and a round close button. The
bottom bar collapses to "home" while the card is open.

Adapt:
- The interaction grammar for S12: hover shows a one-line label at the pointer; click flies the camera and opens one
  card; the rest of the interface steps back while the card is open; one obvious way back.
- The interface weight: controls are small and sit on the edge; the scene is never boxed in.
- A label that says what a click will do before you click.
- The card as a real panel with a hierarchy (title, state, facts, one primary action), not a tooltip that grew.

How it fits: hover and click come from R3F pointer events on the clickable meshes (site and mast, ridges, Sun and
Earth discs); the label is a DOM element moved with `transform` on `pointermove`; the fly-to reuses `CameraRig`
(1.2 s, instant under reduced motion); the card is the `.simple .s-objcard` component from S1. Every clickable object
also gets a real button in an off-canvas list so the keyboard path exists (S12).

Reject:
- Tinting clickable objects in saturated green and orange. On our terrain a colour wash would read as data. Hover
  uses a thin outline and the label only.
- The white card and the pill-shaped buttons. Ours is dark glass with a 2 px radius.
- Chromatic aberration, depth-of-field blur and the warm sunset grade on the scene. Their scene is a mood piece; ours
  is a measurement display, and fringing on a skyline would look like a data artefact.
- The on-screen FPS and parameters panel (a developer tool; our quality tier is one line in About this view).
- The photo carousel inside the card.

## 2. Mancini's Three.js ArchiViz house

What it does: a plain ring loader on black, then a house in daylight. A click reveals white hotspot dots on the
facade, one per room; the list of rooms also exists as plain text in the page.

Adapt: hotspots that sit on the object and are also listed as text. That pairing is exactly the S12 accessibility
plan (each scene object has a matching button).
How it fits: our pins are DOM elements projected from scene coordinates (drei `Html` or a projected overlay), styled
by `.simple .s-pin`.
Reject: the bare spinner on a blank page (the plan asks for loading that is part of the experience), bare white dots
with no label until clicked, and the flat sky-dome lighting.

## 3. igloo.inc

What it does: a tiny text-character loader, then one object (an igloo on a snow ridge) with small monospaced
annotations pinned to it and joined by thin lines. Corner text is tiny and fixed. A "Sound: Off" control sits bottom
left as plain text with an icon. Scrolling moves the camera through the scene; a project opens as a text panel over a
dimmed scene, with the text decoding into place.

Adapt:
- One hero object, annotations pinned to it, hairline leader lines. This is the closest reference for labelled ridges
  and sight lines.
- The sound control as quiet text plus icon in a corner. Ours is the same idea, disabled, with the tooltip "Sound
  coming later".
- Monospace used for what is measured or indexed, which is how we already use JetBrains Mono (numbers, IDs, hashes).
- A loader that is small, typographic and specific.

How it fits: annotations are DOM labels over the canvas with SVG leader lines; the terrain is already a single hero
object in `Scene3D`.
Reject: the fog and soft bloom that give their snow its depth (no atmosphere on the Moon); scroll-driven camera as the
main navigation (ours is click-driven, Planpoint style); the scrambled-text reveal on paragraphs (it delays reading a
number, and our numbers must be readable at once); body text at about 10 px.

## 4. oryzo.ai (Lusion)

What it does: the loader draws the product's outline as a vector construction (anchor points, dashed guides) on a
flat colour; the outline then becomes the real object. The first view is a physically lit product on a cutting mat
with a huge wordmark; scrolling cuts to the object alone on near-black with one short line of text on each side.

Adapt:
- A loader that draws the thing you are about to see. For S3 that is the Moon's limb and the Sun's point of light,
  not a generic bar.
- Material honesty: the cork reads as cork because of roughness and fine grain. For regolith that means a matte,
  lunar-Lambert surface with fine normal detail, labelled VISUAL where it is synthetic.
- The restraint of the dark section: one object, a sentence left, a sentence right, generous empty space.

How it fits: the outline loader is an SVG or a small canvas drawn while bundles load; the dark, low-chrome section
matches our base `#050505` and the type tokens.
Reject: the joke product framing and oversized all-caps wordmark; warm studio lighting (sunlight on the Moon is
white); a small frosted panel used as decoration over the photo. Our glass is used only where a panel has to sit on
live terrain.

## 5. Ivress brand site

What it does: a black loader with a small character and a percentage, a "click to start" gate, then a nearly black
scene lit by one doorway of light, with a tall condensed serif wordmark, a sound control and a language switch at the
top right. The story advances line by line.

Adapt:
- Darkness as the default state and light as the event. That is our subject: the south pole is mostly black, and what
  matters is where light arrives.
- The loader shows real progress as a number.
- Very few words on screen at once.

How it fits: our base colour and the true-light scene already work this way. A progress number is allowed only when
real progress is known (S11), for example bundles fetched out of bundles requested.
Reject: the visible light shaft and dust in the air (volumetric light needs an atmosphere); the mandatory click gate
(our intro must never delay a visitor once data is ready, and is skippable by any key); the long linear story; the
ultra-condensed display face (Instrument Serif stays).

## 6. Primland Residences

What it does: a flat green loader with the mark, a slow aerial hero in haze, then a top-down illustrated map of the
estate that you explore, with a thin white top bar.

Adapt: the map as the navigation. You look down at real ground and pick a place. That is S4's landing view: the south
pole with the ROI sites as pins, pick one and fly in.
How it fits: `GlobalMoon` with pins projected from the bundle coordinates, each pin a `.simple .s-pin` whose shimmer
strength is the spread across the 20 terrain variants from the certainty sidecar.
Reject: aerial haze and golden light (no atmosphere, white sunlight); the white top bar (ours is `#262623`); a consent
banner covering the scene. We set no tracking cookies, so we need no banner.

## 7. Cartier Watches & Wonders 2024 (Immersive Garden)

What it does: a ring of dots as the loader, a full-screen curtain with the title, and the curtain parts as you
scroll. Each scene has one hero object, a title and a line of serif text, one "Discover" button, a ring-shaped
hotspot on the object, and "Overview" and "Sound" as small words in the bottom corners.

Adapt:
- The reveal as one authored moment. For S3 that is the Sun's light arriving across the limb, once.
- The ring hotspot: an open circle on the object reads as "this can be opened" without covering it. Our pin is a
  small solid dot with a ring around it, and the ring carries meaning (variant spread).
- The corners as the home for quiet utilities ("Overview", "Sound").
- One serif line and one button per scene.

How it fits: the reveal belongs to S3's single full-screen canvas; the corner utilities map to the Simple top bar and
footer in S2.
Reject: reflective water and the pastel sky (caustics and atmosphere are both ruled out); scroll as the only way
forward; thin all-caps display type at low contrast, which would fail our contrast checks over terrain.

## 8. makemepulse

What it does (studio site only): large, light, lower-case type with a lot of air, and a case-study image that grows
to fill the screen when clicked, so the page change reads as one continuous movement.

Adapt: transitions that carry an object from one state to the next instead of cutting. For us: the pin you click on
the globe is the point the camera flies into (S4 to S6), and the card opens from the object's side of the screen.
How it fits: `CameraRig` targets plus a card entrance that starts from the anchor side (`transform-origin` set from
the object's screen position).
Reject: the cookie panel, the white editorial page style, and anything about their brand type.
Not studied in S1: enno's Light and Pulztronic. See the S3 re-check at the end of this note.

## What S1 took from this study

| Decision in the design system | From |
| --- | --- |
| One-line hover label at the pointer, saying what a click does | Planpoint |
| Object card as a full glass panel with title, state, facts, one primary action and a Back control | Planpoint |
| Pin = small solid dot plus a ring; the ring's motion or width encodes variant spread | Cartier (ring hotspot), Primland (map pins) |
| "Sound: off" as quiet text plus icon | igloo, Cartier, Ivress |
| Monospace only for numbers, IDs and measurements | igloo |
| Few words, serif for titles, large exact numerals | oryzo, Cartier |
| Dark base, light as the event | Ivress |

Rejected across the board, with the reason: atmosphere effects on terrain (not physical on the Moon), colour washes
over terrain (would read as data), scroll-driven navigation (Sid chose click-to-explore), consent banners (nothing to
consent to), pill and large-radius shapes (our radius is 2 px), and decorative glass (ours is only for panels over
live terrain).

## S3 re-check: how the references load and hand over (17 Nov 2026)

Opened again with the Playwright MCP at 1440 × 900, this time for the loading sequence only: captures at about 0.5 s,
1.8 s, 4.5 s and 9 s after navigation, in `tmp/s3/refs/` (git-ignored, as before). Craft only; nothing copied.

| Reference | What its loading does | Seen this time |
| --- | --- | --- |
| igloo.inc | A flat field and one small row of glyphs in the centre that changes as files arrive. Nothing else on screen. | Loader at four points; it was still loading at 4.5 s |
| oryzo.ai (Lusion) | The loader is the first drawing of the product: a small construction mark grows into the object's outline, so the loaded scene continues from the loader instead of replacing it. | Loader at two points, first view |
| Ivress brand site | Black screen, one small mark, a serif percentage that counts real progress (it read 07 % at 4.5 s on this connection). | Loader, "click to start" gate |
| Cartier Watches & Wonders 2024 | Wordmark inside three dotted rings on a flat field, then a curtain. | Loader, curtain |
| Planpoint WebGPU, ArchiViz house | No sequence to speak of: the scene was interactive before the first capture could be taken. | First view only |
| makemepulse, "Benno's Light" (the plan's "enno's Light") | Case-study page only: a monochrome, hard-lit 3D scene with one light direction and long shadows; the experience itself is not linked from the page. | Case-study page, three captures |
| makemepulse, "Pulztronic" | Not found: the case-studies page listed eight projects and none by that name. | Nothing |

What S3 adapts, and how it fits our stack:

- **The loader is the first frame of the scene (oryzo).** Our sequence is drawn in the globe's own canvas with the
  globe's own camera (`simple/Globe.tsx`, phase `intro`), so its last frame is the S4 view. There is no second canvas, no
  curtain and no cross-fade at the hand-off (reduced motion aside, where a cross-fade is the whole transition).
- **One small, exact progress mark; real numbers (igloo, Ivress).** One hairline along the bottom edge and a monospace
  percentage. The figure comes from the loaders: the bundle read, the certainty sidecar read, and the Moon model's own
  byte-progress events (`introMath.loadFraction`). It stops when loading stops.
- **Dark base, light as the event (Ivress, Benno's Light).** The screen is black until the bundle's Sun comes out from
  behind the Moon's dark limb; that is the one bright thing in the frame. One light direction, hard edge.
- **Waiting is a held picture, not a spinner.** While the Moon model downloads, the camera holds on the Sun at the limb
  and creeps, so a slow connection sees a composed frame; a fast one moves on after 0.9 s.
- **Hand-off as one camera move (makemepulse's carried transitions, S1 note).** The camera swings from the night side
  to the south-pole view and pushes in; the interface comes in over the last third of that move, so it reads as one
  gesture.

Rejected, with the reason:

- A "click to start" gate (Ivress): the plan says the sequence never delays a visitor once the data is ready.
- Curtains, wipes and brand cards (Cartier): a cut between two pictures; ours has to be one picture.
- A full-screen white-out as the reveal: the plan caps any white-out at about 80 % with a ramp of at least 1 s. Our lens
  effects never lift a pixel above 80 % of display white and ramp over 1.2 s (`introMath.INTRO`, unit-tested).
- Warm or amber sunlight (the plan's first draft said "point of amber light"): the light truth table says sunlight on the
  Moon is white, and amber stays an interface accent. The Sun, its glare and the lit crescent are white.
- Tone washes and smoke (Benno's Light): atmosphere, which the Moon does not have.

Where the cinematic effects stop: the wide glare, the streak, the ghost ring and the colour fringing exist only while the
Sun is in frame during the sequence (`uIntro` in `simple/SimplePost.tsx`). They are at zero before the interface comes
in, and the globe and terrain views never set them.
