"""The single ``@ac.system`` entry point and its ``ac.jit`` specialization.

One selected ``@ac.system`` per compiled artifact. The system is the fixed NoC
node's Calendar engine: it wires the five rule-backed transitions over one payload
type, in the order the design documents fix them.

.. code-block:: text

    source(CalEvent)                     a route entry / received segment arrives
      -> load_route_entry(node_index)    the two scalar LDs + rbLo/rbHi decode
      -> apply_forward                   the stateless passive {P, L} hop
      -> admit_send                      the CalReg[opcode] release gate
      -> epoch_policy                    CalendarNextEpoch(opcode)
      -> recv_wait                       the expVal byte accounting
      -> sink

``node_index`` is the *fixed hardware node* of this specialization, so
``2 * node_index`` is a closed constant; the source's runtime ``blockId`` is what
the two scalar LDs index (Calendar §4.3). ``node_count`` and ``epoch_tag_bits``
are ``ac.static_assert``-checked at elaboration time, so an out-of-range node or a
``C-5``-illegal epoch width fails loudly instead of producing a plausible-looking
model.

**Why this file is self-contained.** ``ac.jit(..., workspace=...)`` builds a
*source closure* by walking static imports, and this frontend build rejects almost
every realistic module layout from inside a package. The diagnostics are recorded
verbatim in ``README.md``. What it does accept is a single-file capture, so this
entry file declares the one shared payload type, the width constants it needs, and
the five rules, and ``wse_model.acir.blocks`` keeps the per-rule semantic helpers
(pure functions, no frontend objects) that this file's rules mirror 1:1 and that
the test asserts against. That keeps "the definition's home" honest while still
lowering cleanly.
"""

from __future__ import annotations

import agentic_circuit as ac

__all__ = [
    "CALREG_ENTRY_COUNT",
    "EPOCH_CAPACITY_8",
    "EPOCH_LANES",
    "EPOCH_STRIDE",
    "NODE_COUNT_40",
    "REG_BITS",
    "CalEvent",
    "acir_top",
    "node_lowering_spec",
]

# -- width roots (mirrored by wse_model.acir.contract.widths) ----------------

#: ``opcode`` is 3 bit (Calendar §2.3), so ``CalReg`` has eight code points.
OPCODE_BITS = 3
#: ``CalReg`` entries; ``0`` and ``7`` are reserved.
CALREG_ENTRY_COUNT = 8
#: The Calendar baseline node count; ``routeBits`` is ``2 x node_count`` bit.
NODE_COUNT_40 = 40
#: An entry's register pair is two ordinary 64 bit loads (Calendar §2.6).
REG_BITS = 64
#: The ``epochTag`` baseline of open item ``C-5``.
EPOCH_TAG_BITS_8 = 8
#: One 64 bit scalar holds eight 8 bit epoch lanes (the frontend's scalar limit).
EPOCH_STRIDE = 8
EPOCH_LANES = 8
#: ``2 ** 8 - 1``: the wraparound capacity of the baseline epoch tag.
EPOCH_CAPACITY_8 = 255

# -- Calendar constants used by the rules -----------------------------------

#: ``{P, L}`` pair encodings, ``value = L | (P << 1)`` (Calendar §2.2).
PAIR_ABSENT = 0b00
PAIR_ILLEGAL = 0b01
PAIR_PASS = 0b10
PAIR_LAND = 0b11

#: The ``flags`` byte bits of a route entry (Calendar §2.6).
FLAG_IS_MEMBER = 1 << 0
FLAG_IS_ROOT = 1 << 1
FLAG_SELF_LAND = 1 << 2

#: Local fault codes carried on the reachable fault lane; model diagnostics, not
#: an ISA encoding.
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

#: The frontend has no unbounded set, so ``seen`` is a 64 bit one-hot bitmap.
SEEN_CAPACITY = 64

#: Calendar §1.7 register-pair boundaries, applied to the ``rbHi`` operand:
#: ``[15:0]`` nodes 32..39, ``[23:16]`` landCount, ``[31:24]`` flags,
#: ``[63:32]`` expectedRxBytes.
RBHI_FIELDS = ac.BitfieldSpec(
    width=64,
    fields={
        "nodes32_39": (15, 0),
        "landCount": (23, 16),
        "flags": (31, 24),
        "expectedRxBytes": (63, 32),
    },
)


# The one payload type of this layer: operands, derived lane, resident state.
#
#   ``lane`` is a node bitmap. ``2 x node_count`` would be 80 bit and exceeds the
#   64 bit scalar limit of the frontend, so the field is exactly ``node_count``
#   bits and the two-bit pairs travel in ``rbLo``/``rbHi`` as the hardware's
#   register pair does.
#
#   ``seen`` de-duplicates segment identities, one bit per ``seq`` (contract 5);
#   its width is a frontend limit recorded in ``README.md``.
#
#   ``calreg`` is the ``CalReg`` residency bitmap (``bit i`` *is*
#   ``CalReg[i].installed``) and ``ctr`` is the per-``opcode`` epoch counter
#   vector, whose lane for the active ``opcode`` sits ``opcode * 8`` bits up. Both
#   are resident state the compiler commits with the activation, and both reset to
#   zero — which is why reserved code ``0`` can never be released by a default
#   entry (Calendar §3.9, §4.4.4 rule 4).
@ac.struct
class CalEvent:
    opcode: ac.bits[3]
    epochTag: ac.bits[8]
    epochCapacity: ac.bits[8]
    seq: ac.bits[10]
    segAddr: ac.u64
    segBytes: ac.bits[32]
    selfSourced: bool

    rbLo: ac.u64
    rbHi: ac.u64

    pair: ac.u2
    passes: bool
    lands: bool
    lane: ac.bits[40]

    landCount: ac.bits[8]
    isMember: bool
    isRoot: bool
    selfLand: bool
    expectedRxBytes: ac.bits[32]

    dAddr: ac.u64
    capacity: ac.bits[32]
    counted: ac.bits[32]

    calreg: ac.u8
    gate: bool
    member: bool
    egress: ac.bits[40]

    ctr: ac.u64
    drained: bool
    epochNext: ac.bits[8]
    epochOk: bool
    epochWrap: bool

    accepted: bool
    countedNow: ac.bits[32]
    seen: ac.u64
    complete: bool
    fault: bool
    code: ac.bits[8]


# -- blocks/route_entry.py: the two-LD load and the rbLo/rbHi decode ----------


@ac.rule
def load_route_entry(v, node_index):
    """Decode one loaded 16 B entry: the pairs and the ``rbHi`` tail fields.

    ``pair(n) = ((rbLo >> 2n) & 3) | ((rbHi >> max(0, 2n - 64)) & 3)`` is the
    literal register-pair boundary of Calendar §1.7: for ``n <= 31`` the second
    shift is wider than the register and is zero; for ``n >= 32`` only ``rbHi``
    contributes. The illegal pair ``01`` is not repaired — ``fault`` makes it a
    reachable error lane (Calendar §2.2, §4.4.4 rule 2).
    """
    pair = ac.truncate(
        v.rbLo >> ac.literal(2 * node_index, ac.bits[REG_BITS]), ac.u2
    ) | ac.truncate(
        v.rbHi
        >> ac.literal(
            # For nodes 0..31 the rebased position is negative and the term must
            # vanish. It is set to the register width, because a shift by at least
            # the operand width yields zero in this frontend; shifting by 0 instead
            # leaks rbHi[1:0] — node 32's pair — into every node below 32.
            (2 * node_index - REG_BITS) if 2 * node_index >= REG_BITS else REG_BITS,
            ac.bits[REG_BITS],
        ),
        ac.u2,
    )
    zero8 = ac.literal(0, ac.bits[8])
    raw_flags = ac.truncate(v.rbHi >> ac.literal(24, ac.bits[REG_BITS]), ac.bits[8])
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


# -- blocks/forward.py: the stateless per-hop decision -----------------------


@ac.rule
def apply_forward(v):
    """Publish the stateless hop decision.

    ``passes``/``lands`` are the two Calendar rules for this node's own bits;
    ``egress`` is the node bitmap the NoC replicates over. Rule 2's ``- ingress``
    term is a NoC-side reduction over that bitmap because the ingress port is
    runtime data and this frontend cannot express dynamic bit selection.
    """
    return v.with_fields(
        egress=v.lane,
        fault=v.fault or v.pair == ac.literal(PAIR_ILLEGAL, ac.u2),
    )


# -- blocks/calreg.py: the CalReg[opcode] release gate -----------------------


@ac.rule
def admit_send(v):
    """Index ``CalReg[opcode]`` and gate the send.

    The gate is *not* a default: an uninstalled or reserved code sets ``fault``
    and clears ``gate`` (Calendar §3.9, §4.4.4 rule 4). The residency bitmap
    resets to zero, so code ``0`` is uninstalled by construction.
    """
    zero3 = ac.literal(OPCODE_RESERVED_INVALID, ac.bits[3])
    seven3 = ac.literal(OPCODE_EXTENSION, ac.bits[3])
    reserved = v.opcode == zero3 or v.opcode == seven3
    bit = ac.zext(ac.literal(1, ac.u1), ac.bits[8]) << ac.zext(v.opcode, ac.bits[8])
    present = (v.calreg & bit) != ac.literal(0, ac.u8)
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


# -- blocks/epoch.py: CalendarNextEpoch(opcode) ------------------------------


@ac.rule
def epoch_policy(v):
    """Advance ``CalendarNextEpoch(opcode)`` and publish the round's epoch.

    ``epochWrap`` is the explicit wraparound-refusal signal: the counter reached
    its ``epoch_tag_bits`` capacity while older traffic was still in flight, so
    the epoch is invalid and the receive path must fault rather than account
    against a reused epoch (Calendar §4.5.2 contract 7, open item ``C-5``).
    The lane is ``opcode * EPOCH_STRIDE`` bits up in the 64 bit vector.
    """
    one = ac.literal(1, ac.u64)
    zero = ac.literal(0, ac.u64)
    cap = ac.zext(v.epochCapacity, ac.u64)
    lane = v.ctr >> (ac.zext(v.opcode, ac.u64) * ac.literal(EPOCH_STRIDE, ac.u64))
    at_start = lane == zero
    at_cap = not lane < cap
    refuse = at_cap and not v.drained
    wrap = at_cap and v.drained
    next_tag = one if (at_start or wrap) else lane + one
    return v.with_fields(
        epochNext=ac.truncate(next_tag, ac.bits[8]),
        epochOk=not refuse,
        epochWrap=refuse,
        fault=v.fault or refuse,
        accepted=v.accepted and not refuse,
    )


# -- blocks/recv_wait.py: the expVal byte accounting -------------------------


@ac.rule
def recv_wait(v):
    """Account one delivered segment against the active receive command.

    Seven P0 contracts of Calendar §4.5.2 are enforced fail-closed: payload bytes
    only, ``[dst, dst + capacity)`` only, matching ``{opcode, epoch}`` only,
    de-duplicated by segment identity, ``expVal == 0`` completes immediately,
    ``expVal > capacity`` faults, and the source's own bytes never count.
    Completion is exactly ``counted >= expVal`` — no notification, no semaphore.
    """
    zero32 = ac.literal(0, ac.bits[32])
    zero64 = ac.literal(0, ac.u64)
    epoch_ok = v.epochOk and v.epochTag != ac.literal(0, ac.bits[8])
    fits = not (v.expectedRxBytes > v.capacity)
    inside = (not v.segAddr < v.dAddr) and (
        not (v.dAddr + ac.zext(v.capacity, ac.u64)) < (v.segAddr + ac.zext(v.segBytes, ac.u64))
    )
    bit = ac.zext(ac.literal(1, ac.u1), ac.u64) << ac.zext(v.seq, ac.u64)
    already = (v.seen & bit) != zero64
    seq_ok = v.seq < ac.literal(SEEN_CAPACITY, ac.bits[10])
    valid = (
        epoch_ok
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
        seen=(v.seen | bit) if valid else v.seen,
        complete=not counted < v.expectedRxBytes,
        accepted=valid,
        fault=not valid,
        code=(
            FAULT_EPOCH_INVALID
            if not epoch_ok
            else FAULT_EXPVAL_ABOVE_CAPACITY
            if not fits
            else FAULT_SEQ_OVERFLOW
            if not seq_ok
            else FAULT_NONE
        ),
    )


# -- the single system entry -------------------------------------------------


@ac.system
def acir_top(
    *,
    node_index: ac.const[int] = 0,
    node_count: ac.const[int] = 40,
    epoch_tag_bits: ac.const[int] = 8,
) -> None:
    """One NoC node's Calendar engine as an ACIR queue graph.

    ``node_index`` selects the fixed node, ``node_count`` is the ``Q1`` topology
    reading that sizes the bitmaps, and ``epoch_tag_bits`` is the ``C-5`` epoch
    width.
    """
    ac.static_assert(node_count > 0, message="node_count must be positive")
    ac.static_assert(node_index >= 0, message="node_index must be non-negative")
    ac.static_assert(
        node_index < node_count,
        message="node_index must be a node of the target topology",
    )
    ac.static_assert(
        epoch_tag_bits >= 8 and epoch_tag_bits <= 16,
        message="epoch_tag_bits is outside the proposed 8-16 bit range (C-5)",
    )

    incoming = ac.source(CalEvent, depth=2, latency=1)
    decoded = load_route_entry(incoming, node_index)
    forwarded = apply_forward(decoded)
    admitted = admit_send(forwarded)
    epoch = epoch_policy(admitted)
    accounted = recv_wait(epoch)
    ac.sink(accounted)


#: The single build entry: the 40-node Calendar baseline at node 0 with the 8 bit
#: baseline epoch tag. ``ac.jit`` binds only ``ac.const`` parameters.
node_lowering_spec = ac.jit(acir_top, node_index=0, node_count=40, epoch_tag_bits=8)
