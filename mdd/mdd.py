from __future__ import annotations

import math
from collections import defaultdict
from functools import reduce
from typing import Any, Callable, Dict, Generic, Hashable
from typing import Iterable, Sequence, Tuple, Union

import aiger
import aiger_bv as BV
import aiger_bdd
import attr


Assignment = Tuple[Dict[str, Any], Any]
BDD = Any


@attr.s(frozen=True, auto_attribs=True)
class Variable:
    """BDD representation of a multi-valued variable."""
    size: int
    valid: BV.UnsignedBVExpr = attr.ib()
    encode: Callable[[Hashable], int]
    decode: Callable[[int], Hashable]

    @valid.validator
    def check_bitvector_input(self, _, value):
        if len(value.inputs) != 1:
            raise ValueError("valid must be over single bitvector input!")

    @property
    def _name_bundle(self):
        imap = self.valid.aigbv.imap
        (name, bundle), *_ = imap.items()
        return name, bundle

    @property
    def name(self):
        return self._name_bundle[0]

    @property
    def bundle(self):
        return self.valid.aigbv.imap[self.name]

    def with_name(self, name) -> Variable:
        """Create a copy of this Variable with a new name."""
        valid_circ = self.valid.aigbv['i', {self.name: name}]
        return attr.evolve(self, valid=BV.UnsignedBVExpr(valid_circ))

    def expr(self) -> BV.UnsignedBVExpr:
        size = self.bundle.size  # Need encoding size.
        return BV.uatom(size, self.name)


VariableLike = Union[Sequence[Hashable], Variable]


def pow2_exponent(val: int) -> int:
    """Compute exponent of power of 2."""
    count = 0
    while val > 1:
        count += 1
        val >>= 1
    assert val == 1
    return count


def to_bdd(circ_or_expr) -> BDD:
    return aiger_bdd.to_bdd(circ_or_expr, renamer=lambda _, x: x)[0]


def to_var(vals: Iterable[Hashable], name: str) -> Variable:
    """Create BDD representation of a variable taking on values in `vals`."""
    vals = tuple(vals)
    tmp = BV.atom(len(vals), name, signed=True)

    # Create circuit representing classic onehot bit trick.
    one_hot = (tmp != 0) & ((tmp & (tmp - 1)) == 0)
    one_hot = BV.UnsignedBVExpr(one_hot.aigbv)  # Forget about sign.

    return Variable(
        size=len(vals),
        valid=one_hot.with_output("valid"),
        encode=lambda val: 1 << vals.index(val),
        decode=lambda val: vals[pow2_exponent(val)],
    )


@attr.s(frozen=True, auto_attribs=True)
class Interface:
    """Input output interface of Multi-valued Decision Diagram."""
    # TODO: add tuple converter.
    inputs: Sequence[Variable] = attr.ib()
    output: Variable  # Assumed to be 1-hot.

    @inputs.validator
    def check_unique(self, _, value):
        names = [elem.name for elem in value]
        if len(names) != len(set(names)):
            raise ValueError("All input names must be unique!")

    def valid(self) -> BV.UnsignedBVExpr:
        """Circuit testing if input assignment is valid""" 
        valid_tests = (var.valid for var in self.inputs)
        return reduce(lambda x, y: x & y, valid_tests)

    def __call__(self, inputs):
        # TODO:
        # 1. Encode input values.
        # 2. Turn
        inputs = {
            var.name: var.encode(inputs[var.name]) for var in self.inputs
        }
        
        vals = defaultdict(lambda: False)
        for var in self.inputs:
            pass

    def constantly(self, output: Any, manager=None) -> MDD:
        encoded = self.output.encode(output)
        assert self.output.valid({self.output.name: encoded})[0]

        # Create BDD that only depends on hot variable in encoded.
        index = pow2_exponent(encoded)
        expr = self.output.expr()[index]
        return DecisionDiagram(interface=self, bdd=to_bdd(expr))

    def lift(self, vals: ValueLike, manager=None) -> BDD:
        # Assuming BDD object.
        # TODO: check that it's interface is compatible and extend if
        # necessary. 
        # TODO: Make sure no reordering!
        return DecisionDiagram(interface=self, bdd=vals)
        
    def order(self, inputs: Sequence[Union[Variable, str]]):
        """Reorder underlying BDD to respect order seen in inputs.
        
        As a side effect, this function turns off reordering.
        """
        pass


@attr.s(frozen=True, auto_attribs=True)
class DecisionDiagram:
    interface: Interface
    bdd: BDD

    def override(self, test: ValueLike, pos: DD) -> DD:
        # TODO: override current DD value.
        if isinstance(vals, tuple):  # Assuming partial assignment
            inputs, output = vals

            # Create predicate testing if value matches
            expr = aiger.atom(True)
            for var in self.inputs:
                encoded = var.encode(vals[var.name])
                assert var.valid({var.name: encoded})[0]

                size = var.bundle.size  # Need encoding size.
                test = BV.uatom(size, var.name) == BV.uatom(size, encoded)
                expr &= aiger.BoolExpr(test.aig)

            # Create BDD testing for vals.
            vals = aiger_bdd.to_bdd(expr, manager=manager)

        pass


DD = DecisionDiagram
ValueLike = Union[Assignment, BDD]


__all__ = ["DecisionDiagram", "Interface", "Variable", "BDD", "to_var"]
