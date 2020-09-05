from __future__ import annotations

from typing import Dict, Optional, Sequence

import aiger_bv as BV
import funcy as fn
import networkx as nx
from aiger_bv.expr import UnsignedBVExpr as BVExpr
from dd.autoref import BDD
from networkx import DiGraph

import mdd
from mdd import DecisionDiagram, Variable
from mdd.mdd import name_index


def to_nx(func: DecisionDiagram, 
          symbolic_edges: bool=True,
          order: Optional[Sequence[str]]=None) -> DiGraph:
    """Returns networkx graph representation of `func` DecisionDiagram.

    Nodes represent decision variables given in order.

    If `symbolic_edges`:
      Edges are annotated by py-aiger guard over variable encoding.
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
        visited.add(curr)
        
        name, _ = name_index(curr.var)
        var = func.interface.var(name)

        # Use let to incrementally set variables in var.
        for child, guard in transitions(var, curr).items():
            if child not in visited:
                stack.append(child)
                graph.add_node(child, name=name_index(child.var)[0])

            graph.add_edge(curr, child, guard=guard)
    return graph


def transitions(var: Variable, curr: BDD, prev: BDD=None) -> Dict[BDD, BVExpr]:
    if curr.var is None:
        return {}

    if prev is None:
        prev = curr

    name, idx = name_index(prev.var)
    assert name == var.name

    if not curr.var.startswith(name):
        return { curr: var.expr()[idx] }

    # Recurse and combine guards using ite on current decision bit.
    _, idx = name_index(curr.var)
    bit_test = var.expr()[idx]

    def merge_guards(guards):
        if len(guards) == 1:
            return guards
        return BV.ite(bit_test, guards[0], guards[1])

    return fn.merge_with(
        merge_guards,
        transitions(var, curr.let(**{curr.var: True}), curr),
        transitions(var, curr.let(**{curr.var: False}), curr)
    )


__all__ = ["to_nx"]
