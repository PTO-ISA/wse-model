"""Every ``@ac.struct`` and ``@ac.encoding`` enum of the ACIR layer, once.

Each payload type is defined exactly once and imported elsewhere with an
explicit ``from wse_model.acir.contract.payloads import Symbol``, so no symbol is
re-exported and no module-qualified access is used.

The names are the wire layout, not Python style: they are short and stable so
that ``with_fields`` patches stay readable and the ACIR field names keep matching
the design documents. The register-pair field boundaries are the normative ones
of Calendar §2.6 / §1.7:

.. code-block:: text

    rbLo = entry bytes 0..7   -> nodes 00..31 pairs
    rbHi = entry bytes 8..15  -> [15:0]  nodes 32..39 pairs
                                 [23:16] landCount
                                 [31:24] flags
                                 [63:32] expectedRxBytes
"""

from __future__ import annotations

from enum import Enum

import agentic_circuit as ac

from wse_model.acir.contract.widths import FLAGS_BITS

__all__ = [
    "Flags",
    "Opcode",
    "RBHI_FIELDS",
    "RBI_FIELDS",
]

#: ``opcode`` is 3 bit (Calendar §2.3). The literal is spelled here rather than
#: imported inside the decorator because the frontend evaluates an
#: ``ac.encoding(width=...)`` argument statically.
_OPCODE_WIDTH = 3

#: ``{P, L}`` pair encodings, ``value = L | (P << 1)`` (Calendar §2.2).
PAIR_ABSENT = 0b00
PAIR_ILLEGAL = 0b01
PAIR_PASS = 0b10
PAIR_LAND = 0b11

#: The ``flags`` byte bits of a route entry (Calendar §2.6).
FLAG_IS_MEMBER = 1 << 0
FLAG_IS_ROOT = 1 << 1
FLAG_SELF_LAND = 1 << 2

#: ``CalReg[opcode]`` release-gate states.
GATE_INSTALLED = 1
GATE_UNINSTALLED = 0

#: Local fault codes carried on the reachable fault lane. They are model
#: diagnostics, not an ISA encoding.
FAULT_NONE = 0
FAULT_ILLEGAL_PAIR = 1
FAULT_CALREG_UNINSTALLED = 2
FAULT_CALREG_RESERVED = 3
FAULT_EPOCH_INVALID = 4
FAULT_EXPVAL_ABOVE_CAPACITY = 5
FAULT_SEQ_OVERFLOW = 6

#: ``opcode`` codes 0 and 7 are reserved (Calendar §2.3).
OPCODE_RESERVED_INVALID = 0
OPCODE_EXTENSION = 7


@ac.encoding(width=_OPCODE_WIDTH)
class Opcode(Enum):
    """``opcode``: collective semantics, 3 bit, values fixed by Calendar §2.3.

    Codes ``0`` and ``7`` are reserved, so a node must fault rather than index a
    default ``CalReg`` entry.
    """

    INVALID = 0
    ALL_GATHER = 1
    REDUCE = 2
    ALL_REDUCE = 3
    REDUCE_SCATTER = 4
    SCATTER = 5
    GATHER = 6
    EXTENSION = 7


@ac.struct
class Flags:
    """The ``flags`` byte of a route entry, decoded bit by bit (Calendar §2.6)."""

    raw: ac.bits[FLAGS_BITS]
    member: bool
    root: bool
    selfLand: bool


#: ``rbLo`` is one flat 64 bit register holding nodes 0..31; the constant exists
#: so callers can name that view.
RBI_FIELDS = ac.BitfieldSpec(
    width=64,
    fields={
        "n00_31": (63, 0),
    },
)

#: Calendar §1.7 register-pair boundaries, read as alternate views of ``rbHi``.
#: ``rbHi[15:0]`` is the only part hardware treats as routing bits; the other 48
#: bits are the tail that rides along for free.
RBHI_FIELDS = ac.BitfieldSpec(
    width=64,
    fields={
        "nodes32_39": (15, 0),
        "landCount": (23, 16),
        "flags": (31, 24),
        "expectedRxBytes": (63, 32),
    },
)
