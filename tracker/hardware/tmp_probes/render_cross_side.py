#!/usr/bin/env python3
"""Render the cross-side collision: front parts on top, back parts on top of them.
Shows why U1 and U_E28 cannot coexist: they occupy the same board area.
Usage: render_cross_side.py <out.png>
"""
import sys, pcbnew
from PIL import Image, ImageDraw
UM=1e6
BOARD="/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb"
out = sys.argv[1]
b = pcbnew.LoadBoard(BOARD)
bb = b.GetBoardEdgesBoundingBox()
X0,Y0 = bb.GetX()/UM, bb.GetY()/UM
W_,H_ = bb.GetWidth()/UM, bb.GetHeight()/UM
S = 14
img = Image.new("RGB", (int(W_*S)+120, int(H_*S)+120), (14,14,18))
d = ImageDraw.Draw(img)
def T(x,y): return (60+(x-X0)*S, 60+(y-Y0)*S)
# board
d.rectangle([T(X0,Y0), T(X0+W_,Y0+H_)], outline=(200,200,200), width=3)
front=[]; back=[]
for fp in b.GetFootprints():
    ref=fp.GetReference()
    if ref.startswith(("H1","H2","H3","H4","HW")): continue
    r=fp.GetBoundingBox(False,True)
    rect=(r.GetX()/UM, r.GetY()/UM, (r.GetX()+r.GetWidth())/UM, (r.GetY()+r.GetHeight())/UM)
    (front if fp.GetLayerName()=="F.Cu" else back).append((ref,rect))
for ref,(x0,y0,x1,y1) in front:
    d.rectangle([T(x0,y0),T(x1,y1)], outline=(255,150,40), width=2)
    d.text((T(x0,y0)[0]+4, T(x0,y0)[1]+4), ref, fill=(255,180,90))
for ref,(x0,y0,x1,y1) in back:
    d.rectangle([T(x0,y0),T(x1,y1)], outline=(60,220,120), width=2)
    d.text((T(x0,y0)[0]+4, T(x1,y1)[1]-16), ref, fill=(120,255,160))
# highlight the U1/E28 collision
for ref in ("U1","U_E28"):
    fp=b.FindFootprintByReference(ref)
    r=fp.GetBoundingBox(False,True)
    rect=(r.GetX()/UM, r.GetY()/UM, (r.GetX()+r.GetWidth())/UM, (r.GetY()+r.GetHeight())/UM)
    ox0=max(rect[0], 10.03); oy0=max(rect[1], 32.42)
    ox1=min(rect[2], 27.23); oy1=min(rect[3], 47.58)
    if ox1>ox0 and oy1>oy0:
        d.rectangle([T(ox0,oy0),T(ox1,oy1)], fill=(255,0,0))
d.text((60, 20), "RED = area where a FRONT part and a BACK part occupy the same board space", fill=(255,80,80))
d.text((60, 38), "orange = front parts    green = back parts", fill=(200,200,200))
img.save(out)
print("MARK saved", out)
