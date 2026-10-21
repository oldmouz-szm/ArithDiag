# Exact rational conflict-packing certificates

Let every proved conflict e receive weight w_e>=0 with sum_{e contains c} w_e<=1
for each component c. For any hitting set D, sum_e w_e <= sum_{c in D}
sum_{e contains c} w_e <= |D|. Since |D| is an integer, ceil(sum_e w_e)
is a reliable lower bound. The implementation uses denominator 2 and 4, integer
capacities and integer ceilings; no numerical LP bound is trusted. Every original
vertex coverage is constrained; equivalent columns may share an identical
capacity constraint. Different orders produce alternative sound certificates.
This is an incomplete dual-packing heuristic, not a claim to solve the LP.
It is evaluated once per immutable part-engine root and cached only within it.
