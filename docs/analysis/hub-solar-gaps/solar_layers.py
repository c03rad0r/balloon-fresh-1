#!/usr/bin/env python3
"""For each solar-gap pair, list the copper layers each pad actually has.

A gap can only be closed by a TRACK if the two pads share a copper layer. If they
do not, the only board-side options are (a) a via/through-connection at one end,
which must land on a pad that is PTH, or (b) the connection is intended to happen
through the mating tab / harness, not through board copper.

This decides which of the 9 gaps are board-fixable at all.
"""
import json
import re
from collections import Counter

import pcbnew as k

BASE = ('/home/c08r4d0r/worktrees/hub-repair-candidate/docs/analysis/'
        'hub-repair-20261102/output/after/hub_board_v10_lora1280_7of9.kicad_pcb')
CLS = ('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/'
       'unconn-class/classification.json')
CU = ('F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu')


def main():
    b = k.LoadBoard(BASE)
    d = json.load(open(CLS))
    pat = re.compile(r'Pad (\d+) \[([^\]]*)\] of (\w+) on ([\w.]+)')

    def pad(ref, num):
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            return None
        for p in fp.Pads():
            if p.GetNumber() == num:
                return p
        return None

    def layers(p):
        return [l for l in (b.GetLayerName(x) for x in p.GetLayerSet().Seq())
                if l in CU]

    rows = []
    for rec in d['details']:
        if 'D_BP' not in ' '.join(rec['descs']):
            continue
        ms = [pat.search(x) for x in rec['descs']]
        if not all(ms) or len(ms) != 2:
            continue
        (n1, net, r1, l1), (n2, _, r2, l2) = [m.groups() for m in ms]
        p1, p2 = pad(r1, n1), pad(r2, n2)
        if p1 is None or p2 is None:
            rows.append(dict(net=net, a=f'{r1}.{n1}', b=f'{r2}.{n2}',
                             note='pad missing'))
            continue
        L1, L2 = layers(p1), layers(p2)
        shared = sorted(set(L1) & set(L2))
        attr1 = int(p1.GetAttribute())
        attr2 = int(p2.GetAttribute())
        rows.append(dict(
            net=net, a=f'{r1}.{n1}', b=f'{r2}.{n2}',
            a_layers=L1, b_layers=L2, shared=shared,
            a_attr=('PTH' if attr1 == k.PAD_ATTRIB_PTH else
                    'SMD' if attr1 == k.PAD_ATTRIB_SMD else str(attr1)),
            b_attr=('PTH' if attr2 == k.PAD_ATTRIB_PTH else
                    'SMD' if attr2 == k.PAD_ATTRIB_SMD else str(attr2))))
        print(f"{net:14s} {r1}.{n1} {L1} ({rows[-1]['a_attr']})  <->  "
              f"{r2}.{n2} {L2} ({rows[-1]['b_attr']})  shared={shared}")

    fixable = [r for r in rows if r.get('shared')]
    print(f'\npairs sharing a copper layer (track-fixable): {len(fixable)}/{len(rows)}')
    c = Counter(r.get('a_attr', '?') + '/' + r.get('b_attr', '?') for r in rows)
    print('pad type combos:', dict(c))

    json.dump(rows, open('/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/'
                         'unconn-class/solar_layers.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
