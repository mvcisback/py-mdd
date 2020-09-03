import aiger_bv as BV

import mdd


def test_to_var():
    var = mdd.to_var(domain=["x", "y", "z"], name="myvar")
    assert var.name == "myvar"
    assert var.size() == 3

    assert var.encode("x") == 0b001
    assert var.encode("y") == 0b010
    assert var.encode("z") == 0b100

    assert var.decode(0b100) == 'z'
    assert var.decode(0b010) == 'y'
    assert var.decode(0b001) == 'x'

    # Test valid circuit checks onehot.

    valid_input = {'myvar': (True, False, False)}
    invalid_input = {'myvar': (True, True, False)}
    assert var.valid(valid_input)[0]
    assert not var.valid(invalid_input)[0]

    var2 = var.with_name("bar")
    assert var.name == "myvar"
    assert var2.name == "bar"


def test_interface():
    var1 = mdd.to_var(domain=["x", "y", "z"], name="myvar1")
    var2 = var1.with_name("myvar2")
    var3 = var1.with_name("myvar3")

    interface = mdd.Interface(inputs=[var1, var2, var3], output={1, 2, 3})

    # Check that interface can test domain.
    valid = interface.valid()
    assert valid({'myvar1': 0b100, 'myvar2': 0b100, 'myvar3': 0b100})[0]
    assert not valid({'myvar1': 0b000, 'myvar2': 0b100, 'myvar3': 0b100})[0]

    func = interface.constantly(2)
    result = func({'myvar1': 'x', 'myvar2': 'x', 'myvar3': 'x'})
    assert result == 2


def test_lift():
    interface = mdd.Interface(
        inputs={
            "x": [1, 2, 3],
            "y": [6, 4, 5],
            "z": [7, 9, 8],
        },
        output=[-1, 0, 1]
    )

    x, y, z = [var.expr() for var in interface.inputs]
    out = interface.output.expr()

    # If all all the inputs have the same encoding,
    # then output -1, otherwise output 1.

    all_equal = (x == y) & (y == z)

    # Due to one hot output encoding, we have:
    #                          -1       1
    expr = BV.ite(all_equal, out[0], out[1])
    func = interface.lift(expr)

    assert func({'x': 1, 'y': 6, 'z': 7}) == -1
    assert func({'x': 2, 'y': 6, 'z': 7}) == 0


def test_order():
    interface = mdd.Interface(
        inputs={
            "x": [1, 2, 3],
            "y": [6, 5],
            "z": [7, 9, 8],
        },
        output=[-1, 0],
    )
    func = interface.constantly(-1)
    func.order(['y', 'x', 'z', interface.output.name])

    assert func.bdd.bdd.vars == {
        "y[0]": 0,
        "y[1]": 1,
        "x[0]": 2,
        "x[1]": 3,
        "x[2]": 4,
        "z[0]": 5,
        "z[1]": 6,
        "z[2]": 7,
        f"{interface.output.name}[0]": 8,
        f"{interface.output.name}[1]": 9,
    }


def test_override():
    interface = mdd.Interface(
        inputs={
            "x": [1, 2, 3],
            "y": [6, 5],
            "z": [7, 9, 8],
        },
        output=[-1, 0],
    )
    x = interface.var('x')

    func = interface.constantly(-1)
    test = x.expr() == x.encode(2)
    func2 = func.override(test=test, value=0)
    assert func2({'x': 2, 'y': 6, 'z': 9}) == 0


def test_partial():
    interface = mdd.Interface(
        inputs={
            "x": [1, 2, 3],
            "y": [6, 5],
            "z": [7, 9, 8],
        },
        output=[-1, 0],
    )

    func = interface.constantly(-1)
    func2 = func.let({'x': 2})
    assert isinstance(func2, mdd.DecisionDiagram)
    assert func2({'y': 6, 'z': 9}) == -1
