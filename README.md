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

```python
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

The `mdd` api centers around three `DecisionDiagram` objects.

  This
object is a wrapper around a Binary Decision Diagram object (from
[dd](https://github.com/tulip-control/dd)).


# Interfaces, Inputs, and Outputs

# MDD Manipulations
1. [ ] partial assigments.
1. [ ] overrides.
1. [ ] setting order.
1. [ ] wrapping lifting a bdd.

# Variables and Encodings


