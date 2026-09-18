"""``CalendarNextEpoch(opcode)``: the per-``opcode`` round counter.

Calendar §1.5: the report instruction that performs Step2 alignment is a pure
side effect with no return value, so the round's epoch cannot come back through
alignment. Instead each core keeps a counter per ``opcode`` domain::

    epoch = CalendarNextEpoch(opcode)   // pure scalar increment, starts at 1

Properties this layer mirrors:

* the counter starts at ``1`` and is **per ``opcode``**, so one domain cannot
  perturb another (``ctr`` is a vector of ``epochTag``-wide lanes, selected by
  ``opcode``);
* it wraps only when the previous epoch's traffic has drained — invariant **O2**
  plus §4.5.2 contract 7 — and a wrap attempt with traffic in flight must
  *fault*, never silently reuse a live epoch;
* the width is open item ``C-5``, so ``capacity`` is ``2 ** epoch_tag_bits - 1``
  for the bound width and the layer refuses to depend on any other value.

The counter is not a data-plane operand: no notification, semaphore, or
``WAIT_SPR`` is involved anywhere in this file.
"""

from __future__ import annotations

import agentic_circuit as ac

from wse_model.acir.contract.widths import (
    EPOCH_TAG_MAX_BITS,
    EPOCH_TAG_MIN_BITS,
    EPOCH_TAG_MIN_VALUE,
)

__all__ = [
    "capacity_for",
    "epoch_policy",
    "refuses_wrap",
    "wraps_only_when_drained",
]

#: ``opcode`` is 3 bit, so the epoch vector has eight lanes (Calendar §2.3).
EPOCH_LANES = 8

#: Vector lane stride in bits. The vector is one 64 bit scalar (the frontend's
#: scalar limit), so it holds eight 8 bit lanes: the Calendar baseline
#: ``epoch_tag_bits = 8``. A wider ``C-5`` reading needs one scalar per lane and
#: is recorded as a gap in ``README.md``.
EPOCH_STRIDE = 8


def capacity_for(epoch_tag_bits: int) -> int:
    """``2 ** epoch_tag_bits - 1`` for the widths proposed by open item ``C-5``.

    Widths outside the documented 8-16 bit range are an error, never a silent
    clamp: the capacity decides when wraparound is even possible.
    """
    if not EPOCH_TAG_MIN_BITS <= epoch_tag_bits <= EPOCH_TAG_MAX_BITS:
        raise ValueError(
            f"epochTag width {epoch_tag_bits} is outside the proposed "
            f"{EPOCH_TAG_MIN_BITS}-{EPOCH_TAG_MAX_BITS} bit range (open item C-5)"
        )
    return (1 << epoch_tag_bits) - 1


def wraps_only_when_drained(ctr, capacity, drained) -> bool:
    """Whether the counter sits at capacity and may legitimately wrap."""
    return not ctr < capacity and drained


def refuses_wrap(ctr, capacity, drained) -> bool:
    """The wraparound refusal of Calendar §4.5.2 contract 7."""
    return not ctr < capacity and not drained


def lane_select(vector, opcode):
    """This ``opcode``'s lane of the epoch vector, ``opcode * stride`` bits up."""
    offset = ac.zext(opcode, ac.bits[EPOCH_STRIDE]) * ac.literal(
        EPOCH_STRIDE, ac.bits[EPOCH_STRIDE]
    )
    return ac.truncate(ac.zext(vector, ac.bits[EPOCH_STRIDE]) >> offset, ac.bits[EPOCH_STRIDE])


@ac.rule
def epoch_policy(v):
    """Advance ``CalendarNextEpoch(opcode)`` and publish the round's epoch.

    The resident counter is the event's ``ctr`` slot, which the compiler owns and
    commits with the rest of the activation. ``epochWrap`` is the explicit
    wraparound-refusal signal: the counter reached its ``epoch_tag_bits``
    capacity while older traffic was still in flight, so the epoch is invalid and
    the send/receive path must fault rather than account against a reused epoch
    (Calendar §4.5.2 contract 7, open item ``C-5``).
    """
    one = ac.literal(EPOCH_TAG_MIN_VALUE, ac.bits[EPOCH_STRIDE])
    zero = ac.literal(0, ac.bits[EPOCH_STRIDE])
    cap = ac.literal(v.epochCapacity, ac.bits[EPOCH_STRIDE])
    lane = lane_select(v.ctr, v.opcode)
    at_start = lane == zero
    at_cap = not lane < cap
    refuse = at_cap and not v.drained
    wrap = at_cap and v.drained
    next_tag = one if (at_start or wrap) else lane + one
    return v.with_fields(
        epochNext=ac.truncate(next_tag, ac.bits[v.epochTag]),
        epochOk=not refuse,
        epochWrap=refuse,
        fault=v.fault or refuse,
        accepted=v.accepted and not refuse,
    )
