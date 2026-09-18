"""The ``MTE4_NOC_RECV_WAIT`` byte accounting.

Calendar §4.5: ``MTE4_NOC_RECV_WAIT(dst, capacity, expVal, opcode, epoch)``
**moves no bytes**; the payload is written into the core's arena directly by the
NoC and MTE4 only *accounts*. The command retires once the valid payload bytes
that match ``{opcode, epoch, dstRange}`` and are already committed reach the
``expVal`` threshold.

Calendar §4.5.2 states the seven P0 contracts; the ones expressible at this level
are implemented here as explicit, fail-closed checks:

1. the unit is valid payload **bytes** — header, CRC, padding, retransmit copies
   and the source's own bytes never count (``selfSourced``);
2. only writes inside ``[dst, dst + capacity)`` matching the current
   ``{opcode, epoch}`` count; anything else is discarded **and faults**;
3. accounting happens after the payload is committed and readable — this rule
   accounts at the activation boundary, which is the commit point;
4. legal arrivals that predate the command but belong to the same established
   epoch must not be missed (the ``{opcode, epoch}`` key is the adoption key);
5. duplicate segment identities must not be double counted, including multicast
   forked copies per land point (the ``seen`` bitmap);
6. ``expVal == 0`` completes immediately; ``expVal > capacity`` and counter
   overflow fault — never a silent permanent block;
7. because ``opcode`` is a weak discriminator, ``collectionEpoch`` carries the
   whole discrimination duty, so a mismatched epoch must not be counted.

**Completion is exactly ``counted >= expVal`` and nothing else.** There is no
notification, no semaphore write, and no ``WAIT_SPR``; the design's whole point
is that completion is a local counter comparison (Calendar §1.2).

The de-duplication set is a 64 bit one-hot bitmap over ``seq``. The frontend
cannot express an unbounded set, so the model caps distinct segment identities at
64 and faults on overflow instead of aliasing (see ``README.md``).
"""

from __future__ import annotations

import agentic_circuit as ac

from wse_model.acir.contract.payloads import (
    FAULT_EPOCH_INVALID,
    FAULT_EXPVAL_ABOVE_CAPACITY,
    FAULT_NONE,
    FAULT_SEQ_OVERFLOW,
)

__all__ = [
    "SEEN_CAPACITY",
    "add_mask",
    "complete",
    "in_range",
    "recv_wait",
    "seen_bit",
]

#: The frontend has no unbounded set, so ``seen`` is a 64 bit one-hot bitmap.
SEEN_CAPACITY = 64


def seen_bit(seq) -> ac.u64:
    """The one-hot bitmap bit reserved for ``seq``."""
    return ac.zext(ac.literal(1, ac.u1), ac.u64) << ac.zext(seq, ac.u64)


def add_mask(seen: ac.u64, seq) -> ac.u64:
    """Mark ``seq`` as delivered without disturbing the other entries."""
    return seen | seen_bit(seq)


def complete(counted, exp_val) -> bool:
    """Contract 6 and the completion rule: ``counted >= expVal``, nothing else."""
    return not counted < exp_val


def in_range(addr, end_addr, dst, capacity) -> bool:
    """``dst <= address`` and ``address + nbytes <= dst + capacity`` (contract 2)."""
    return not addr < dst and not (dst + capacity) < end_addr


@ac.rule
def recv_wait(v):
    """Account one delivered segment against the active receive command.

    ``counted`` carries the running byte total and ``seen`` the de-duplication
    bitmap, so consecutive firings of this rule under one ``{opcode, epoch}`` are
    exactly one ``MTE4_NOC_RECV_WAIT`` command's accounting.
    """
    zero32 = ac.literal(0, ac.bits[32])
    zero64 = ac.literal(0, ac.u64)
    epoch_ok = v.epochOk and v.epochTag != ac.literal(0, ac.bits[v.epochTag])
    ctx_ok = epoch_ok
    exp_val = v.expectedRxBytes
    fits = not (exp_val > v.capacity)
    end_addr = v.segAddr + v.segBytes
    inside = in_range(v.segAddr, end_addr, v.dAddr, v.capacity)
    already = (v.seen & seen_bit(v.seq)) != zero64
    seq_ok = v.seq < ac.literal(SEEN_CAPACITY, ac.bits[32])
    valid = (
        ctx_ok
        and fits
        and inside
        and not already
        and seq_ok
        and not v.selfSourced
        and v.gate
        and not v.fault
    )
    counted = v.counted + (v.segBytes if valid else zero32)
    return v.with_fields(
        countedNow=v.segBytes if valid else zero32,
        counted=counted,
        seen=add_mask(v.seen, v.seq) if valid else v.seen,
        complete=complete(counted, exp_val),
        accepted=valid,
        fault=not valid,
        code=(
            FAULT_EPOCH_INVALID
            if not ctx_ok
            else FAULT_EXPVAL_ABOVE_CAPACITY
            if not fits
            else FAULT_SEQ_OVERFLOW
            if not seq_ok
            else FAULT_NONE
        ),
    )
