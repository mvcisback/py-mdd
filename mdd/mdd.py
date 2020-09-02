from __future__ import annotations

import math
from typing import Any, Callable, Dict, Generic, Hashable
from typing import Iterable, Sequence, Union

import aiger
import aiger_bv
import aiger_bdd
import attr


Assignment = Dict[Hashable, bool]
BDD = Any


@attr.s(frozen=True, auto_attribs=True)
class Variable:
    """BDD representation of a multi-valued variable."""
    size: int
    valid: aiger_bv.SignedBVExpr
    encode: Callable[[Hashable], int]
    decode: Callable[[int], Hashable]


    @property
    def _name_bundle(self):
        imap = self.valid.aigbv.imap
        (name, bundle), *_ = imap.items()
        assert not _, "Variables must be over single bitvector."
        return name, bundle

    @property
    def name(self):
        return self._name_bundle[0]

    @property
    def bundle(self):
        return self._name_bundle[1]

    def with_name(self, name) -> Variable:
        """Create a copy of this Variable with a new name."""
        valid_circ = self.valid.aigbv['i', {self.name: name}]
        return attr.evolve(self, valid=aiger_bv.SignedBVExpr(valid_circ))


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
    tmp = aiger_bv.atom(len(vals), name, signed=True)

    # Create circuit representing classic onehot bit trick.
    one_hot = (tmp != 0) & ((tmp & (tmp - 1)) == 0)

    return Variable(
        size=len(vals),
        valid=one_hot.with_output("valid"),
        encode=lambda val: 1 << vals.index(val),
        decode=lambda val: vals[pow2_exponent(val)],
    )


@attr.s(frozen=True, auto_attribs=True)
class Interface:
    """Input output interface of Multi-valued Decision Diagram."""
    inputs: Sequence[Variable]
    output: Variable

    def lift(self, val: ValueLike) -> MDD:
        if isinstance(val, dict):
            # TODO: create constant bdd
            # Fall through to BDD object extension.
            pass

        # Assuming BDD object.
        # TODO: check that it's interface is compatible and extend if
        # necessary. 
        # TODO: Make sure no reordering!
        return MDD(interface=self, bdd=val)
        
    def ite(self, test: ValueLike, pos: MDD, neg: MDD) -> MDD:
        pass

    def order(self, inputs: Sequence[Union[Variable, str]]):
        """Reorder underlying BDD to respect order seen in inputs.
        
        As a side effect, this function turns off reordering.
        """
        pass


@attr.s(frozen=True, auto_attribs=True)
class MDD:
    interface: Interface
    bdd: BDD


ValueLike = Union[Assignment, BDD]


__all__ = ["MDD", "Interface", "Variable", "BDD", "to_var"]
