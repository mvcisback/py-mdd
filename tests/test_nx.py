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
    assert len(graph) == 4
