"""The two-LD ``CalendarRouteEntry`` load and its ``rbLo``/``rbHi`` field decode.

Calendar §2.6 / §1.7 fix the entry at 16 B so that two ordinary 64 bit scalar
``LD`` operations fill one GPR pair, and §4.4.1 shows the send instruction taking
``rbLo`` and ``rbHi`` as ordinary register operands::

    rbLo = entry bytes 0..7   -> nodes 00..31
    rbHi = entry bytes 8..15  -> [15:0]  nodes 32..39
                                 [23:16] landCount
                                 [31:24] flags
                                 [63:32] expectedRxBytes

The *source's* runtime ``blockId`` is what the two scalar loads index; the node
whose pair this rule extracts is the **fixed hardware node** the specialization
was compiled for. That node index is therefore an ``ac.const[int]`` and
``2 * node_index`` is a closed constant, which is what lets the frontend fold the
extraction exactly as the hardware's fixed wiring does.

The two shifts below are the literal expression of the register-pair boundary::

    pair(n) = ((rbLo >> 2n) & 3) | ((rbHi >> max(0, 2n - 64)) & 3)

For ``n <= 31`` the second shift is by at least 64, whose exact-width semantics
are zero, so only ``rbLo`` contributes; for ``n >= 32`` only ``rbHi``
contributes. That is precisely "``rbLo`` holds nodes 0..31 and ``rbHi[15:0]``
holds nodes 32..39", with no dynamic bit slicing anywhere.

The rule parameter is deliberately unannotated: this frontend resolves a payload
type name only inside the file that declares it, so the shared record type is
declared once in :mod:`wse_model.acir.model.top` and the blocks operate on its
fields generically.
"""

from __future__ import annotations

import agentic_circuit as ac

from wse_model.acir.contract.payloads import (
    FAULT_ILLEGAL_PAIR,
    FLAG_IS_MEMBER,
    FLAG_IS_ROOT,
    FLAG_SELF_LAND,
    PAIR_ILLEGAL,
    PAIR_LAND,
    PAIR_PASS,
)

__all__ = [
    "REG_BITS",
    "both_shift_amounts",
    "load_route_entry",
    "pair_bit_high",
    "pair_bit_low",
    "pair_of",
]

#: ``routeBits`` is ``2 x node_count`` bit, but the entry's register pair is
#: always two 64 bit loads regardless of topology (Calendar §2.6).
REG_BITS = 64


def both_shift_amounts(node_index: int) -> tuple[ac.bits[REG_BITS], ac.bits[REG_BITS]]:
    """Return ``(shift_lo, shift_hi)`` as exact-width closed 64 bit constants.

    ``shift_lo`` is ``2 * node_index``. ``shift_hi`` is the same bit position
    rebased into the second register: ``2 * node_index - 64`` for nodes 32 and
    above, which is where ``rbHi`` starts.

    For nodes 0..31 the rebased position would be negative, and the term must
    **vanish** rather than shift by zero. It is set to ``REG_BITS`` on purpose,
    because this frontend defines a shift by at least the operand width as zero
    (``agentic-circuit.md`` §"exact-width arithmetic"). Shifting by ``0`` would
    instead leak ``rbHi[1:0]`` — node 32's pair — into every node below 32, which
    is exactly the cross-register aliasing the register-pair layout exists to
    avoid.
    """
    shift_lo = ac.literal(2 * node_index, ac.bits[REG_BITS])
    raw_hi = 2 * node_index - REG_BITS
    shift_hi = ac.literal(raw_hi if raw_hi >= 0 else REG_BITS, ac.bits[REG_BITS])
    return shift_lo, shift_hi


def pair_bit_low(event, node_index: int) -> ac.u2:
    """``rbLo``'s contribution to this node's ``{P, L}`` pair."""
    shift_lo, _ = both_shift_amounts(node_index)
    return ac.truncate(event.rbLo >> shift_lo, ac.u2)


def pair_bit_high(event, node_index: int) -> ac.u2:
    """``rbHi[15:0]``'s contribution to this node's ``{P, L}`` pair."""
    _, shift_hi = both_shift_amounts(node_index)
    return ac.truncate(event.rbHi >> shift_hi, ac.u2)


def pair_of(event, node_index: int) -> ac.u2:
    """The node's ``{P, L}`` pair, ``value = L | (P << 1)`` (Calendar §2.2)."""
    lo = pair_bit_low(event, node_index)
    hi = pair_bit_high(event, node_index)
    return lo | hi


@ac.rule
def load_route_entry(v, node_index):
    """Decode one loaded 16 B entry into the model's event fields.

    The rule returns its input payload type, which the frontend requires of every
    ``@ac.rule``; every derived fact is written as a field. The illegal pair
    ``01`` is deliberately *not* repaired here: ``fault`` makes it a reachable
    error lane that the CalReg gate refuses to release (Calendar §2.2, §4.4.4).
    """
    pair = pair_of(v, node_index)
    raw_flags = ac.truncate(v.rbHi >> ac.literal(24, ac.bits[REG_BITS]), ac.bits[8])
    zero8 = ac.literal(0, ac.bits[8])
    member = (raw_flags & ac.literal(FLAG_IS_MEMBER, ac.bits[8])) != zero8
    root = (raw_flags & ac.literal(FLAG_IS_ROOT, ac.bits[8])) != zero8
    self_land = (raw_flags & ac.literal(FLAG_SELF_LAND, ac.bits[8])) != zero8
    return v.with_fields(
        pair=pair,
        passes=pair == ac.literal(PAIR_PASS, ac.u2) or pair == ac.literal(PAIR_LAND, ac.u2),
        lands=pair == ac.literal(PAIR_ILLEGAL, ac.u2) or pair == ac.literal(PAIR_LAND, ac.u2),
        lane=ac.zext(pair, ac.bits[40]),
        landCount=ac.truncate(v.rbHi >> ac.literal(16, ac.bits[REG_BITS]), ac.bits[8]),
        isMember=member,
        isRoot=root,
        selfLand=self_land,
        expectedRxBytes=ac.truncate(v.rbHi >> ac.literal(32, ac.bits[REG_BITS]), ac.bits[32]),
        fault=pair == ac.literal(PAIR_ILLEGAL, ac.u2),
        code=ac.literal(FAULT_ILLEGAL_PAIR, ac.bits[8]),
    )
