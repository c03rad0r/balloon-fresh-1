# Gallery render framing — measured, not inferred

A visual review of these renders reported that the wing render was clipped:
"the leftmost connector-tab edge and the far-right board edge touch the image boundaries",
and asked for a re-export "with margins on all sides so its entire board outline can be inspected".

**Measured, the board is NOT clipped.** From `docs/boards/wing-v9.svg`:

    svg page (KiCad frame):   184.10 x 37.13 mm
    board outline:            184.00 x 25.00 mm
    margin added:             x 0.10 mm, y 12.13 mm
    => the board is enclosed by its frame on every side

The render was not the problem: it reproduces its own SVG exactly
(1600 x 323 px, aspect 4.95, against the SVG viewBox aspect 184.0992/37.1348 = 4.96).

**So this is a FRAMING IMPRESSION, not a clipping defect.** The reviewer's instinct was not baseless:
the horizontal margin is only **0.10 mm**, so the board visually touches the left and right edges even
though it is fully inside the frame. The aspect discrepancy the reviewer saw (board 7.36 vs render 4.95)
comes from KiCad padding the page VERTICALLY by 12.13 mm for a long thin board, not from cutting it.

**Recorded rather than "fixed".** Chasing this would have meant changing a correct renderer to satisfy a
misreading of a correct artefact. The check that settles it is arithmetic on the SVG viewBox against the
board's own outline — not another look at the picture.

If a future render needs more usable margin, add padding at the raster step; do NOT re-enable
`--page-size-mode 0`, which reinstates the worksheet overlay that the first review correctly rejected.
