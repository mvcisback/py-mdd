from __future__ import annotations

import math
import re
import itertools
import uuid
from functools import reduce
from typing import Any, Callable, Dict, Generic, Hashable
from typing import Iterable, Optional, Sequence, Tuple, Union

import aiger
import aiger_bv as BV
import aiger_bdd
import attr


Assignment = Tuple[Dict[str, Any], Any]
BDD = Any

INDEX_SPLITTER = re.compile(r"(.*)\[(.*)\]")


@attr.s(frozen=True, auto_attribs=True)
class Variable:
    """BDD representation of a multi-valued variable."""
    valid: BV.UnsignedBVExpr = attr.ib()
    encode: Callable[[Hashable], int]
    decode: Callable[[int], Hashable]

    def size(self) -> int:
        """Returns number of values Variable can take on."""
        return aiger_bdd.count(self.valid)

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

    @property
    def _encoding_size(self) -> int:
        return self.bundle.size

    def expr(self) -> BV.UnsignedBVExpr:
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


def to_bdd(circ_or_expr) -> BDD:
    return aiger_bdd.to_bdd(circ_or_expr, renamer=lambda _, x: x)[0]


Domain = Union[Iterable[Any], Variable]


def to_var(domain: Domain, name: Optional[str]=None) -> Variable:
    """Create BDD representation of a variable taking on values in `domain`."""
    if name is None:
        name = str(uuid.uuid1())  # Create unique name.

    if isinstance(domain, Variable):
        return domain.with_name(name)  # Just rename.

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


Variables = Sequence[Variable]


def to_vars(vals: Union[Iterable[Variable], Dict[str, Domain]]) -> Variables:
    if isinstance(vals, dict):
        vals = (to_var(name=key, domain=value) for key, value in vals.items())
    return tuple(vals)


@attr.s(frozen=True, auto_attribs=True)
class Interface:
    """Input output interface of Multi-valued Decision Diagram."""
    inputs: Variables = attr.ib(converter=to_vars)
    output: Variable = attr.ib(converter=to_var)

    @inputs.validator
    def check_unique(self, _, value):
        names = [elem.name for elem in value]
        if len(names) != len(set(names)):
            raise ValueError("All input names must be unique!")

    def valid(self) -> BV.UnsignedBVExpr:
        """Circuit testing if input assignment is valid""" 
        valid_tests = (var.valid for var in self.inputs)
        return reduce(lambda x, y: x & y, valid_tests)

    def constantly(self, output: Any, manager=None) -> DD:
        encoded = self.output.encode(output)
        assert self.output.valid({self.output.name: encoded})[0]

        # Create BDD that only depends on hot variable in encoded.
        index = pow2_exponent(encoded)
        expr = self.output.expr()[index] & self.valid()
        return DecisionDiagram(interface=self, bdd=to_bdd(expr))

    def lift(self, bdd_or_aig, manager=None) -> DD:
        if hasattr(bdd_or_aig, "aig"):
            bdd = to_bdd(bdd_or_aig)

        bdd_vars = set(bdd.bdd.vars)
        interface_vars = set()
        for var in itertools.chain(self.inputs, [self.output]):
            interface_vars |= set(var.bundle)

        if bdd_vars != interface_vars:
            diff = bdd_vars.symmetric_difference(interface_vars)
            raise ValueError("Input AIG or BDD does not agree with this"
                             f"interface.\n symmetric difference={diff}")

        return DecisionDiagram(interface=self, bdd=bdd)
        
    def order(self, inputs: Sequence[Union[Variable, str]]):
        """Reorder underlying BDD to respect order seen in inputs.
        
        As a side effect, this function turns off reordering.
        """
        pass


@attr.s(frozen=True, auto_attribs=True)
class DecisionDiagram:
    interface: Interface
    bdd: BDD

    def __call__(self, inputs):
        input_vars = self.interface.inputs
        encoded_inputs = {
            var.name: var.encode(inputs[var.name]) for var in input_vars
        }
        assert self.interface.valid()(encoded_inputs)[0]

        vals = {}
        for var in self.interface.inputs:
            encoded = encoded_inputs[var.name]

            # Turn bitvector into individual assignments.
            bundle = var.bundle
            encoded = BV.encode_int(bundle.size, encoded, signed=False)
            vals.update(bundle.blast(encoded))
        bdd = self.bdd.let(**vals)
        assert bdd.dag_size == 2, "Result should be single variable BDD."

        # Return which decision this was.
        name, idx = INDEX_SPLITTER.match(bdd.var).groups()
        idx = int(idx)
        output_var = self.interface.output
        assert name == output_var.name
        assert 0 <= idx < output_var._encoding_size
        return output_var.decode(1 << idx)

    def override(self, test: ValueLike, pos: DD) -> DD:
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


__all__ = ["DecisionDiagram", "Interface", "Variable", "BDD", "to_var", "to_bdd"]
