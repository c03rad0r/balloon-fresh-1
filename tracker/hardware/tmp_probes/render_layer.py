#!/usr/bin/env python3
"""Render ONE copper layer with its own pads: the visual answer to "what layer are the lanes".

Usage: render_layer.py <F|B> <out.png> [x0 y0 x1 y1]
Copper on this layer is drawn; pads that have NO copper on this layer are drawn as thin
grey outlines only -- so a lane passing over them is visibly NOT touching anything.
"""
import sys, pcbnew
from PIL import Image, ImageDraw
UM=1e6
BOARD="/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb"
which=sys.argv[1].upper(); out=sys.argv[2]
crop = [float(x) for x in sys.argv[3:7]] if len(sys.argv)>=7 else None
LAY = pcbnew.F_Cu if which=="F" else pcbnew.B_Cu
COL = (255,140,0) if which=="F" else (0,200,255)
b=pcbnew.LoadBoard(BOARD)
bb=b.GetBoardEdgesBoundingBox()
X0,Y0,W_,H_ = bb.GetX()/UM, bb.GetY()/UM, bb.GetWidth()/UM, bb.GetHeight()/UM
if crop: X0,Y0,x1,y1 = crop; W_,H_ = x1-X0, y1-Y0
S = 15 if not crop else 34
img=Image.new("RGB",(int(W_*S)+130,int(H_*S)+130),(12,12,16))
d=ImageDraw.Draw(img)
def T(x,y): return (65+(x-X0)*S, 65+(y-Y0)*S)
d.rectangle([T(X0,Y0),T(X0+W_,Y0+H_)],outline=(210,210,210),width=2)
# pads: copper on this layer solid, no copper on this layer = grey outline
for fp in b.GetFootprints():
    for p in fp.Pads():
        has = p.GetLayerSet().Contains(LAY)
        r=p.GetBoundingBox()
        rr=[T(r.GetX()/UM, r.GetY()/UM), T((r.GetX()+r.GetWidth())/UM,(r.GetY()+r.GetHeight())/UM)]
        if has:
            net=p.GetNetname() or ""
            fill=(60,60,120) if net else (110,60,60)
            d.rectangle(rr, fill=fill, outline=(230,230,90))
        else:
            d.rectangle(rr, outline=(70,70,70))
# tracks on this layer
for t in b.GetTracks():
    if t.GetLayer()!=LAY: continue
    if "VIA" in str(type(t)):
        c=t.GetPosition(); rad=t.GetWidth()/UM/2
        d.ellipse([T(c.x/UM-rad,c.y/UM-rad),T(c.x/UM+rad,c.y/UM+rad)],fill=(255,255,0))
        continue
    if "TRACK" not in str(type(t)): continue
    w=max(2,int(t.GetWidth()/UM*S))
    d.line([T(t.GetStart().x/UM,t.GetStart().y/UM),T(t.GetEnd().x/UM,t.GetEnd().y/UM)],fill=COL,width=w)
d.text((65,18),"%s.Cu ONLY  (orange/cyan = copper on THIS layer, yellow = pad with copper here, grey outline = NO copper on this layer)" % which,fill=(255,255,255))
d.text((65,40),"%s" % (out.split('/')[-1]),fill=(170,170,170))
if crop: d.text((65,58),"zoom: x %.1f..%.1f  y %.1f..%.1f" % (X0,W_+X0,Y0,H_+Y0),fill=(170,170,170))
img.save(out); print("MARK saved",out)
