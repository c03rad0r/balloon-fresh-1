#!/usr/bin/env python3
"""
BASE-STATION NETLIST -- two boards, one generator (ADR-051 gate 1, ADR-054)

Operator decision 2026-10-13 (recommendation c):
  SHACK board   -> ORDERS NOW. Nothing in it depends on the LNA dispute.
  MASTHEAD board-> WAITS for the LiteVNA S21 sweep (TQP3M9037 433 MHz gate).

Run:
  ~/venvs/pw/bin/python base_station_netlist.py shack     -> base_station_shack.net
  ~/venvs/pw/bin/python base_station_netlist.py masthead  -> base_station_masthead.net

skidl notes (measured on cobrador, 2026-10-13):
  - bare library names do NOT resolve; pass the full /usr/share/kicad/symbols/*.kicad_sym path
  - Conn_Coaxial lives in Connector.kicad_sym (NOT Connector_Generic.kicad_sym)
  - Conn_Coaxial pins are numeric (1 = centre, 2 = shield); there is no .signal/.shield
  - every part needs a footprint or the netlist reports an error
"""
import os
import sys

os.environ.setdefault("KICAD9_SYMBOL_DIR", "/usr/share/kicad/symbols")
os.environ.setdefault("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")

from skidl import Circuit, Net, Part, ERC, generate_netlist  # noqa: E402

SYM = "/usr/share/kicad/symbols"
COAX = f"{SYM}/Connector.kicad_sym"
DEV = f"{SYM}/Device.kicad_sym"
GEN = f"{SYM}/Connector_Generic.kicad_sym"
REG = f"{SYM}/Regulator_Linear.kicad_sym"

SMA_FP = "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount"

BOARD = (sys.argv[1] if len(sys.argv) > 1 else "shack").lower()
assert BOARD in ("shack", "masthead"), "usage: base_station_netlist.py [shack|masthead]"

# ---- decision knobs (only place board decisions live) ----
PART_LNA = "TQP3M9037"        # PRE-GATE: LiteVNA S21 400-500 MHz sweep decides
PART_VGA = "ADL5240"          # AGC element, DNP first-flight
PART_DSA = "PE43711-CLASS"
POPULATE_AGC = False          # first-flight = TX-only level control


def coax(ref, val):
    return Part(COAX, "Conn_Coaxial", ref=ref, value=val, footprint=SMA_FP)


def make_shack():
    gnd, v3v3, vin = Net("GND"), Net("+3V3"), Net("VIN")

    # ---------- 433 RX input from the masthead (RF + DC on the same coax) ----------
    j_feed = coax("J_FEED", "SMA_feed_from_masthead")
    feed = Net("RF433_FEED")
    j_feed[1] += feed
    j_feed[2] += gnd

    # ---------- BIAS TEE: inject DC onto the feed centre conductor ----------
    l_bias = Part(DEV, "L", ref="L_BIAS", value="1uH_bias_tee_DC_inject",
                  footprint="Inductor_SMD:L_0805_2012Metric")
    l_bias[1] += vin
    l_bias[2] += feed
    c_bias = Part(DEV, "C", ref="C_BIAS_FEED", value="1nF_DC_return",
                  footprint="Capacitor_SMD:C_0402_1005Metric")
    c_bias[1] += feed
    c_bias[2] += gnd

    # ---------- DC block into the receiver chain ----------
    c_dc = Part(DEV, "C", ref="C_DCBLOCK", value="100pF_DC_block",
                footprint="Capacitor_SMD:C_0402_1005Metric")
    rx = Net("RF433_RX")
    c_dc[1] += feed
    c_dc[2] += rx

    # ---------- RX level control: AGC (DNP) or 0R bypass ----------
    rxout = Net("RF433_RX_OUT")
    if POPULATE_AGC:
        vga = Part(DEV, "R", ref="U_VGA", value=PART_VGA,
                   footprint="Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm")
        vga[1] += rx
        vga[2] += rxout
    else:
        rbp = Part(DEV, "R", ref="R_AGC_BYPASS", value="0R__populate_U_VGA_here",
                   footprint="Resistor_SMD:R_0402_1005Metric")
        rbp[1] += rx
        rbp[2] += rxout

    j_rxout = coax("J_RXOUT", "SMA_433_RX_out")
    j_rxout[1] += rxout
    j_rxout[2] += gnd

    # ---------- 2.4 GHz TX chain (first-flight populated) ----------
    j_in = coax("J_IN2G4", "SMA_2G4_TX_in")
    txin = Net("RF24_TX_IN")
    j_in[1] += txin
    j_in[2] += gnd

    att = Part(DEV, "R", ref="ATT1", value="XR-613_resistive_pad_6dB",
               footprint="Resistor_SMD:R_0603_1608Metric")
    txpad = Net("RF24_TX_PAD")
    att[1] += txin
    att[2] += txpad

    dsa = Part(DEV, "R", ref="DSA1", value=PART_DSA,
               footprint="Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm")
    txout = Net("RF24_TX_OUT")
    dsa[1] += txpad
    dsa[2] += txout

    j_ant = coax("J_ANT2G4", "SMA_2G4_antenna")
    j_ant[1] += txout
    j_ant[2] += gnd

    # ---------- PSU ----------
    ldo = Part(REG, "AP2112K-3.3", ref="U_PSU", value="AP2112K-3.3_SOT23_600mA",
               footprint="Package_TO_SOT_SMD:SOT-23-5")
    ldo[1] += vin
    ldo[2] += gnd
    ldo[3] += v3v3
    for i, rail in ((1, v3v3), (2, vin)):
        c = Part(DEV, "C", ref=f"C_DEC{i}", value="100nF",
                 footprint="Capacitor_SMD:C_0402_1005Metric")
        c[1] += rail
        c[2] += gnd
    return "base_station_shack.net", "SHACK"


def make_masthead():
    gnd = Net("GND")
    # powered over the coax from the shack bias tee -- no local supply
    j_ant = coax("J_ANT433", "SMA_433_antenna")
    ant = Net("RF433_ANT")
    j_ant[1] += ant
    j_ant[2] += gnd

    # NORMATIVE ORDER: band-pass filter BEFORE the LNA (ADR-072 INV-3).
    # The BPF rejects the 2.4 GHz TX carrier and out-of-band energy before any
    # gain stage, so the LNA cannot be desensitised or overdriven by them.
    bpf = Part(DEV, "R", ref="BPF433", value="FBP-433s_class_BPF",
               footprint="RF_Filter:Sawtek_1-1-2_SMD")
    lna_in = Net("RF433_LNA_IN")
    bpf[1] += ant
    bpf[2] += lna_in

    lna = Part(DEV, "R", ref="LNA1", value=PART_LNA,
               footprint="Package_TO_SOT_SMD:SOT-89-3")
    lna_out = Net("RF433_LNA_OUT")
    lna[1] += lna_in
    lna[2] += lna_out

    lim = Part(DEV, "D_Schottky", ref="D_LIM", value="PIN_RF_limiter_10-20dBm",
               footprint="Package_TO_SOT_SMD:SOT-143")
    lim_out = Net("RF433_LIM_OUT")
    lim[1] += lna_out
    lim[2] += gnd

    # DC arrives up the coax and is separated at the output by the LNA's own
    # bias network -- modelled here as the feed inductor on the LNA output node.
    l_feed = Part(DEV, "L", ref="L_FEED", value="1uH_DC_feed_from_coax",
                  footprint="Inductor_SMD:L_0805_2012Metric")
    feed = Net("RF433_FEED")
    l_feed[1] += lim_out
    l_feed[2] += feed

    j_feed = coax("J_FEED", "SMA_feed_to_shack")
    j_feed[1] += feed
    j_feed[2] += gnd
    return "base_station_masthead.net", "MASTHEAD"


netfile, label = (make_shack() if BOARD == "shack" else make_masthead())
ERC()
generate_netlist(file_=netfile)
print(f"{label} netlist written: {netfile}")
