from __future__ import annotations

from functools import reduce
from typing import Any, Dict, Optional, Sequence

import aiger_bv as BV
import funcy as fn
import networkx as nx
from aiger_bv.expr import UnsignedBVExpr as BVExpr
from dd.autoref import BDD
from networkx import DiGraph

from mdd import DecisionDiagram, Variable
from mdd.mdd import name_index, to_bdd


def to_nx(func: DecisionDiagram,
          symbolic_edges: bool = True,
          order: Optional[Sequence[str]] = None) -> DiGraph:
    """Returns networkx graph representation of `func` DecisionDiagram.

    Nodes represent decision variables given in order.

    If `symbolic_edges`:
      Edges are annotated by py-aiger guards over variable encoding.
    Else:
      Edges are annotated by a subset of the variable's domain.
    """
    # Force bdd to be ordered by MDD variables.
    if order is None:
        order = [var.name for var in func.interface.inputs]
        order.append(func.interface.output.name)
    func.order(order)

    # DFS construction of graph.
    graph = nx.DiGraph()
    stack, visited = [func.bdd], set()
    while stack:
        curr = stack.pop()
        if curr in visited:
            continue

        visited.add(curr)
        graph.add_node(curr, name=name_index(curr.var)[0])

        name, idx = name_index(curr.var)
        var = func.interface.var(name)
        children = transitions(var, curr).items()

        if not children:
            # Relabel name with output if leaf.
            output = func.interface.output
            assert name == output.name
            graph.nodes[curr]['name'] = output.decode(1 << idx)
            continue

        # Use let to incrementally set variables in var.
        for child, guard in children:
            guard &= var.valid
            stack.append(child)
            graph.add_edge(curr, child, guards=guard)

    # Decouple from BDD.
    graph = nx.convert_node_labels_to_integers(graph)
    return graph if symbolic_edges else concrete_graph(func, graph)


def concrete_graph(func: DecisionDiagram, graph: DiGraph) -> DiGraph:
    for *_, data in graph.edges(data=True):
        guard = data['guards']
        assert isinstance(guard, BVExpr)
        assert len(guard.inputs) == 1
        var = func.interface.var(fn.first(guard.inputs))
        data['guards'] = set(solutions(var, guard))
    return graph


def solutions(var: Variable, guard: BVExpr) -> Any:
    bdd = to_bdd(guard)
    assert bdd != bdd.bdd.true, "BDD not reduced?!"

    for model in bdd.bdd.pick_iter(bdd, care_vars=guard.aig.inputs):
        # BDD doesn't know about bit-vectors.
        # Collect model dictionary into an integer using aiger_bv.
        as_tuple = guard.aigbv.imap[var.name].unblast(model)
        as_int = BV.decode_int(as_tuple, signed=False)

        # Decode int to corresponding variable.
        yield var.decode(as_int)


def transitions(var: Variable,
                curr: BDD,
                prev: Optional[BDD] = None,
                path: BVExpr = BV.uatom(1, 1)) -> Dict[BDD, BVExpr]:
    """Recursively compute transition to next variable."""
    if curr.var is None:
        return {}

    if prev is None:
        prev = curr

    if path is None:
        path = BV.uatom(1, 1)

    name, idx = name_index(prev.var)
    assert name == var.name

    if not curr.var.startswith(name):
        return {curr: path}

    # Recurse and combine guards using ite on current decision bit.
    _, idx = name_index(curr.var)
    bit_test = var.expr()[idx]

    return fn.merge_with(
        lambda guards: reduce(lambda g1, g2: g1 | g2, guards),
        transitions(var, curr.let(**{curr.var: True}), curr, path & bit_test),
        transitions(var, curr.let(**{curr.var: False}), curr, path & ~bit_test),
    )


__all__ = ["to_nx"]
