# Python Code Style Guide

This document gives the conventions of the SK-RAFT Python client
(`api/python/skraft`). Follow them in all new code, so that the client stays
uniform.

All code must also follow PEP 8: four spaces for indentation, standard Python
spacing. The rules below are the *additional* project conventions on top of
PEP 8.

**Every line, code or comment, is at maximum 79 columns wide.** This is a hard
limit, not a guideline: any line that would reach column 80 must be broken.

**Write all docstrings and comments in ASD-STE100 Simplified Technical
English**, as `CONTRIBUTING.md` requires: short sentences, active voice, one
instruction or fact in each sentence.

Examples use placeholder names. Substitute the real module, class, and
function names of whatever you are working on.

---

## 1. File header

Every source file starts with the SPDX licence header. A blank line and the
module docstring come after it:

```python
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2024-2026 SOLIDKOSMOS S.A.

"""
Short description of the module, as one sentence.

One or more paragraphs that tell what the module contains and how it is
used.
"""
```

- The client is open source (Apache License 2.0). Do not use the proprietary
  banner of the SK-RAFT server.
- `datatypes.py` and `skraft_fpga.py` do not have the header yet. Add it when
  you change one of these files.

---

## 2. Imports

Imports come after the module docstring, in three groups with one blank line
between them:

```python
from __future__ import annotations

import hashlib
import os
from typing import Optional, overload

import grpc
from google.protobuf import empty_pb2

from . import skraft_client_pb2
from .datatypes import (
    Design,
    FpgaFrame,
    TargetMemory,
)
from .exceptions import (
    ConnectionFailedError,
    DesignFileError,
)
```

- `from __future__ import annotations` is the first import of every module
  that has type hints.
- The groups are: the standard library, third-party packages (`grpc`,
  `google.protobuf`), then the client itself.
- Imports from the client are relative (`from . import`, `from .datatypes
  import`). Do not import the client by its package name from inside it.
- Import the generated modules as modules (`from . import
  skraft_client_pb2`), and use their names with the module prefix.
- When an import names more than one item and does not fit on one line, put
  the names in parentheses, one name on each line, with a trailing comma.
- Do not use wildcard imports (`from x import *`).

---

## 3. Naming

| Item | Style | Example |
| --- | --- | --- |
| Module | `snake_case` | `skraft_fpga.py`, `datatypes.py` |
| Class | `CapWords` | `FpgaFrame`, `XadcSensorSelector` |
| Exception | `CapWords`, ends with `Error` | `BscanError` |
| Function, method, variable | `snake_case` | `read_register`, `reg_addr` |
| Constant | `UPPER_CASE` | `SK_RAFT_VERSION` |
| Enum member | `UPPER_CASE` | `TargetMemory.ESSENTIAL_CRAM` |
| Private name | leading `_` | `_rpc_detail`, `_UPLOAD_CHUNK_SIZE` |

- Write acronyms as one word in class names: `Fpga`, `Bscan`, `Xadc`, not
  `FPGA`, `BSCAN`, `XADC`.
- Give a class that mirrors a server message the prefix of its area:
  `FpgaFrame`, `FpgaScrubReport`, `XadcSensor`.
- Put the unit at the end of the name of a quantity: `duration_ms`,
  `sbu_percent`, `READ_PERIOD_S`.
- `uploadDesignToServer` and `programFPGA` are older names that do not follow
  these rules. They stay for compatibility. Do not add new `camelCase` names.

---

## 4. Docstrings

Every module, class, function, method and property has a docstring. Private
helpers have one too.

The opening `"""` is on its own line. The first line of text is a summary,
as one sentence. A blank line and the details come after it, then the
sections:

```python
def read_widget(self, widget_addr: int) -> int:
    """
    Read a widget of the device.

    Uses the FpgaReadWidget RPC.

    Parameters:
        widget_addr (int): The address of the widget, for example
            WidgetAddress.STATUS.

    Returns:
        int: The value of the widget.

    Raises:
        WidgetError: If the widget could not be read.
    """
```

- The summary of a function or method is an instruction: "Read a widget of
  the device.", "Create a frame.", "Reserve a device by its serial number."
- The summary of a class tells what an object of the class is: "A single
  32-bit word of configuration data."
- A property has a docstring of one line: `"""The value of the word."""`.
- An exception class has a docstring of one sentence that tells what failed:
  `"""A boundary-scan (BSCAN) operation failed."""`.
- Use only these section names, in this order: `Parameters:`, `Returns:`,
  `Yields:`, `Raises:`, `Examples:`. A class uses `Attributes:`. Do not use
  `Args:`.
- Write each item as `name (type): Description.` Indent a continuation line
  by four more spaces.
- In `Returns:`, give the type, then the description: `int: The value of the
  widget.`
- In `Raises:`, give each exception that a caller can catch, and when it
  occurs.
- A method that calls the server tells which RPC it uses: "Uses the
  FpgaReadRegister RPC."
- Give the unit of each physical value. The client uses the International
  System of Units (SI): volts (V), degrees Celsius (degC), seconds, and so
  on.

---

## 5. Type hints

Every function and method has type hints for all parameters (except `self`
and `cls`) and for the return value, including `-> None`:

```python
def write_widget(self, widget_addr: int, value: int) -> None:
```

- Use `Optional[X]` for a value that can be `None`.
- Use the built-in generic types: `list[FpgaFrame]`, `dict[str, int]`,
  `tuple[str, ...]`.
- `X | Y` is permitted in annotations, because of
  `from __future__ import annotations`.
- Use `typing.overload` when one method accepts different kinds of
  arguments. If the overloads give different names to the same argument,
  make it positional-only with `/`:

```python
@overload
def read_sensor(self, selector: SensorSelector, /) -> Sensor: ...

@overload
def read_sensor(self, drp_address: int, /) -> Sensor: ...

def read_sensor(self, sensor: SensorSelector | int, /) -> Sensor:
```

- The client supports Python 3.9. Do not use language features that newer
  versions added, for example `match` statements or `X | Y` outside
  annotations, such as in `isinstance`.

---

## 6. Classes and getters

### Value types

A class that the client returns keeps its data in private, name-mangled
attributes. It gives each attribute through a read-only property with the
same name:

```python
class FpgaWidget:
    """
    A widget of the device.

    Attributes:
        far (int): The frame address of the widget.
        value (int): The value of the widget.
    """

    def __init__(self, far: int, value: int):
        """
        Create a widget.

        Parameters:
            far (int): The frame address of the widget.
            value (int): The value of the widget.
        """
        self.__far = far
        self.__value = value

    @property
    def far(self) -> int:
        """The frame address of the widget."""
        return self.__far

    @property
    def value(self) -> int:
        """The value of the widget."""
        return self.__value
```

- Use `self.__name` (two underscores) for the data of a value type.
- Do not add setters. A value type does not change after it is created.
- List each property under `Attributes:` in the class docstring.

### Input types

A class that the user fills in and gives to the client is a `@dataclass`.
Make it `frozen=True` when it does not change after it is created, as
`Design` is. Check the values in `__post_init__`, and raise `ValueError` for a
value that is not valid, as `FpgaFiSession` does.

### Client classes

`SkraftFpga` and `FpgaDevice` keep their connection state in attributes with
one underscore, for example `self._stub`. Only the client uses them. Give a
value to the user through a property. `FpgaDevice.serial_number`,
`FpgaDevice.part_number`, `SkraftFpga.ip` and `SkraftFpga.port` are older
public attributes. Do not add new ones.

- A class that holds a reservation or a connection is a context manager.
  `__enter__` returns the object. `__exit__` releases the reservation or
  closes the connection.
- Use a `@classmethod` for a constructor that does more than store values,
  for example `SkraftFpga.connect`.
- Give the gRPC stub to a helper as an argument, as
  `BscanPrimitive.shift_in` gets it. Do not store the stub in a value type.

---

## 7. Enums

```python
class WidgetMode(int, Enum):
    """
    The modes of a widget.

    Attributes:
        FAST (WidgetMode): The fast mode.
        SAFE (WidgetMode): The safe mode.
    """

    FAST = skraft_client_pb2.FPGA_WIDGET_MODE_FAST
    SAFE = skraft_client_pb2.FPGA_WIDGET_MODE_SAFE
```

- Use `class X(int, Enum)` when the user selects one value.
- Use `IntFlag` when the user can combine values, as `TargetMemory` does.
- When a value goes to the server, take it from the constant of the
  generated module, not from a number. Then the client and the server cannot
  disagree.

---

## 8. Errors

### The exception hierarchy

All exceptions of the client are in `exceptions.py`. Each one derives from
`SkraftError`, so that a caller can catch all of them with one `except`.
Each one is for one area of failure, for example `BscanError` or
`DesignFileError`. Export each one from `__init__.py`.

### Calls to the server

Put each RPC call in a `try` block. Change a `grpc.RpcError` into the
exception of the area, and keep the cause with `from e`:

```python
try:
    request = skraft_client_pb2.FpgaReadWidgetRequest(
        addr=int(widget_addr),
    )
    reply = self._stub.FpgaReadWidget(request)

    return reply.value
except grpc.RpcError as e:
    raise WidgetError(
        f"failed to read widget {widget_addr:#04x}: {_rpc_detail(e)}"
    ) from e
```

- Get the text of the server error with `_rpc_detail(e)`.
- Start the message with a lower-case letter, with no full stop at the end.
  Start it with "failed to" and tell what the client tried to do.
- Put the values that identify the request in the message: an address, a
  serial number, a file name.

### Errors of the caller

Check the arguments before the RPC call. Raise `TypeError` for an argument of
the wrong type and `ValueError` for a value that is not valid. Do not send a
request that is not valid to the server.

### Clean-up

Do not ignore an error. The only exception is a clean-up step, for example
`_release_programmers`. Tell in its docstring that it ignores errors, and
why.

---

## 9. Strings

- Use double quotes for strings.
- Use f-strings to put values in a string. Do not use `%` or `.format()`.
- To break a long string, put it in parentheses and let Python join the
  parts. Do not use a backslash to continue a line.

```python
raise ValueError(
    "a unit is required when the sensor is given by its "
    "DRP address"
)
```

---

## 10. Layout

- Maximum line length: 79 columns, for code, comments and docstrings. No
  exceptions.
- Break a long call or literal after the opening bracket. Put a trailing
  comma after the last item, and the closing bracket on its own line.
- Two blank lines between top-level definitions. One blank line between
  methods. Some older parts of `datatypes.py` and `skraft_fpga.py` have one
  blank line between top-level definitions. Correct them when you change
  them.
- Use a banner to separate groups of definitions in a long module:

```python
# --------------------------------------------------------------------------- #
# Injection selection
# --------------------------------------------------------------------------- #
```

- Inside a class, use the short form:

```python
    # -- device acquisition ------------------------------------------------ #
```

- Module constants come after the imports, each with a comment that tells
  what it is:

```python
# The size of each chunk that the client streams during a design file upload.
_UPLOAD_CHUNK_SIZE = 1 << 20
```

---

## 11. The public API

`__init__.py` sets what a user can import from `skraft`:

- Import each public name from its module.
- Put each public name in `__all__` too.
- When you add a public class, function, constant or exception, add it to
  both places.

---

## 12. Generated code

`skraft_client_pb2.py`, `skraft_client_pb2.pyi` and
`skraft_client_pb2_grpc.py` are generated from `skraft_client.proto` of the
SK-RAFT server. Do not change them by hand. After each change to the
`.proto` file, make them again with `grpcio-tools`:

```bash
python -m grpc_tools.protoc -I. --python_out=out --pyi_out=out \
    --grpc_python_out=out skraft_client.proto
```

Then change the import line in `skraft_client_pb2_grpc.py` to a relative
import, which is the only change by hand:

```python
from . import skraft_client_pb2 as skraft__client__pb2
```

Use the same `grpcio-tools` version as the files in the client. The
generated files require at least the `protobuf` version that made them.

---

## 13. Comments

- Write comments in Simplified Technical English, as complete sentences.
- Tell *why* the code does something. The code itself shows *what* it does.
- Put a comment on the line before the code it is about.
- Use `# type: ignore[code]` only with a specific error code, and only when
  the type checker cannot know the type.

---

## Checklist before opening a pull request

- [ ] SPDX header present, then the module docstring.
- [ ] Imports in three groups, `from __future__ import annotations` first,
      relative imports inside the client.
- [ ] `snake_case` for functions, methods and variables. No new `camelCase`
      names.
- [ ] Every module, class, function, method and property has a docstring,
      with `Parameters:`, `Returns:` and `Raises:` where they apply.
- [ ] Every function and method has type hints, including `-> None`.
- [ ] Value types keep their data in `self.__name` and give it through
      read-only properties.
- [ ] Every RPC call changes `grpc.RpcError` into a `SkraftError` subclass,
      with `from e`.
- [ ] New public names are in both the imports and `__all__` of
      `__init__.py`.
- [ ] Generated files are not changed by hand (except the relative import).
- [ ] No line exceeds 79 columns.
- [ ] Docstrings and comments are in Simplified Technical English.
