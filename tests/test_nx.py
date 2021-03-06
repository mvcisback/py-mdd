import aiger_bv as BV

import mdd
from mdd.nx import to_nx


def test_to_nx():
    interface = mdd.Interface(
        inputs={"x": [1, 2, 3, 4, 5], "y": ['a', 'b']},
        output=[-1, 0, 1]
    )

    test = interface.var('x').expr()[0] & interface.var('y').expr()[0]
    output = interface.output.expr()
    expr = BV.ite(test, output[1], output[-1])
    func = interface.lift(expr)

    graph = to_nx(func)
    assert len(graph) == 5  # TODO: should be 4 for reduced graph.

    graph2 = to_nx(func, symbolic_edges=False)
    assert len(graph) == len(graph2)
    assert graph2.edges

    guards = (data['label'] for *_, data in graph2.edges(data=True))
    edge_vals = set(map(frozenset, guards))
    assert edge_vals == {
        frozenset({'a'}),
        frozenset({'b'}),
        frozenset({'a', 'b'}),  # TODO: should not appear in reduced graph.
        frozenset({1}),
        frozenset({2, 3, 4, 5}),
    }

    graph3 = to_nx(func, reindex=False)
    assert len(graph3) == len(graph2)
