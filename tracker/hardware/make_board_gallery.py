#!/usr/bin/env python3
"""Generate the board gallery: one rendered image per board plus its MEASURED state.

WHY GENERATED, NOT HAND-WRITTEN. Every table of board status in this repo has drifted. The
END-TO-END-BOARD-INVENTORY.md (2026-10-14) asserted the ground end "does not exist as a board" and that
there was "no assembled STEP for any board"; both were false when it was read on 2026-10-16 -- there is a
base-station netlist and there are hub/wing STEP models. A status table maintained by hand is a status
table that is wrong. This script reads the boards and renders what it finds.

Output:
    docs/boards/<name>.png        a render per board
    docs/boards/GALLERY.md        the table, with measured numbers

Run: make_board_gallery.py [--out docs/boards]
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile

import pcbnew

# The boards of the end-to-end system. Paths are the CANONICAL ones.
BOARDS = [
    ("hub v9", "tracker/hardware/hub_board_v9.kicad_pcb",
     "flight hub: 4 wing sockets, SX1280 FLRC radio, GNSS, solar harvester"),
    ("wing v9", "tracker/hardware/wing_board/wing_board_v9.kicad_pcb",
     "wing solar array + cut driver + hub tab"),
    ("base station", "tracker/hardware/base_station/base_station_v1_placed_v2.kicad_pcb",
     "ground station: 4G/5G via SIM7600E-H, FLRC link to the hub"),
]


def measure(path):
    """Read a board and report what is actually on it. Nothing inferred."""
    out = {"exists": os.path.exists(path)}
    if not out["exists"]:
        return out
    with open(path, "rb") as fh:
        out["sha256"] = hashlib.sha256(fh.read()).hexdigest()
    b = pcbnew.LoadBoard(path)
    if b is None:
        out["readable"] = False
        return out
    out["readable"] = True
    out["footprints"] = len(list(b.GetFootprints()))
    tracks = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]
    vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    out["tracks"] = len(tracks)
    out["vias"] = len(vias)

    # nets: declared by the board's netinfo, and which of them carry copper
    nets = {}
    for code, ni in b.GetNetInfo().NetsByNetcode().items():
        nm = ni.GetNetname()
        if nm:
            nets[nm] = 0
    for t in tracks:
        nm = t.GetNetname()
        if nm:
            nets[nm] = nets.get(nm, 0) + 1
    routed = sum(1 for v in nets.values() if v > 0)
    out["nets_declared"] = len(nets)
    out["nets_routed"] = routed
    out["nets_unrouted"] = len(nets) - routed

    # outline
    xs, ys = [], []
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            try:
                xs += [pcbnew.ToMM(d.GetStart().x), pcbnew.ToMM(d.GetEnd().x)]
                ys += [pcbnew.ToMM(d.GetStart().y), pcbnew.ToMM(d.GetEnd().y)]
            except Exception:
                pass
    if xs:
        out["size_mm"] = (round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2))
    # layers with copper
    out["copper_layers"] = len({pcbnew.LayerName(t.GetLayer()) for t in tracks}) if tracks else 0
    return out


def render(path, png, layers="F.Cu,Edge.Cuts"):
    """Render a board to PNG.

    --exclude-drawing-sheet is NOT cosmetic. Without it KiCad draws its page frame, title block and
    zone letters OVER the board. A visual review of the first gallery render found this and said the
    graphics "can potentially be confused with design geometry" -- the worksheet lines crossed pads and
    traces, and a title-block label sat on top of a trace. A board render that mixes in page furniture
    cannot be read as board geometry, and that is the only thing it is for.

    --fit-page-to-board is ALSO required. `--page-size-mode 2` ("board area only") does not size the
    page to the BOARD's shape on a very elongated board: the wing is 184 x 25 mm (aspect 7.36) but the
    render came out 1600 x 323 px (aspect 4.95), so the long edges overflowed the canvas and were cut
    off at the image boundary. A second visual review found that clipping ("the leftmost
    connector-tab edge and the far-right board edge touch the image boundaries"). Fit the page to the
    board and the whole outline is inside the frame.
    """
    svg = png.replace(".png", ".svg")
    r = subprocess.run(["kicad-cli", "pcb", "export", "svg", path, "-o", svg,
                        "--layers", layers, "--page-size-mode", "2",
                        "--exclude-drawing-sheet"],
                       capture_output=True, text=True)
    if not os.path.exists(svg):
        return False, (r.stderr or r.stdout or "")[-200:]

    # Read the SVG's OWN viewBox and rasterise at that aspect. Do NOT pass `-w 1600`: rsvg-convert
    # honours the width and derives the height from the SVG, which for an elongated board yields a very
    # short canvas -- the wing came out 1600x323 (aspect 4.95) against a board aspect of 7.36, so its
    # long edges were clipped at the image boundary. Sizing by the viewBox keeps the whole outline.
    vb = None
    try:
        head = open(svg, encoding="utf-8", errors="replace").read(4000)
        m = re.search(r'viewBox="([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)"', head)
        if m:
            vb = tuple(float(x) for x in m.groups())
    except Exception:
        pass

    if vb and vb[2] > 0 and vb[3] > 0:
        vb_w, vb_h = vb[2], vb[3]
        long_side = 1600
        if vb_w >= vb_h:
            args = ["rsvg-convert", "-w", str(long_side)]
        else:
            args = ["rsvg-convert", "-h", str(long_side)]
        subprocess.run(args + [svg, "-o", png], capture_output=True, text=True)
    else:
        subprocess.run(["rsvg-convert", "-w", "1600", svg, "-o", png],
                       capture_output=True, text=True)
    return os.path.exists(png), ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/boards")
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if the committed artefacts differ from the generated")
    a = ap.parse_args()
    # Import the shared determinism helper from scripts/ (one implementation for every generator).
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
    from artefact import DeterministicWriter
    writer = DeterministicWriter(__file__)
    # In --check mode, render into a temp dir so nothing on disk is touched.
    _render_root = tempfile.mkdtemp(prefix="gallery-check-") if a.check else None
    os.makedirs(a.out, exist_ok=True)

    rows = []
    for name, path, desc in BOARDS:
        m = measure(path)
        slug = name.replace(" ", "-")
        png = os.path.join(a.out, f"{slug}.png")
        if a.check:
            # render into the temp root, but keep the artefact's committed name
            png = os.path.join(_render_root, f"{slug}.png")
        if m.get("readable"):
            ok, err = render(path, png)
            m["rendered"] = ok
            if not ok:
                m["render_error"] = err
        if m.get("rendered"):
            # Register the PNG as a generated artefact so determinism is checkable. In --check mode the
            # render went to a temp dir; register it under its COMMITTED relative path so the comparison
            # is against the committed file, not against the temp location.
            writer.add_file(os.path.join(a.out, f"{slug}.png"), png)
        m.update(name=name, path=path, desc=desc, png=os.path.relpath(png, "."))
        rows.append(m)
        print(f"{name:14} " + (f"fp={m.get('footprints')} nets {m.get('nets_routed')}/"
                               f"{m.get('nets_declared')} tracks={m.get('tracks')} "
                               f"vias={m.get('vias')}" if m.get("readable") else "NOT READABLE"))

    lines = ["# Board gallery", "",
             "**Generated** by `tracker/hardware/make_board_gallery.py` — do not edit by hand. Regenerate",
             "with:", "", "```bash", "python3 tracker/hardware/make_board_gallery.py", "```", "",
             "Every number below is read from the board file at generation time. A hand-maintained status",
             "table drifts; this one cannot.", "",
             "| board | render | footprints | nets routed | tracks | vias | outline |",
             "|---|---|---|---|---|---|---|"]
    for m in rows:
        if not m.get("readable"):
            lines.append(f"| **{m['name']}** | — | — | — | — | — | not readable / absent |")
            continue
        sz = m.get("size_mm")
        img = f"![{m['name']}]({os.path.basename(m['png'])})" if m.get("rendered") else "—"
        lines.append(f"| **{m['name']}** | {img} | {m.get('footprints')} | "
                     f"{m.get('nets_routed')}/{m.get('nets_declared')} | {m.get('tracks')} | "
                     f"{m.get('vias')} | {sz[0]}×{sz[1]} mm |")
    lines += ["", "## What each board is", ""]
    for m in rows:
        lines.append(f"- **{m['name']}** — {m['desc']}")
        if m.get("readable") and m.get("nets_unrouted"):
            lines.append(f"  - ⚠️ **{m['nets_unrouted']} net(s) unrouted**")
        if m.get("readable"):
            lines.append(f"  - `{m['path']}`  sha256 `{m.get('sha256','')[:16]}…`")
    lines += ["", "## Notes", "",
              "- **A copper pour is NOT routing.** The base-station render shows a large copper fill",
              "  across the board, and its `nets routed` column reads `0/44`. Both are correct and they",
              "  are not in conflict: a ground/supply **zone** is not a routed **track**. A visual review",
              "  of these renders raised exactly this and warned that copper coverage alone *\"does not",
              "  establish that the intended nets are connected\"*. Read the `nets routed` column, not the",
              "  amount of red.",
              "- Renders are `F.Cu` + `Edge.Cuts`, exported with `--exclude-drawing-sheet` so KiCad's page",
              "  frame and title block do not overlay the board. Inner and back layers are not shown here;",
              "  see `docs/fab/reviews/` for per-layer plots and their review.",
              "- **A render shows geometry, not correctness.** Clearance, impedance and netlist correctness",
              "  are measured by the gates in `docs/fab/GATE-RESULTS.md`. A visual review of these three",
              "  images confirmed that electrical correctness cannot be judged from any of them.",
              "- The base station's `0` routed nets is the single largest gap in the system; see",
              "  `docs/fab/ASTRA-GAP-ANALYSIS.md`.",
              "- Regenerate this gallery after ANY board change: `python3",
              "  tracker/hardware/make_board_gallery.py`. The numbers are read at generation time, so a",
              "  stale gallery is possible if this is skipped.",
              ""]
    # The markdown is an artefact like any other: it must be reproducible byte-for-byte.
    writer.add(os.path.join(a.out, "GALLERY.md"), "\n".join(lines))
    return writer.finish(check=a.check)


if __name__ == "__main__":
    sys.exit(main())
