import json
from collections import defaultdict

dag = json.load(open("data/dag.json"))
N = dag["nodes"]
E = dag["edges"]

childMap = {}
for e in E:
    childMap.setdefault(e["source"], []).append(e["target"])

hasParent = set(e["target"] for e in E)
roots = [nid for nid in N if nid not in hasParent]

order = {nid: 0 for nid in N}
for _ in range(20):
    changed = False
    for e in E:
        s, t = e["source"], e["target"]
        if s in order and t in order:
            nd = order[s] + 1
            if nd > order[t]:
                order[t] = nd
                changed = True
    if not changed:
        break

layers = defaultdict(list)
for nid, o in order.items():
    layers[o].append(nid)

for o in sorted(layers.keys()):
    print(f"=== {o}阶 ({len(layers[o])}) ===")
    for nid in sorted(layers[o], key=lambda x: -N[x]["probability"]):
        n = N[nid]
        print(f'  {n["probability"]:.0%} {n["label"][:40]}')
    print()

print(f"Roots: {[N[r]['label'][:20] for r in roots]}")
