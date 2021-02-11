from __future__ import annotations

import re
import itertools
import uuid
from functools import reduce
from typing import Any, Callable, Dict, Hashable
from typing import Iterable, Optional, Sequence, Set, Tuple, Union
from typing import FrozenSet

import aiger_bv as BV
import aiger_bdd
import attr
from aiger_bv.bundle import Bundle
from aiger_bv.expr import UnsignedBVExpr
from attr._make import Attribute

try:
    from dd.cudd import BDD
except ImportError:
    from dd.autoref import BDD


Assignment = Tuple[Dict[str, Any], Any]

INDEX_SPLITTER = re.compile(r"(.*)\[(.*)\]")


def name_index(var: str) -> Tuple[str, int]:
    match = INDEX_SPLITTER.match(var)
    assert match is not None
    name, idx_str = match.groups()
    return name, int(idx_str)


@attr.s(frozen=True, auto_attribs=True)
class Variable:
    """BDD representation of a multi-valued variable."""

    valid: BV.UnsignedBVExpr = attr.ib()
    encode: Callable[[Any], int]
    decode: Callable[[int], Any]

    def size(self) -> int:
        """Returns number of values Variable can take on."""
        return aiger_bdd.count(self.valid)

    @valid.validator
    def check_bitvector_input(self, _: Attribute, value: UnsignedBVExpr):
        if len(value.inputs) != 1:
            raise ValueError("valid must be over single bitvector input!")

    @property
    def _name_bundle(self) -> Tuple[str, int]:
        imap = self.valid.aigbv.imap
        (name, bundle), *_ = imap.items()
        return name, bundle

    @property
    def name(self) -> str:
        return self._name_bundle[0]

    @property
    def bundle(self) -> Bundle:
        return self.valid.aigbv.imap[self.name]

    def with_name(self, name: str) -> Variable:
        """Create a copy of this Variable with a new name."""
        if self.name == name:
            return self
        valid_circ = self.valid.aigbv["i", {self.name: name}]
        return attr.evolve(self, valid=BV.UnsignedBVExpr(valid_circ))

    @property
    def _encoding_size(self) -> int:
        return self.bundle.size

    def expr(self) -> BV.UnsignedBVExpr:
        """Returns Aiger BitVector representing this variable."""
        return BV.uatom(self._encoding_size, self.name)


VariableLike = Union[Sequence[Hashable], Variable]


def pow2_exponent(val: int) -> int:
    """Compute exponent of power of 2."""
    count = 0
    while val > 1:
        count += 1
        val >>= 1
    assert val == 1
    return count


def id_renamer(_, x):
    return x


def to_bdd(circ_or_expr, manager: Optional[BDD] = None, levels=None) -> BDD:
    """Convert py-aiger compatible object into a BDD."""
    return aiger_bdd.to_bdd(
        circ_or_expr, manager=manager, renamer=id_renamer, levels=levels,
    )[0]


Domain = Union[Iterable[Any], Variable]


def to_var(domain: Domain, name: Optional[str] = None) -> Variable:
    """Create a named variable taking on values in `domain`.

    Uses a 1-hot encoding of domain, i.e., one variable per
    element. For more efficient encoding consider creating Variable
    directly.

    If `name is None`, then unique name selected when creating
    Variable.
    """
    if isinstance(domain, Variable):
        return domain if (name is None) else domain.with_name(name)
    if name is None:
        name = str(uuid.uuid1())  # Create unique name.

    domain = tuple(domain)
    tmp = BV.atom(len(domain), name, signed=True)

    # Create circuit representing classic onehot bit trick.
    one_hot = (tmp != 0) & ((tmp & (tmp - 1)) == 0)
    one_hot = BV.UnsignedBVExpr(one_hot.aigbv)  # Forget about sign.

    return Variable(
        valid=one_hot.with_output("valid"),
        encode=lambda val: 1 << domain.index(val),
        decode=lambda val: domain[pow2_exponent(val)],
    )


Variables = Dict[str, Variable]


def to_vars(vals: Union[Iterable[Variable], Dict[str, Domain]]) -> Variables:
    if isinstance(vals, dict):
        vals = (to_var(name=key, domain=value) for key, value in vals.items())
    return {var.name: var for var in vals}


@attr.s(frozen=True, auto_attribs=True)
class Interface:
    """Input output interface of Multi-valued Decision Diagram."""

    _inputs: Variables = attr.ib(converter=to_vars)
    output: Variable = attr.ib(converter=to_var)
    applied: FrozenSet[str] = frozenset()
    _valid: Optional[UnsignedBVExpr] = attr.ib(default=None)

    @_valid.validator
    def check_interface(self, _, value):
        if value is None:
            return
        if not (value.inputs <= set(self._inputs.keys())):
            raise ValueError("valid circ incompatible with interface.")

    def __attrs_post_init__(self):
        names = self._names()
        if len(names) != len(set(names)):
            raise ValueError("All input names must be unique!")

    def _names(self):
        return list(self._inputs.keys()) + [self.output.name]

    @property
    def inputs(self) -> Iterable[Variable]:
        return [var for var in self._inputs.values()]

    def valid(self) -> BV.UnsignedBVExpr:
        """Circuit testing if input assignment is valid."""
        valid_tests = (var.valid for var in self.inputs)
        if self._valid is not None:
            valid_tests = itertools.chain([self._valid], valid_tests)
        expr = reduce(lambda x, y: x & y, valid_tests)
        sink = BV.sink(self.output._encoding_size, [self.output.name])
        return BV.UnsignedBVExpr(expr.aigbv | sink)  # Adds don't care inputs.

    def constantly(self, output: Any, manager: Optional[BDD] = None) -> MDD:
        """Return MDD returns `output` for any input."""
        encoded = self.output.encode(output)
        assert self.output.valid({self.output.name: encoded})[0]

        # Create BDD that tests valid inputs + value of hot index.
        index = pow2_exponent(encoded)  # hot index.
        expr = self.output.expr()[index] & self.valid()
        bdd = to_bdd(expr, manager=manager)
        return DecisionDiagram(interface=self, bdd=bdd)

    def _levels(self, var_names: Optional[Sequence[str]] = None):
        """Create BDD levels from ordered sequence of variable names."""
        if var_names is None:
            return None

        levels: Dict[str, int] = {}
        for name in var_names:
            offset = len(levels)

            var = self._inputs.get(name, self.output)
            assert var.name == name, "Name doesn't match input or output."

            size = var._encoding_size
            levels.update(var.bundle.blast(range(offset, offset + size)))
        return levels

    def lift(self, bdd_or_aig, manager=None, order=None) -> MDD:
        """Wrap bdd or py-aiger object using this interface.

        Note: Output is assumed to be 1-hot encoded!
        """
        lvls = self._levels(order)
        if hasattr(bdd_or_aig, "aig"):
            bdd_or_aig = to_bdd(bdd_or_aig, manager=manager, levels=lvls)
        bdd_or_aig &= to_bdd(self.valid(), manager=bdd_or_aig.bdd, levels=lvls)

        return DecisionDiagram(interface=self, bdd=bdd_or_aig)

    def var(self, name: str) -> Variable:
        """Get `Variable` for `name` in this interface."""
        return self._inputs.get(name, self.output)


@attr.s(frozen=True, auto_attribs=True)
class DecisionDiagram:
    interface: Interface
    bdd: BDD

    @property
    def io(self) -> Interface:
        """Alias for interface property."""
        return self.interface

    def __attrs_post_init__(self):
        """Check that bdd conforms to interface."""
        bdd_vars: Set[str] = set(self.bdd.bdd.vars)
        interface_vars: Set[str] = set()

        io = self.interface
        for var in itertools.chain(io.inputs, [io.output]):
            interface_vars |= set(var.bundle)

        if bdd_vars != interface_vars:
            diff = bdd_vars.symmetric_difference(interface_vars)
            raise ValueError(
                "Input AIG or BDD does not agree with this"
                f"interface.\n symmetric difference={diff}"
            )

    def let(self, inputs: Dict[str, Any]) -> MDD:
        """Return MDD where subset of inputs have been applied."""
        vals: Dict[str, bool] = {}
        for name, value in inputs.items():
            var = self.io.var(name)
            encoded = var.encode(value)
            assert var.valid({var.name: encoded})[0]

            # Turn bitvector into individual assignments.
            bundle = var.bundle
            encoded = BV.encode_int(bundle.size, encoded, signed=False)
            vals.update(bundle.blast(encoded))

        bdd = self.bdd.let(**vals)
        assert bdd.bdd.false != bdd, "Inputs violated self.interface.valid."

        io2 = attr.evolve(self.io, applied=self.io.applied | set(inputs))
        return attr.evolve(self, bdd=bdd, interface=io2)

    def __call__(self, inputs: Dict[str, Any]) -> Any:
        """Evaluate MDD on inputs."""
        bdd = self.let(inputs).bdd
        assert bdd.dag_size == 2, "Result should be single variable BDD."

        # Return which decision this was.
        name, idx = name_index(bdd.var)

        output_var = self.io.output
        assert name == output_var.name
        assert 0 <= idx < output_var._encoding_size
        return output_var.decode(1 << idx)

    def order(self, var_names: Optional[Sequence[str]] = None):
        """Reorder underlying BDD to respect order seen in var_names.

        If var_names is None, then order is set `self.interface.inputs`'s
        order followed by `self.interface.output`.

        As a side effect, this function turns off reordering.
        """
        if var_names is None:
            var_names = [var.name for var in self.io.inputs]
            var_names.append(self.io.output.name)

        levels = self.io._levels(var_names)
        assert len(levels) == len(self.bdd.bdd.vars)
        self.bdd.bdd.reorder(levels)
        self.bdd.bdd.configure(reordering=False)

    def override(self, test, value: Union[Any, MDD]) -> MDD:
        """Return MDD where `value if test else self`.

        Args:
          test: Can be a BDD or and py-aiger compatible object.
          value: Either an element of co-domain or another compatible
                 MDD.
        """
        manager = self.bdd.bdd
        if not isinstance(value, DecisionDiagram):
            value = self.io.constantly(value, manager=manager).bdd

        if hasattr(test, "aig"):
            test = to_bdd(test, manager=manager)

        # Assuming test and value are BDDs now.
        #         test => value    ~test => self.bdd.
        bdd = ((~test) | value) & (test | self.bdd)
        return attr.evolve(self, bdd=bdd)


MDD = DecisionDiagram


__all__ = ["DecisionDiagram", "Interface", "Variable", "to_var", "to_bdd"]
