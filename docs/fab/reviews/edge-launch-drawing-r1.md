# Astra visual review

Served model: gpt-6-astra
Images: docs/fab/jlc-query/edge-launch-cross-section.png

### Checks

1. **OVERLAP: Fail.** Above View A, the “0.30 mm” dimension overlaps the subtitle. Below the View A heading, “exposed copper pad (F.Cu) — solderable” overlaps “mating wing tab — 0.6 mm FR4, copper facing the board.” The dashed clearance guide also crosses this heading/callout area.
2. **CLIPPING: Pass;** no text or graphic is visibly cut off by the image boundary.
3. **LEGIBILITY: Fail.** The overlapping clearance annotation and the two overlapping material/copper callouts above View A are not cleanly readable.
4. **CONSISTENCY: Fail.** The solder-mask requirement says the opening “ends BEFORE the routed edge,” while the drawing and other notes require exposed copper to the edge. View A also depicts a horizontal gap between boards, whereas the “slot 0.9 mm minus tab 0.6 mm = 0.30 mm” annotation describes clearance across a slot receiving the tab thickness.
5. **COMPLETENESS: Fail.** The named 0.9 mm slot and the tab seated 6.0 mm into it are not drawn. The solder-mask opening boundary is not drawn, so its termination cannot be checked.
6. **ARROW / DIMENSION CONVENTION: Fail.** In View A, the arrowheads on “pad 4.0 mm” and “insertion depth 6.0 mm” point inward, away from their endpoint ticks. Their extension lines do not establish both measured features. The floating “0.30 mm” dimension is not connected to actual slot faces. In View B, “4.0 mm (insertion axis)” has only an underline, not a dimension with endpoints and arrowheads.
7. **TECHNICAL CORRECTNESS: Fail.** View A shows two boards end-to-end with a solder bridge, not the claimed seated tab-and-slot interface. Also, the specification calls the freshly routed, unplated copper edge the electrical contact surface while specifying ENIG as the solderable finish; ENIG on the board faces does not establish a protected finish on copper newly exposed by routing.
8. **TYPOS: Fail.** “HASBL” in the Surface finish row is a misspelled finish abbreviation.

### Actionable defect list

1. Move the “0.30 mm” dimension and its clearance explanation into clear space below the subtitle, with no text overlap.
2. Separate the exposed-copper and mating-tab callouts above View A; add leaders to their respective parts and keep the dashed guide clear of the heading and text.
3. Resolve the solder-mask contradiction: if copper must remain exposed to the routed edge, specify an opening that reaches that edge and draw its boundary.
4. Redraw View A to include the actual 0.9 mm slot and the 0.6 mm tab in its seated position; dimension the 0.30 mm clearance across the receiving slot rather than across the end-to-end board gap.
5. Show the slot entrance and seated tab tip or stop, and attach the 6.0 mm insertion-depth dimension to those features.
6. Reverse the arrowheads on View A’s pad-length and insertion-depth dimensions so their tips meet the endpoint extension lines; extend those lines from the measured features.
7. Replace View B’s underline beneath “4.0 mm (insertion axis)” with a proper dimension spanning the pad’s inner end to the routed edge.
8. Clarify whether the functional contact is the top pad, a soldered joint, or the freshly cut copper edge. If it is the cut edge, explicitly specify its required surface condition and qualification rather than implying the face ENIG finish protects it.
9. Replace “HASBL/HASL acceptable” with “HASL acceptable,” or spell out the intended alternative finish if a different process was meant.

VERDICT: DEFECTS_PRESENT 9
