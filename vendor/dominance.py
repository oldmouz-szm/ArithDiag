"""Conservative component dominance over whole-signal dependency graph.

For weak faults and total combinational component functions, replacing any
fault in a cone by its dominating component preserves feasibility with no larger
cardinality. Whole-signal dependencies overapproximate bit dependencies, hence
only lose reductions. Dominance is used ONLY to find/prove the minimum; all
original component AB patterns are restored for projected enumeration.
"""
from functools import lru_cache
from iqcqp_model import circuit_wiring
def top_level_search_components(model, group):
    edges={}
    def edge(a,b):
        edges.setdefault(a,set()).add(b)
        edges.setdefault(b,set())
    def refs(e):
        return [p["ref"]["signal"] for p in e["parts"] if p["ref"]]
    sink="@OBS"
    for p in model["ports"]:
        if p["direction"]=="output": edge("s:"+p["name"],sink)
    for c in circuit_wiring(model):
        for src in refs(c["source"]): edge("s:"+src,"s:"+c["target"]["signal"])
    for c in model["components"]:
        node="c:"+c["name"]
        for src in refs(c["a"])+refs(c["b"]): edge("s:"+src,node)
        edge(node,"s:"+c["output"]["signal"])
    active=set()
    @lru_cache(maxsize=None)
    def dom(node):
        if node==sink: return frozenset()
        if node in active: raise ValueError("Whole-signal dependency cycle")
        active.add(node)
        children=[dom(n) for n in edges.get(node,())]
        active.remove(node)
        reachable=[x for x in children if x is not None]
        if not reachable: return None
        shared=set(reachable[0])
        for x in reachable[1:]: shared.intersection_update(x)
        if node.startswith("c:"): shared.add(node[2:])
        return frozenset(shared)
    result={}
    group_names=set(group["components"])
    try:
        for c in group["components"]:
            ds=dom("c:"+c)
            other=sorted((set(ds or ())-{c}) & group_names)
            if other: result[c]=other
    except ValueError:
        return {}
    return result
