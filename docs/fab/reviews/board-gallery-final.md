# Board gallery — TERMINAL VERDICT

**Status: CLOSED.** This record concludes the board-gallery visual review. The earlier review
`board-gallery-render-r3.md` recorded a real framing defect and **no terminal verdict**; that defect is
now fixed in the generator, the gallery is regenerated, and the regenerated images have been re-reviewed
to a terminal verdict by the visual consultant.

## The defect that was open (from r3, never fixed)

> **"(b) Image 2 — wing:** the outline is **not comfortably contained within the image margins**: the
> **leftmost connector-tab edge and the far-right board edge touch the image boundaries**. The top edge
> is also extremely close to the top boundary."

**Cause (measured, not inferred).** The generator exported with `--page-size-mode 2` ("board area
only"), which sizes the page to the board's own bounding box. For the elongated wing (outline
184.00 × 25.00 mm) that left a **horizontal margin of only 0.10 mm** — the outline was fully inside the
frame but visually touched the left and right edges. The board was never clipped; it was under-framed.
`--fit-page-to-board` does **not** change this (measured: byte-identical viewBox for all three boards),
and it was named in the code comment while never actually being passed.

**Fix (in the generator, `tracker/hardware/make_board_gallery.py`).** The frame is widened around the
board before rasterising: the SVG viewBox (and its width/height) is expanded by `MARGIN_FRACTION = 6%`
of the frame's longer side on **all four sides** (`_widen_frame()`). This is a viewport change; the
board files are untouched, the drawing sheet stays excluded, and no generated output was hand-edited.

Measured margins in the regenerated PNGs (transparent-background pixel bounds):

| board | PNG px | left | right | top | bottom |
|---|---|---|---|---|---|
| hub v9 | 1434 × 1600 | 236 | 257 | 320 | 320 |
| wing v9 | 1600 × 460 | 85 | 85 | 87 | 177 |
| base station | 1600 × 823 | 284 | 411 | 91 | 85 |

`python3 tracker/hardware/make_board_gallery.py --check` → **4 artefacts, 4 current, 0 stale, 0 missing**.

## Re-review of the REGENERATED images

Command (run **after** regeneration, so no stale PNG was reviewed):

```
python3 tracker/hardware/ask_astra.py --prompt-file /tmp/gallery-q.txt \
    docs/boards/hub-v9.png docs/boards/wing-v9.png docs/boards/base-station.png \
    --out docs/fab/reviews/board-gallery-render-r4.md
```

Question asked (answerable wrongly, targeting the actual defect; boards named so a per-board answer is
possible): *does each board's complete outline sit fully inside the image with a clear margin on all four
sides, and does any edge touch or get clipped by the boundary?*

- **SERVED MODEL: `gpt-6-astra`** (tool prints the served id; it matches the intended model)
- **Exit code: 0** — the consultant returned `VERDICT: CLEAN`
- Full transcript: `docs/fab/reviews/board-gallery-render-r4.md`

Per-board answer (consultant's own words, condensed):

| board | outline fully inside with clear margin on all 4 sides? | any edge touching / clipped? | reported margins |
|---|---|---|---|
| hub | Yes | No | L 17%, R 17%, T 21%, B 21% of image |
| wing | Yes — including the projecting tab on the left | No | L 5%, R 5%, T 19%, B 38% |
| base station | Yes | No | L 18%, R 26%, T 11%, B 11% |

The wing — the board r3 flagged — is the one that was fixed: its tab and far-right edge no longer touch
the boundary.

## sha256 of every PNG reviewed

```
e9591a2fc58436abee36ebc2906d6b2da2bf4db5a2181065983989154b9ad19b  docs/boards/hub-v9.png
dc72a383b6ea7f0d6bf47ed97be292a789a30dd0cc313c703cd6c82f5c67aaf4  docs/boards/wing-v9.png
5bb9a02a2bfbf17ba4588ea3348ddd6fbb57063dddb5a9afbec7654bc2aec72e  docs/boards/base-station.png
```

These hashes are of the exact files sent to the consultant; any later board or generator change
invalidates this verdict and requires regeneration (`make_board_gallery.py`) and re-review.

## What a copper-fill view CAN and CANNOT establish

These renders are `F.Cu` + `Edge.Cuts` only. **CAN** establish: the board outline and its framing; the
extent of the copper pour; the visible presence/absence of routed tracks and vias on the front layer;
coarse placement of footprints. **CANNOT** establish (confirmed by this review and by r3): correct net
connections; routing completeness; shorts/opens; inner- and back-layer routing or planes; actual
clearances; return paths; 2.4 GHz impedance / antenna-keepout compliance; copper thickness; whether
placement matches the schematic. Those are measured by the gates in `docs/fab/GATE-RESULTS.md`, not by
looking at a render.

## Closing note

An artefact that is reviewed but not concluded is worse than an unreviewed one, because it looks
reviewed. This record closes that gap: the framing defect r3 found is fixed in the generator, the
gallery is regenerated and byte-current, and the consultant's terminal verdict on the regenerated
images is **CLEAN** (served `gpt-6-astra`, exit 0).
