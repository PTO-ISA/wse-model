"""JIT-bound roots and the exact widths of the ``agentic_circuit`` layer.

This module is the only place that declares ``ac.param`` roots. The roots exist
so that a dependent width in :mod:`wse_model.acir.contract.payloads` resolves
only under an explicit ``ac.jit`` specialization, exactly like the documented
``types/parameterized_types.py`` pattern of the ``agentic_circuit`` frontend.

The numeric values are transcribed from the design sources, never re-derived:

* ``routeBits`` is ``2 x node_count`` bit (Calendar §2.2), so 80 bit = 10 B at
  the 40-node Calendar baseline and 96 bit = 12 B at the 48-node whitepaper
  reading (open item ``Q1``);
* the route-table entry is 16 B and its register pair is two ordinary 64 bit
  loads (Calendar §2.6, §1.7), so ``rbLo``/``rbHi`` are always exactly 64 bit;
* ``opcode`` is 3 bit (Calendar §2.3);
* ``epochTag`` is an open 8-16 bit parameter (open item ``C-5``) whose Calendar
  baseline is 8 bit.
"""

from __future__ import annotations

import agentic_circuit as ac

__all__ = [
    "ADDRESS_BITS",
    "BYTE_COUNT_BITS",
    "CALREG_ENTRY_COUNT",
    "EPOCH_ROW_COUNT",
    "EPOCH_TAG_BITS",
    "EPOCH_TAG_MAX_BITS",
    "EPOCH_TAG_MIN_BITS",
    "EPOCH_TAG_MIN_VALUE",
    "FLAGS_BITS",
    "LAND_COUNT_BITS",
    "NODE_COUNT",
    "RECV_ROW_COUNT",
    "REG_BITS",
    "ROW_BYTES_BITS",
    "ROW_STRIDE_BITS",
    "SEQ_BITS",
]

#: ``routeBits`` is ``2 x node_count`` bit (Calendar §2.2); 40 at the baseline,
#: 48 under the whitepaper reading of open item ``Q1``.
NODE_COUNT = ac.param[int]("node_count")

#: ``epochTag`` is an open 8-16 bit parameter (Calendar §1.8, open item ``C-5``).
EPOCH_TAG_BITS = ac.param[int]("epoch_tag_bits")

#: The proposed ``epochTag`` range of open item ``C-5``.
EPOCH_TAG_MIN_BITS = 8
EPOCH_TAG_MAX_BITS = 16

#: Calendar §1.5: the per-``opcode`` round counter starts at 1.
EPOCH_TAG_MIN_VALUE = 1

#: ``opcode`` is 3 bit (Calendar §2.3), so ``CalReg`` has eight code points with
#: ``0`` and ``7`` reserved.
OPCODE_BITS = 3
CALREG_ENTRY_COUNT = 1 << OPCODE_BITS

#: One ``CalReg[opcode]`` row exists per opcode code point.
EPOCH_ROW_COUNT = CALREG_ENTRY_COUNT

#: The two registers of one 16 B route entry are ordinary 64 bit loads
#: (Calendar §2.6, §1.7); this never depends on the node count.
REG_BITS = 64

#: ``landCount`` is the entry's byte 10, ``flags`` byte 11 (Calendar §2.6).
LAND_COUNT_BITS = 8
FLAGS_BITS = 8

#: ``expectedRxBytes`` is the entry's ``uint32`` tail (Calendar §2.6).
BYTE_COUNT_BITS = 32

#: ``MTE4_NOC_RECV_WAIT(dst, capacity, expVal, opcode, epoch)`` operand widths.
#: ``S-1`` leaves the exact widths open; the model follows the Calendar
#: baseline's ``uint32`` for ``expVal``/``capacity`` and a 64 bit symmetric
#: address.
ADDRESS_BITS = 64
#: ``seq`` identifies one delivered segment for de-duplication (contract 5).
SEQ_BITS = 10

#: Receive-arena geometry of the FFN example (Calendar §2.2.1, §2.8): 8 rows.
RECV_ROW_COUNT = 8
ROW_STRIDE_BITS = 32
ROW_BYTES_BITS = 32
