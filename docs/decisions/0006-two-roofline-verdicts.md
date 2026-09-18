# 0006 — The model reports two roofline verdicts, not one

- **Status:** accepted
- **Date:** 2026-09-18
- **Supersedes:** nothing
- **Relates to:** whitepaper §1, §3.1, §19.2; Calendar §3.4

## Context

Whitepaper §1 derives the whole WSE motivation from one ratio. Per AICORE the
balance point is the Cube throughput over the local DRAM bandwidth — 11.5
FLOP/Byte at FP16, 45.9 at FP8, 91.8 at FP4 — and the decode-stage GEMV intensity
is stated as "approximately `2 x batch` FLOP/Byte, because each weight byte is
used once". Dividing the balance point by two gives the batch at which decode
stops being memory-bound: about 6, 23, and 46.

That analysis counts **two FLOPs per weight element**. It therefore treats a
"weight byte" as one weight element regardless of the element's real width, and
it assumes the Cube fills its `M x K x N` block every cycle.

Both assumptions are first-order. A tile-accurate model has to charge for them:

- at FP16 a weight element is two bytes, so the physically exact intensity is
  `batch` FLOP per fetched weight byte, not `2 x batch`; and
- the Cube's block is 16 rows tall, so at `batch = 1` the array runs at 1/16 of
  its row capacity and retires 256 MACs/cycle instead of 4096.

Implementing only one convention in `wse_model.core.cube` while
`wse_model.analysis.roofline` implements the other would put two contradictory
answers inside one model. Choosing one and discarding the other would either
break the published 6/23/46 figures or hide a real effect.

## Decision

`MatmulTiming` reports **both** verdicts, named so they cannot be confused:

- `first_order_is_memory_bound` reproduces the whitepaper's balance-point
  analysis, with `first_order_intensity = 2 x batch` FLOP per weight element.
  This is the view that yields the published minimum batches 6 / 23 / 46, and
  `wse_model.analysis.roofline` remains its authority.
- `is_memory_bound` is tile-accurate: it compares the fetched-weight seconds with
  the Cube seconds including `m_utilization`, and is the view that answers "which
  leg actually sets the time for this shape".

`describe()` reports `m_utilization`, `effective_macs_per_cycle`, both verdicts,
and a `verdicts_agree` flag.

## Consequences

For the canonical batch-1 GEMV `[1, 4096] x [4096, 4096]`:

| precision | effective MACs/cycle | compute | fetch | tile-accurate | first-order |
| --- | --- | --- | --- | --- | --- |
| FP16 | 256 | 46.8 µs | 33.6 µs | compute | memory |
| FP8 | 1024 | 11.7 µs | 16.8 µs | memory | memory |
| FP4 | 2048 | 5.9 µs | 8.4 µs | memory | memory |

So the design's headline claim — decode is weight-bandwidth-bound — holds at FP8
and FP4 batch 1, and at FP16 once the batch fills the Cube's row block. At FP16
batch 1 the idle rows, not the memory system, are the binding constraint. That is
a statement about the Cube's shape, not a defect in the design's bandwidth
argument, and it is exactly the kind of thing a model exists to surface.

Two follow-on obligations:

1. Any report that quotes a "memory-bound" or "compute-bound" label must say
   which verdict it means. The CLI and the documentation do.
2. The published minimum batches (6 / 23 / 46) stay pinned by
   `tests/golden/test_golden_vectors.py` and must not move. If a future decision
   changes the convention, it changes that test deliberately and cites this
   record.

## Alternatives considered

- **Report only the tile-accurate verdict.** Rejected: it contradicts the
  published 6/23/46 figures and would silently imply the whitepaper's analysis is
  wrong.
- **Report only the first-order verdict.** Rejected: it asserts a "memory-bound"
  label for a shape where memory is not the binding leg, which is the sort of
  unfalsifiable claim the rest of this model refuses to make.
- **Make the element width the sole difference and normalise the block fill
  away.** Rejected: the under-fill is a real, measurable consequence of the fixed
  16-row Cube that the whitepaper itself relies on elsewhere (§3.1 notes the Cube
  and the memory system are deliberately balanced at 512 B of weights per cycle
  against about 714 B supplied).
