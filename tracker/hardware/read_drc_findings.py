"""Read the fab_grade DRC JSON directly -- the grader, not my arithmetic.

Rule 2: when arithmetic and a grader disagree, the grader is right. So read the grader's own fields.

Investigates two findings from the fab_grade run that nothing else has explained:
  via_dangling 8      -- dangling vias usually mean rip-up debris; they are also 8 holes in the copper
  holes_co_located 2  -- two drill holes at the SAME coordinate
and confirms the 4 unconnected items by NAME rather than by count.
"""
import collections
import json
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else \
    "tracker/hardware/output/fabgrade_exittest/hub_board_v9_drc.json"

d = json.load(open(PATH))
print(f"report: {PATH}")
print(f"keys   : {sorted(d.keys())}\n")

v = d.get("violations", [])
u = d.get("unconnected_items", [])

print(f"=== UNCONNECTED ITEMS: {len(u)} ===")
for item in u:
    desc = item.get("description", "")
    items = item.get("items", [])
    nets = {i.get("net") for i in items if i.get("net")}
    print(f"  {desc}")
    for i in items:
        print(f"      {i.get('description')}  pos={i.get('pos')}  layer={i.get('layer')}")
    if nets:
        print(f"      nets involved: {sorted(nets)}")
print()

print(f"=== VIOLATIONS BY TYPE: {len(v)} ===")
by = collections.defaultdict(list)
for x in v:
    by[x.get("type")].append(x)
for t, xs in sorted(by.items(), key=lambda kv: -len(kv[1])):
    sev = collections.Counter(x.get("severity") for x in xs)
    print(f"  {t:28} {len(xs):4}   {dict(sev)}")

for want in ("via_dangling", "holes_co_located", "copper_edge_clearance", "lib_footprint_issues"):
    xs = by.get(want, [])
    if not xs:
        continue
    print(f"\n=== {want}: {len(xs)} ===")
    for x in xs[:6]:
        print(f"  {x.get('description')}")
        for i in x.get("items", []):
            print(f"      {i.get('description')}  pos={i.get('pos')}")
    if len(xs) > 6:
        print(f"  ... and {len(xs) - 6} more")
