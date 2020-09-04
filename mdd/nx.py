from typing import Optional, Sequence

import networkx as nx
from networkx import DiGraph

import mdd
from mdd import DecisionDiagram, Variable


def to_nx(func: DecisionDiagram, 
          symbolic_edges: bool=True,
          order: Optional[Sequence, Variable]=None) -> DiGraph:
    """Returns networkx graph representation of `func` DecisionDiagram.

    Nodes represent decision variables given in order.

    If `symbolic_edges`:
      Edges are annotated by py-aiger guard over variable encoding.
    Else:
      Edges are annotated by a subset of the variable's domain.
    """
    graph = nx.DiGraph()
    root = func.bdd
