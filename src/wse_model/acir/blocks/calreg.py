"""``CalReg[opcode]`` residency and the release gate.

Calendar §3.9: the *value* of the timeslot information is computed at compile
time and installed once into a resident register on each NoC node. The core never
sees that value — it only supplies a 3 bit ``opcode``, and the node performs one
register index ``CalReg[opcode]`` to decide when to release the packet. The
properties this layer mirrors are:

* **Residency.** A send is admitted only when ``CalReg[opcode]`` is installed;
  the register image is written once inside a stop-the-world window and is
  read-only for the rest of the kernel.
* **Illegal or uninstalled codes fault.** ``opcode in {0, 7}`` and any code with
  no installed content must fault; they must never be released by a default
  entry. The gate is a residency bitmap that resets to all-zero, so code ``0``
  is *uninstalled by construction* — exactly the design's "an all-zero flit
  header must fault" (Calendar §4.4.4 rule 4).
* **Per-``opcode`` independence.** One domain cannot head-of-line block another;
  the indexed bit is the whole state.

The register file is modelled as an 8 bit residency bitmap over the 3 bit
``opcode`` space. A ``Table`` was the natural carrier, but this frontend build
resolves a Table entry type only inside the file that declares it, so a Table
whose row type lives in the contract layer cannot be declared (see ``README.md``).
The bitmap is the equivalent closed form: ``bit i`` *is* ``CalReg[i].installed``,
and code ``0`` stays uninstalled because the reset image is zero.
"""

from __future__ import annotations

import agentic_circuit as ac

from wse_model.acir.contract.payloads import (
    FAULT_CALREG_RESERVED,
    FAULT_CALREG_UNINSTALLED,
    FAULT_NONE,
    OPCODE_EXTENSION,
    OPCODE_RESERVED_INVALID,
)

__all__ = [
    "CALREG_BITS",
    "admit_send",
    "installed",
    "mask_with",
    "reserved_code",
]

#: ``opcode`` is 3 bit, so ``CalReg`` has eight code points (Calendar §2.3).
CALREG_BITS = 8


def reserved_code(code):
    """Whether ``opcode`` is one of the two reserved codes ``0`` and ``7``."""
    zero = ac.literal(OPCODE_RESERVED_INVALID, ac.bits[3])
    seven = ac.literal(OPCODE_EXTENSION, ac.bits[3])
    return code == zero or code == seven


def installed(mask, code) -> bool:
    """``CalReg[opcode].installed``: the indexed bit of the residency bitmap."""
    shifted = ac.truncate(
        ac.zext(mask, ac.bits[CALREG_BITS]) >> ac.zext(code, ac.bits[CALREG_BITS]),
        ac.u1,
    )
    return shifted == ac.literal(1, ac.u1)


def mask_with(mask, code, value: bool):
    """Return the residency bitmap with ``CalReg[opcode]`` set or cleared."""
    bit = ac.zext(ac.literal(1, ac.u1), ac.bits[CALREG_BITS]) << ac.zext(code, ac.bits[CALREG_BITS])
    return (mask | bit) if value else (mask & ~bit)


@ac.rule
def admit_send(v):
    """Index ``CalReg[opcode]`` and gate the send.

    The gate is *not* a default: an uninstalled or reserved code sets ``fault``
    and clears ``gate``, which every later stage keys off (Calendar §3.9).
    """
    reserved = reserved_code(v.opcode)
    present = installed(v.calreg, v.opcode)
    admitted = present and not reserved
    return v.with_fields(
        gate=admitted,
        member=present,
        accepted=admitted,
        fault=v.fault or not admitted,
        code=(
            FAULT_CALREG_RESERVED
            if reserved
            else FAULT_CALREG_UNINSTALLED
            if not present
            else FAULT_NONE
        ),
    )
