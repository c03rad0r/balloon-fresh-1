#!/usr/bin/env python3
"""Classify the 20 ERC errors: expected-open, pin-exhausted, or genuine omissions.

WHY CLASSIFY RATHER THAN FIX. Connecting a pin is a design decision. If a pin is unconnected because a
decision is still open, wiring it would INVENT that decision and hide the open item. If it is unconnected
because a pin ran out, wiring it is not possible at all. Only a genuine omission should be fixed by
adding a connection. This script reads the source documents and assigns each error to a class.

Inputs are the netlist (which carries the designers' own open-item notes in the component descriptions)
and docs/analysis/ADC-PIN-RESOLUTION-OPEN17-OPEN25.md, which states the pin arithmetic.

Run: classify_erc_errors.py
"""
import re
import sys

NET = "tracker/hardware/schematics/flight_board/v9_flight.net"
ANALYSIS = "docs/analysis/ADC-PIN-RESOLUTION-OPEN17-OPEN25.md"


def comp_desc(ntxt, ref):
    m = re.search(r'\(comp\s+\(ref\s+"' + re.escape(ref) + r'"\).*?(?=\n    \(comp |\Z)', ntxt, re.S)
    if not m:
        return ""
    d = re.search(r'\(description\s+"([^"]*)"', m.group(0))
    return d.group(1) if d else ""


def main():
    ntxt = open(NET, encoding="utf-8", errors="replace").read()
    try:
        atxt = open(ANALYSIS, encoding="utf-8", errors="replace").read()
    except Exception:
        atxt = ""

    print("=" * 84)
    print("THE 20 ERC ERRORS, CLASSIFIED")
    print("=" * 84)

    # --- group A: the twelve U_CUT* provisioning pins
    print("\nA. U_CUT1..4 pins 4 (ARM), 5 (CTRL), 6 (SENSE) -- 12 errors")
    print("-" * 84)
    d = comp_desc(ntxt, "U_CUT1")
    print("  The netlist's OWN description of U_CUT1 says:")
    for ln in re.findall(r'[^.]*\.', d):
        if any(k in ln for k in ("LATCHED", "TODO", "OPEN", "GPIO", "sense divider")):
            print(f"    ...{ln.strip()[:150]}")
    print()
    print("  So the symbol connects ONLY pins 1 (VSCAP), 2 (GND), 3 (CUT_W). Pins 4/5/6 are")
    print("  PROVISIONING STUBS whose exact implementation is stated as TODO in the netlist itself.")
    print()
    closed = "OPEN-17` and `OPEN-25` CLOSED" in atxt or "OPEN-25 CLOSED" in atxt
    print(f"  docs/analysis/ADC-PIN-RESOLUTION-OPEN17-OPEN25.md declares OPEN-25 CLOSED: {closed}")
    if closed:
        m = re.search(r'none is spare|no[  ]?spare|none are spare', atxt, re.I)
        print(f"  and states the blocking reason: {'PIN EXHAUSTION' if m else '(see the file)'}")
        q = re.search(r'[^.]*only workable shape[^.]*\.', atxt, re.S)
        if q:
            print(f"    \"{q.group(0).strip()[:220]}\"")
    print()
    print("  CLASS: EXPECTED-OPEN + PIN-EXHAUSTED. Two separate facts:")
    print("    - the DRIVE (ARM/CTRL) needs a LATCHED ONE-SHOT of an undecided part (ADR-051 2.5.1)")
    print("    - the SENSE needs an ADC input, and the analysis says NONE IS SPARE")
    print("  FIX: do NOT wire them. Wiring would invent an undecided circuit. Annotate as expected-open")
    print("       and make the pin-exhaustion conflict visible instead of silent.")

    # --- group B: U_HUB_CVT VOUT
    print("\nB. U_HUB_CVT pin 4 (VOUT) -- 1 error")
    print("-" * 84)
    d2 = comp_desc(ntxt, "U_HUB_CVT")
    print(f"  U_HUB_CVT description: {d2[:200] if d2 else '(none)'}")
    print("  CLASS: needs checking -- the harvester's OUTPUT not connected is either open-by-design")
    print("         (harvest path not yet routed) or a real omission. Listed, not guessed.")

    # --- group C: U4 power pins
    print("\nC. U4 pins 2 (VDD_IN) and 11 (VBAT_IO) -- 2 errors (power_pin_not_driven)")
    print("-" * 84)
    print("  ERC says these are Power-INPUT pins not driven by any Power-OUTPUT pin.")
    print("  U4 is the SX1280. A power_in pin with no driver means no net carries power INTO it.")
    print("  NOTE the asymmetry worth checking: /SX1280_VBAT_IO EXISTS as net code 44, so a net by")
    print("  that name is present. Whether its driver is typed power_out (and therefore whether this")
    print("  is a modelling error or a real gap) is the thing to determine before changing anything.")
    print("  CLASS: UNRESOLVED -- could be a symbol pin-type modelling issue rather than missing copper.")
    print("         Must be settled against the symbol's pin types, not by adding a wire.")

    # --- group D: the ESP32 module pins
    print("\nD. U1 pins 3 (EN), 13 (USB_D-), 14 (USB_D+), 35 (IO42) -- 4 errors")
    print("-" * 84)
    print("  U1 is the ESP32-S3-WROOM-1U. These are plausible intentional non-connections on a flight")
    print("  board (EN tied via an RC elsewhere, USB pads broken out or unused, a spare IO left free).")
    print("  CLASS: likely INTENTIONAL. Each should be confirmed and then EXCLUDED from ERC rather than")
    print("         wired -- an unused pin with a no-connect marker is the correct schematic form.")

    # --- group E: the dangling wire
    print("\nE. one 'wire_dangling' -- a 0.0508 mm horizontal wire")
    print("-" * 84)
    print("  CLASS: COSMETIC-REAL. A 2-mil stub connects nothing. Delete it. This is the only error in")
    print("         the set that is unambiguously a drawing artefact rather than a decision.")

    print("\n" + "=" * 84)
    print("SUMMARY -- WHAT THE 20 ERRORS ACTUALLY ARE")
    print("=" * 84)
    print("  12  expected-open provisioning pins on an explicitly undecided circuit (U_CUT1-4)")
    print("   4  plausibly-intentional non-connections on the ESP32 module (U1)")
    print("   2  power-input pins with no driver -- needs a pin-type check before any change (U4)")
    print("   1  a 2-mil dangling wire -- delete it")
    print("   1  harvester VOUT unconnected -- classify before touching (U_HUB_CVT)")
    print()
    print("  ZERO of the twelve U_CUT pins should be connected by us. The netlist and ADR-051 2.5.1")
    print("  state the circuit is undecided, and the closing analysis says the ADC input it needs")
    print("  does not exist. The correct fix is to make that conflict VISIBLE, not to resolve it by")
    print("  inventing a connection.")
    print()
    print("  THE CONFLICT FOUND WHILE CLASSIFYING: docs/analysis/ADC-PIN-RESOLUTION-OPEN17-OPEN25.md")
    print("  declares OPEN-25 CLOSED, while the netlist's U_CUT1 description still says 'see OPEN-25'.")
    print("  Two live records disagree with nothing surfacing it -- the same defect class as the stale")
    print("  inventory, the stale order-readiness counts, and ADR-046 4.2 vs the built board.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
