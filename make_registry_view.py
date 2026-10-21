import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
lines = open("/home/c08r4d0r/worktrees/master-check/tracker/hardware/connectivity/v10_pinmap.reg").read().splitlines()
# show the interesting blocks: U3, U_C, U_E28, and the UNASSIGNED summary
keep, block = [], None
for ln in lines:
    if ln.startswith("# --- "):
        block = ln
        if any(k in ln for k in ("U3 ", "U_C ", "U_E28 ", "U1 ", "ANT")):
            keep.append(ln)
        else:
            block = None
        continue
    if block and ln.strip() and not ln.startswith("#"):
        keep.append(ln)
    if "UNASSIGNED pins on this board" in ln:
        keep.append("")
        keep.append(ln[:150] + ("..." if len(ln) > 150 else ""))
txt = "\n".join(keep[:46])
fig = plt.figure(figsize=(11, 12), dpi=150)
fig.patch.set_facecolor("#0d1117")
fig.text(0.02, 0.975, "v10 connectivity registry  tracker/hardware/connectivity/v10_pinmap.reg",
         color="#58a6ff", fontsize=12, weight="bold", family="monospace")
fig.text(0.02, 0.952, "195 pins, one line each, in git. Authority column names the deciding ADR.",
         color="#8b949e", fontsize=9, family="monospace")
fig.text(0.02, 0.03, txt, color="#c9d1d9", fontsize=7.4, family="monospace", va="bottom")
plt.axis("off")
plt.savefig("/tmp/v10gate/registry.png", facecolor="#0d1117")
print("MARK saved registry.png")
