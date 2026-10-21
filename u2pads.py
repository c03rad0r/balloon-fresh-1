import pcbnew
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
UM = 1e6
print("MARK === U2 (F33) pads: pos + size ===")
u2 = b.FindFootprintByReference("U2")
fp_bb = u2.GetBoundingBox(False, True)
print(f"MARK U2 body/courtyard: x {fp_bb.GetX()/UM:.2f}..{(fp_bb.GetX()+fp_bb.GetWidth())/UM:.2f} "
      f"y {fp_bb.GetY()/UM:.2f}..{(fp_bb.GetY()+fp_bb.GetHeight())/UM:.2f}")
for p in sorted(u2.Pads(), key=lambda q: (q.GetPosition().y, q.GetPosition().x)):
    pos = p.GetPosition(); s = p.GetSize()
    n = p.GetNet()
    print(f"MARK U2.{p.GetNumber():>2} ({pos.x/UM:6.2f},{pos.y/UM:6.2f}) size {s.x/UM:.2f}x{s.y/UM:.2f} "
          f"net {n.GetNetname() if n else 'NC'}")
print("MARK === U1 pads near the F33_IRQ arrival (x 13..18, y 50..53) ===")
u1 = b.FindFootprintByReference("U1")
for p in u1.Pads():
    pos = p.GetPosition()
    if 13 <= pos.x/UM <= 18 and 50 <= pos.y/UM <= 53:
        n = p.GetNet(); s = p.GetSize()
        print(f"MARK U1.{p.GetNumber():>2} ({pos.x/UM:6.2f},{pos.y/UM:6.2f}) size {s.x/UM:.2f}x{s.y/UM:.2f} net {n.GetNetname() if n else 'NC'}")
