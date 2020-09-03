# Py-MDD

Python abstraction around Binary Decision Diagrams to implement
Multivalued Decision Diagrams.

[![Build Status](https://cloud.drone.io/api/badges/mvcisback/py-mdd/status.svg)](https://cloud.drone.io/mvcisback/py-mdd)
[![docs badge](https://img.shields.io/badge/docs-docs-black)](https://mjvc.me/py-mdd)
[![codecov](https://codecov.io/gh/mvcisback/py-mdd/branch/main/graph/badge.svg)](https://codecov.io/gh/mvcisback/py-mdd)
[![PyPI version](https://badge.fury.io/py/mdd.svg)](https://badge.fury.io/py/mdd)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


# Installation

If you just need to use `py-mdd`, you can just run:

`$ pip install mdd`

For developers, note that this project uses the
[poetry](https://poetry.eustace.io/) python package/dependency
management tool. Please familarize yourself with it and then
run:

`$ poetry install`


# Usage

For the impatient, here are two basic usage examples:

```python
import mdd

interface = mdd.Interface(
    inputs={
        "x": [1, 2, 3],
        "y": [6, 'w'], 
        "z": [7, True, 8],
    }, 
    output=[-1, 0, 1],
)
func = interface.constantly(-1)
assert func({'x': 1, 'y': 'w', 'z': 8}) == -1
```

## Variables, Interfaces, and Encodings


func.override()


The `mdd` api centers around three objects:

1. `Variable`: Representation of a named variable taking on values in
   from a finite set described by an aiger circuit.
1. `Interface`: Description of inputs and outputs of a Multi-valued Decision Diagram.
1. `DecisionDiagram`: Representation of a Multi-valued Decision Diagram that conforms
   to an interface.

This object is a wrapper around a Binary Decision Diagram object (from
[dd](https://github.com/tulip-control/dd)).

By default, variables use one-hot encoding, but all input variables
can use arbitrary encodings.

```python
# One hot encoded.
var1 = mdd.to_var(domain=["x", "y", "z"], name="myvar1")

# Copied from another variable.
var2 = var1.with_name("myvar2")

# Hand crafted encoding using `py-aiger`.

import aiger_bv

# Named 2-length bitvector circuit.
bvexpr = aiger_bv.uatom(2, 'myvar3')

domain = ('a', 'b', 'c')
var3 = mdd.Variable(
     encode=domain.index,        # Any -> int
     decode=domain.__getitem__,  # int -> Any
     valid=bvexpr < 4,           # 0b11 is invalid!
)

interface = mdd.Interface(inputs=[var1, var2, var3], output={1, 2, 3})
```

## MDD Manipulations

TODO

## BDD <-> MDD

TODO