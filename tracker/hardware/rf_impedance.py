#!/usr/bin/env python3
"""Read the stackup and net classes, then compute the 50-ohm microstrip width.

For a 2.4 GHz match the trace between U4.pad22, C0 and L1 must be a controlled-impedance line, not
just "connected". The move made the three pads 3 mm apart; this works out what WIDTH that line
should have on the board's actual stackup.

Wheeler/IPC-2141 microstrip (surface layer over one dielectric, ground plane below):
    Z0 = (87 / sqrt(eps_r + 1.41)) * ln(5.98*H / (0.8*W + T))
with H = dielectric height, W = trace width, T = copper thickness. Solved for W by bisection.

NOTE ON VALIDITY: this is the standard closed-form approximation, not a field solve. It is good to
roughly 2% for W/H in the 0.1..3 range. The result is a STARTING POINT that must be confirmed by the
fab's own impedance calculator, and the final authority is the VNA measurement the consultant asked
for. Reported with its assumptions so they can be falsified.
"""
import json
import math
import sys

C0 = 2.998e8


def z0_microstrip(w_mm, h_mm, t_mm, eps_r):
    if w_mm <= 0 or h_mm <= 0:
        return float("nan")
    return (87.0 / math.sqrt(eps_r + 1.41)) * math.log(5.98 * h_mm / (0.8 * w_mm + t_mm))


def solve_width(z_target, h_mm, t_mm, eps_r, lo=0.05, hi=3.0):
    for _ in range(200):
        mid = (lo + hi) / 2
        z = z0_microstrip(mid, h_mm, t_mm, eps_r)
        if math.isnan(z):
            hi = mid
            continue
        # wider trace -> lower impedance
        if z > z_target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main():
    pro = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pro"
    d = json.load(open(pro))
    ds = d.get("board", {}).get("design_settings", {})
    st = ds.get("stackup", {})
    print(f"project: {pro}")
    print(f"stackup key present: {bool(st)}")

    eps_r = None
    h = None
    t = None
    if st:
        layers = st.get("layers", [])
        print(f"  layers declared: {len(layers)}")
        # print the dielectric immediately below the first copper layer
        for i, L in enumerate(layers):
            print(f"    [{i}] type={L.get('type'):20} name={L.get('name','')!r:22} "
                  f"thickness={L.get('thickness')} epsR={L.get('epsilon_r')}")
            if h is None and L.get("type") == "dielectric":
                h = L.get("thickness")
                eps_r = L.get("epsilon_r")
        # copper thickness from the first copper layer
        for L in layers:
            if L.get("type") == "copper":
                t = L.get("thickness")
                break
    if h is None:
        h = 0.21          # JLCPCB JLC04161H-3313: prepreg between L1 and L2
        eps_r = 4.1
        print(f"\n  no stackup in the project file -> using the JLCPCB 1.6mm 4-layer default:")
        print(f"    H (L1 to L2 dielectric) = {h} mm, eps_r = {eps_r}")
    if t is None:
        t = 0.035         # 1 oz copper
    if eps_r is None:
        eps_r = 4.1

    print(f"\nASSUMPTIONS USED: H={h} mm, T={t} mm, eps_r={eps_r}")
    print(f"  (JLCPCB 4-layer 1.6mm: L1-L2 prepreg ~0.21 mm, eps_r ~4.1, 1 oz outer copper)")
    print()
    for z in (50.0, 45.0, 55.0):
        w = solve_width(z, h, t, eps_r)
        print(f"  Z0 = {z:5.1f} ohm  ->  W = {w:.3f} mm   "
              f"(check: Z0({w:.3f}) = {z0_microstrip(w, h, t, eps_r):.2f} ohm)")
    print()
    w50 = solve_width(50.0, h, t, eps_r)
    # sanity: what does the board's existing default width give?
    for probe in (0.2, 0.25, 0.3, 0.35, 0.5):
        print(f"  a {probe:.2f} mm trace on this stackup is {z0_microstrip(probe, h, t, eps_r):6.2f} ohm")
    print()
    print(f"RECOMMENDATION: route /SX1280_RF at W = {w50:.3f} mm for 50 ohm.")
    print(f"  The board's 0.20 mm minimum could not reach 50 ohm on this stackup; a wider RF trace is")
    print(f"  REQUIRED, not optional, and it must be checked against the fab's impedance calculator.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
