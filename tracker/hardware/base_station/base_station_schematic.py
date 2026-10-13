#!/usr/bin/env python3
"""
BASE-STATION SCHEMATIC -- Stage 1 netlist (ADR-051 gate 1, ADR-054 SKiDL)

Ground side of the balloon bent-pipe gateway. Two sub-circuits on ONE netlist,
two physical boards (per the approved-recommendation split):

  MASTHEAD board (tiny, weatherproof, no MCU):
    SMA_antenna -> BPF_433 -> LNA (TQP3M9037) -> PIN limiter -> SMA_feed
    Powered over the coax: bias-tee DC INJECT on the shack board, DC BLOCK
    after the masthead chain (the LNA's own DC path feeds through its output).

  SHACK board:
    433 RX:  SMA_feed -> DC_BLOCK -> (option AGC: ADL5240 VGA) -> SMA_out_rx
    2.4 GHz TX: SMA_in_tx -> XR-613 (pad/attenuator) -> DSA (PE43711-class,
             level control) -> SMA_ant_2g4  [first-flight: TX-only populate]
    Bias tee: DC_INJECT on the 433 feed line (powers the masthead LNA)
    PSU: VIN -> LDO -> 3V3 rail (LNA + DSA logic)

DNP-OPTION pattern (per ADR-051 + the checklist's "qty 1 on TX only is the
sufficient first-flight build"): the AGC element is instantiated but marked
DNP; populate for the full-AGC build by flipping the flag in one place.

PRE-GATE (the TQP3M9037 dispute, checklist row 3): the LNA symbol is
parameterised by PART_LNA. If the bench S21 sweep fails (Qorvo 0.7-6 GHz
authoritative -> no 433 coverage), swap to a 433-capable LNA in ONE constant
and regenerate; nothing else changes.

Run:  python3 base_station_schematic.py
Out:  base_station.net   (+ .erc report via skidl ERC)
"""
import os

os.environ.setdefault("KICAD9_SYMBOL_DIR", "/usr/share/kicad/symbols")
os.environ.setdefault("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")

from skidl import *  # noqa: E402

# ---------------- knobs (decisions live here, nowhere else) ----------------
PART_LNA = "TQP3M9037"        # PRE-GATE: bench S21 400-500 MHz sweep decides
PART_VGA = "ADL5240"          # AGC element (DNP first-flight)
PART_DSA = "PE43711-CLASS"    # 2.4 GHz TX level control (populate first-flight)
POPULATE_AGC = False          # first-flight = TX-only level control
POPULATE_LIMITER = True       # PIN limiter = cheap insurance (checklist row 4)

# ---------------- rails / connectors ----------------
gnd = Net("GND")
v3v3 = Net("+3V3")
vin = Net("VIN")

j_ant433 = Part("/usr/share/kicad/symbols/Connector.kicad_sym", "Conn_Coaxial", ref="J_ANT433",
                value="SMA_433_antenna_masthead",
                footprint="Connector_Coaxial:SMA_Amphenol_132289_EdgeMount")
j_feed = Part("/usr/share/kicad/symbols/Connector.kicad_sym", "Conn_Coaxial", ref="J_FEED",
              value="SMA_feed_to_shack",
                footprint="Connector_Coaxial:SMA_Amphenol_132289_EdgeMount")
j_rxout = Part("/usr/share/kicad/symbols/Connector.kicad_sym", "Conn_Coaxial", ref="J_RXOUT",
               value="SMA_433_RX_out",
               footprint="Connector_Coaxial:SMA_Amphenol_132289_EdgeMount")
j_in2g4 = Part("/usr/share/kicad/symbols/Connector.kicad_sym", "Conn_Coaxial", ref="J_IN2G4",
               value="SMA_2G4_TX_in",
               footprint="Connector_Coaxial:SMA_Amphenol_132289_EdgeMount")
j_ant2g4 = Part("/usr/share/kicad/symbols/Connector.kicad_sym", "Conn_Coaxial", ref="J_ANT2G4",
                value="SMA_2G4_antenna",
                footprint="Connector_Coaxial:SMA_Amphenol_132289_EdgeMount")

rf433_in = Net("RF433_IN")      # antenna side of the BPF
rf433_lna = Net("RF433_LNA")    # LNA output -> limiter
rf433_rx = Net("RF433_RX")      # after limiter/DC-block -> shack RX chain
rf24_in = Net("RF24_TX_IN")
rf24_pad = Net("RF24_PAD")
rf24_out = Net("RF24_TX_OUT")

# ---------------- MASTHEAD: BPF BEFORE LNA (ADR-072 INV-3, normative order) ----------------
bpf = Part("/usr/share/kicad/symbols/Device.kicad_sym", "R", ref="BPF433", value="FBP-433s_class_BPF",
               footprint="RF_Filter:Sawtek_1-1-2_SMD")
# model the BPF as a 2-port through element for the netlist stage
bpf[1] += j_ant433[1], rf433_in           # antenna -> BPF in
bpf[2] += rf433_in                            # BPF out (2-port simplification)

lna = Part("/usr/share/kicad/symbols/Device.kicad_sym", "R", ref="LNA1", value=PART_LNA,
               footprint="Package_TO_SOT_SMD:SOT-89-3")
lna[1] += rf433_in
lna[2] += rf433_lna

limiter = Part("/usr/share/kicad/symbols/Device.kicad_sym", "D_Schottky", ref="D_LIM", value="PIN_RF_limiter_10-20dBm",
               footprint="Package_TO_SOT_SMD:SOT-143")
limiter[1] += rf433_lna
limiter[2] += gnd
if POPULATE_LIMITER:
    lim_out = Net("RF433_LIM_OUT")
    lim_out += rf433_rx          # limiter in series: LNA -> limiter -> feed
else:
    rf433_lna += rf433_rx        # limiter DNP: jumper its pads

# ---------------- SHACK: 433 RX (AGC option DNP) ----------------
dc_block = Part("/usr/share/kicad/symbols/Device.kicad_sym", "C", ref="C_DCBLOCK", value="100pF_DC_block",
             footprint="Capacitor_SMD:C_0402_1005Metric")
dc_block[1] += rf433_rx
dc_block[2] += Net("RF433_SHACK")

if POPULATE_AGC:
    vga = Part("/usr/share/kicad/symbols/Device.kicad_sym", "R", ref="U_VGA", value=PART_VGA,
             footprint="Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.8x1.8mm")
    vga[1] += Net("RF433_SHACK")
    vga_out = Net("RF433_OUT")
    vga[2] += vga_out
    v3v3 += vga[1]  # placeholder power pin (real part: 2-supply, SPI ctrl)
else:
    bypass = Part("/usr/share/kicad/symbols/Device.kicad_sym", "R", ref="R_AGC_BYPASS", value="0R_DNP_will_populate_VGA",
             footprint="Resistor_SMD:R_0402_1005Metric")
    bypass[1] += Net("RF433_SHACK")
    bypass[2] += Net("RF433_OUT")
    # the AGC footprint stays on the board as DNP (pads present)

j_rxout[1] += Net("RF433_OUT")

# ---------------- SHACK: 2.4 GHz TX chain (first-flight populated) ----------------
xr613 = Part("/usr/share/kicad/symbols/Device.kicad_sym", "R", ref="ATT1", value="XR-613_resistive_pad_6dB",
               footprint="RF:ATT_0402")
xr613[1] += rf24_in
j_in2g4[1] += rf24_in
xr613[2] += rf24_pad

dsa = Part("/usr/share/kicad/symbols/Device.kicad_sym", "R", ref="DSA1", value=PART_DSA,
               footprint="Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm")
dsa[1] += rf24_pad
dsa[2] += rf24_out
j_ant2g4[1] += rf24_out

# ---------------- BIAS TEE (powers the masthead LNA over the feed coax) ----------------
bias_inject = Part("/usr/share/kicad/symbols/Device.kicad_sym", "L", ref="L_BIAS", value="1uH_bias_tee_DC_inject",
                 footprint="Inductor_SMD:L_0805_2012Metric")
bias_inject[1] += vin
bias_inject[2] += rf433_rx        # DC onto the feed line centre conductor

# ---------------- PSU ----------------
ldo = Part("/usr/share/kicad/symbols/Regulator_Linear.kicad_sym", "AP2112K-3.3",
           ref="U_PSU", value="AP2112K-3.3_SOT23_600mA",
           footprint="Package_TO_SOT_SMD:SOT-23-5")
ldo[1] += vin      # VI
ldo[2] += gnd      # GND
ldo[3] += v3v3     # VO

# decoupling
for i, rail in ((1, v3v3), (2, vin)):
    c = Part("/usr/share/kicad/symbols/Device.kicad_sym", "C", ref=f"C_DEC{i}",
             value="100nF", footprint="Capacitor_SMD:C_0402_1005Metric")
    c[1] += rail
    c[2] += gnd

# ---------------- grounds ----------------
for j in (j_ant433, j_feed, j_rxout, j_in2g4, j_ant2g4):
    j[2] += gnd

ERC()
generate_netlist(file_="base_station.net")