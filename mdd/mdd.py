from typing import Any, Callable, Dict, Generic, Hashable, Sequence, Union

import attr


Assignment = Dict[Hashable, bool]
BDD = Any


@attr.s(frozen=True, auto_attribs=True)
class Variable:
    name: Hashable
    valid: BDD
    encode: Callable[[Hashable], Assignment]
    decode: Callable[[Assignment], Hashable]


VariableLike = Union[Sequence[Hashable], Variable]


def to_var(vals: VariableLike) -> Variable:
    pass



@attr.s(frozen=True, auto_attribs=True)
class Interface:
    inputs: Sequence[Variable]
    output: Variable

    def lift(self, val: ValueLike) -> MDD:
        pass

    def ite(self, test: ValueLike, pos: MDD, neg: MDD) -> MDD:
        pass


@attr.s(frozen=True, auto_attribs=True)
class MDD:
    interface: Interface
    bdd: BDD


ValueLike = Union[Assignment, BDD, MDD]


__all__ = ["MDD", "Interface", "Variable", "BDD"]
