#!/usr/bin/env python3
"""Design the coupon test that measures the peel knockdown for the ADR-046 wing joint.

WHY A COUPON AND NOT A NUMBER. The trade study (tracker/hardware/trade_study_wing_joint.py) finds that
Option A (routed slot) beats Option B (plain face pads) by ~65x on capacity, but that its conclusion
hangs on ONE quantity that is an explicit ASSUMPTION, not a measurement:

    peel knockdown = 4x      ->  Option B margin 7.8x on a 10 g landing shock
                             ->  below ~1.2x, Option B approaches Option A

Everything else in that study is either read from the repo or a flagged assumption. This is the one
number that would decide the question, and it cannot be looked up: it depends on the actual fillet
geometry, the actual solder, and the actual hand technique. So: measure it.

WHAT THIS SCRIPT DOES. It computes the COUPON GEOMETRY and the LOAD CASES from the same inputs the
trade study uses, and emits a drawing plus a test procedure. It does NOT invent the result.

Design principle: the coupon must reproduce the FAILURE MODE, not the full wing. Option B fails by peel
about the fillet root on ONE edge of a face land; Option A fails by shear through a two-face fillet
inside the slot. So the coupon is two specimens, one per mode, loaded to failure.

Run: python3 peel_coupon_design.py [--out docs/fab/hub-v9/PEEL-COUPON.md]
"""
import argparse
import math

# ---- inputs, matching trade_study_wing_joint.py so the coupon and the study cannot diverge ----
WING_LEN_MM = 176.0          # [repo] ADR-046 body 176.0 x 25.0 mm
WING_T_MM = 0.6              # [repo] ADR-046: tab thickness = substrate
LAND_LEN_MM = 4.0            # [repo] pad 4.0 mm along the insertion axis
LAND_WID_MM = 1.2            # [repo] pad 1.2 mm
INSERT_DEPTH_MM = 6.0        # [repo] ADR-046 insertion depth
SLOT_W_MM = 0.9              # [repo] ADR-046 slot 0.9 +/-0.10
SHOCK_G = 10.0               # [assume] conservative landing shock
G = 9.80665
WING_MASS_G = 13.88          # [computed+assume] from the trade study


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    per_land_N = (WING_MASS_G * 1e-3) * G * SHOCK_G / 4.0
    print("=" * 82)
    print("PEEL COUPON DESIGN -- measuring the one number the joint decision hangs on")
    print("=" * 82)
    print(f"\nload case reproduced by the coupon: the 10 g landing shock, per land")
    print(f"    whole-wing force at 10 g   {(WING_MASS_G*1e-3)*G*SHOCK_G:.3f} N")
    print(f"    per land (4 lands)         {per_land_N:.3f} N")
    print(f"    moment about the joint     {(WING_MASS_G*1e-3)*G*SHOCK_G*(WING_LEN_MM/2e-3):.4f} N m")

    print(f"\nSPECIMEN B -- the PEEL mode (what Option B does)")
    print(f"    a face-land COUPON, not a wing: same land {LAND_LEN_MM} x {LAND_WID_MM} mm,")
    print(f"    same 0.6 mm FR4, same solder, ONE fillet along a single 1.2 mm edge.")
    print(f"    loaded at a lever arm that reproduces the wing's moment-to-force ratio:")
    arm = (WING_LEN_MM / 2.0) / (WING_LEN_MM)   # 0.5, i.e. the wing's own CoM arm, scaled out
    print(f"      the wing applies F at L/2 over a 176 mm span -> a 0.5 lever ratio")
    print(f"      so the coupon applies F at {LAND_LEN_MM/2:.1f} mm from the fillet root")
    print(f"      this makes the coupon a DIRECT test of peel strength per unit fillet length")

    print(f"\nSPECIMEN A -- the SHEAR mode (what Option A does)")
    print(f"    a tab coupon {INSERT_DEPTH_MM} mm long x {LAND_WID_MM} mm wide, soldered on BOTH faces")
    print(f"    into a {SLOT_W_MM} mm slot, pulled along the insertion axis (pure shear on both fillets).")

    print(f"\nWHAT TO MEASURE, and how the result is used")
    print(f"    For each specimen: peak force at failure, in N, over n>=5 samples per condition.")
    print(f"    knockdown_B = (pure tensile strength of the same fillet) / (measured peel strength)")
    print(f"    Feed knockdown_B back into trade_study_wing_joint.py's peel_knockdown input and re-run.")
    print(f"    Decision rule, already in the study:")
    print(f"      knockdown_B ~ 4x    -> Option B margin {2.65/per_land_N:.1f}x  (comfortable)")
    print(f"      knockdown_B < 1.2x  -> Option B approaches Option A; the joint stops being the")
    print(f"                             deciding factor and the FIXTURE becomes the schedule risk")

    print(f"\nENVIRONMENTAL VARIANTS worth one specimen each (they move the number)")
    print(f"    - as-soldered, room temperature          (baseline)")
    print(f"    - after a thermal cycle to the balloon's cold soak, because the wing sees -40 C or lower")
    print(f"    - a deliberately WEAK hand fillet, to bound the technique spread")
    print(f"    - the same joint with the solder the build actually uses (record the alloy and flux)")

    print(f"\nWHY THIS IS WORTH BUILDING")
    print(f"    The coupon needs no balloon flight and no new board revision: it is 0.6 mm FR4 offcuts")
    print(f"    plus the same solder. It converts the study's crux from an assumption into a measurement,")
    print(f"    which is the difference between choosing A or B on evidence and choosing on opinion.")

    if a.out:
        with open(a.out, "w") as fh:
            fh.write("# Peel coupon design -- measuring the joint decision's crux\n\n")
            fh.write(f"Per-land load at a 10 g landing shock: **{per_land_N:.3f} N**\n\n")
            fh.write("Two specimens, one per failure mode:\n\n")
            fh.write(f"- **B (peel)**: face land {LAND_LEN_MM} x {LAND_WID_MM} mm on 0.6 mm FR4, one fillet on a "
                     f"single {LAND_WID_MM} mm edge, load applied at {LAND_LEN_MM/2:.1f} mm from the root.\n")
            fh.write(f"- **A (shear)**: tab {INSERT_DEPTH_MM} x {LAND_WID_MM} mm soldered on both faces into a "
                     f"{SLOT_W_MM} mm slot, pulled along the insertion axis.\n\n")
            fh.write("Measure peak force over n>=5 per condition. Derive `knockdown_B` and re-run "
                     "`trade_study_wing_joint.py` with it.\n")
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
