import mdd


def test_to_var():
    var = mdd.to_var(vals=["x", "y", "z"], name="myvar")
    assert var.name == "myvar"
    assert var.size == 3

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
    var = mdd.to_var(vals=["x", "y", "z"], name="myvar")
    
