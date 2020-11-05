from __future__ import annotations

from functools import reduce
from typing import Any, Dict, Optional, Sequence

import aiger_bv as BV
import bdd2dfa
import funcy as fn
import networkx as nx
from aiger_bv.expr import UnsignedBVExpr as BVExpr
from bdd2dfa.b2d import BNode
from networkx import DiGraph

from mdd import DecisionDiagram, Variable
from mdd.mdd import name_index, to_bdd


def to_nx(func: DecisionDiagram,
          symbolic_edges: bool = True,
          order: Optional[Sequence[str]] = None,
          reindex: bool = True) -> DiGraph:
    """Returns networkx graph representation of `func` DecisionDiagram.

    Nodes represent decision variables given in order. The variable is
    accessible using the 'label' key.

    If `symbolic_edges`:
      Edges are annotated by py-aiger guards over variable encoding.
    Else:
      Edges are annotated by a subset of the variable's domain.

    The inputs the edge represents are accessable via the 'label' key.
    """
    # Force bdd to be ordered by MDD variables.
    func.order(order)

    # Use bit-dfa to hide some of dd's internal details.
    start = bdd2dfa.to_dfa(func.bdd, qdd=False).start

    # DFS construction of graph.
    graph = nx.DiGraph()
    stack, visited = [start], set()
    while stack:
        curr = stack.pop()
        if curr in visited:
            continue

        visited.add(curr)
        graph.add_node(curr, label=name_index(curr.node.var)[0])

        name, idx = name_index(curr.node.var)
        var = func.interface.var(name)
        children = transitions(var, curr).items()

        if not children:
            # Relabel name with output if leaf.
            output = func.interface.output
            assert name == output.name
            graph.nodes[curr]['label'] = output.decode(1 << idx)
            continue

        # Use let to incrementally set variables in var.
        for child, guard in children:
            stack.append(child)
            graph.add_edge(curr, child, label=guard)

    if reindex:  # Decouple from BDD.
        graph = nx.convert_node_labels_to_integers(graph)
    return graph if symbolic_edges else concrete_graph(func, graph)


def concrete_graph(func: DecisionDiagram, graph: DiGraph) -> DiGraph:
    for *_, data in graph.edges(data=True):
        guard = data['label']
        assert isinstance(guard, BVExpr)
        assert len(guard.inputs) == 1
        var = func.interface.var(fn.first(guard.inputs))
        data['label'] = set(solutions(var, guard))
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


def merge_guards(guards):
    return reduce(lambda x, y: x | y, guards)


def transitions(var: Variable, curr: BNode) -> Dict[BNode, BVExpr]:
    """Recursively compute transition to next variable."""
    if curr.node.var is None:
        return {}

    if not curr.node.var.startswith(var.name):
        return {curr: BV.uatom(1, 1)}

    # Recurse and combine guards using ite on current decision bit.
    _, idx = name_index(curr.node.var)
    bit = var.expr()[idx]

    factors = {
        0: transitions(var, curr.transition(False)),
        1: transitions(var, curr.transition(True)),
    }
    for decision, factor in factors.items():
        test = bit if decision else ~bit
        for node in factor:
            factor[node] = test & factor[node]

    return fn.join_with(merge_guards, factors.values())


__all__ = ["to_nx"]
