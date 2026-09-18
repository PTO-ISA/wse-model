# AICORE

The AICORE is the WSE compute core: one Cube plus one Vector at 1.4 GHz, with a
private 384 MB local DRAM at 1 TB/s. This page states what the model knows about
it and what it does not.

Two packages carry it:

- [`wse_model.analysis.platform`](../../src/wse_model/analysis/platform.py) records
  the transcribed constants, and
  [`wse_model.analysis.roofline`](../../src/wse_model/analysis/roofline.py) the
  closed-form balance arithmetic.
- [`wse_model.core`](../../src/wse_model/core/) models the pipe set and the
  Calendar ordering rules, the local DRAM page arithmetic, the on-chip buffer
  hierarchy, and Cube/Vector timing.

Reach them through `wse-model report aicore` and `wse-model report roofline`.
What is **not** modelled is listed in [What is not modelled](#what-is-not-modelled).

Design sources: whitepaper [§1](../design/wse-system-architecture-whitepaper.md),
[§2](../design/wse-system-architecture-whitepaper.md),
[§3](../design/wse-system-architecture-whitepaper.md),
[§4.4](../design/wse-system-architecture-whitepaper.md),
[§15.2](../design/wse-system-architecture-whitepaper.md),
[§19](../design/wse-system-architecture-whitepaper.md); Calendar
[§4.7](../design/wse-calendar-scheme.md).

## Platform constants

Every constant carries its source in the module. Nothing is rounded or inferred:
a value that is not in the design sources is a declared parameter or a registered
open item, never a hard-coded constant.

| Symbol | Value | Meaning (design source) |
| --- | --- | --- |
| `AICORE_CLOCK_HZ` | `1.4e9` | one AICORE = 1 Cube + 1 Vector at 1.4 GHz (whitepaper §3) |
| `LOCAL_DRAM_BYTES` | `384 * 1024 * 1024` = 402 653 184 | per-core private local DRAM, 384 MB (whitepaper §3.2) |
| `LOCAL_DRAM_BYTES_PER_SEC` | `1.0e12` | 1 TB/s local DRAM bandwidth (whitepaper §3.2 / §1.2) |
| `LOCAL_DRAM_PAGE_BYTES` | `2048` | the actual read/write granularity is a 2 KB page (whitepaper §3.4) |
| `VECTOR_BYTES_PER_CYCLE` | `256` | Vector parallelism (whitepaper §3.1) |
| `FIXPIPE_BYTES_PER_CYCLE` | `256` | FixPipe matches the Vector (whitepaper §3.1) |
| `UB_BYTES` | `384 * 1024` | the intra-core Unified Buffer size; also `ON_CHIP_BUFFERS["UB"]` |

Note the two meanings of "UB" the whitepaper warns about: at this level it is the
intra-core **Unified Buffer**; the external **UB bus** is a different thing and is
described in [Batcher and UB bus](batcher-ub.md).

### On-chip storage hierarchy

`ON_CHIP_BUFFERS` transcribes the whitepaper §3.2 table, and `wse_model.core.buffers`
re-exports it as `BUFFER_CAPACITY_BYTES` and `BufferKind`:

| Level | Bytes | Role |
| --- | --- | --- |
| `L0A` | `128 * 1024` | Cube left matrix (activations) |
| `L0B` | `512 * 1024` | Cube right matrix (weights); WSE widens this to 4× L0A |
| `L0C` | `256 * 1024` | Cube accumulation output |
| `L1` | `1 * 1024 * 1024` | on-chip large buffer |
| `UB` | `384 * 1024` | Vector workspace; a candidate location for the collective arena |

## Cube precisions and the roofline

`PrecisionSpec` and `PRECISIONS` transcribe the whitepaper §3.1 precision table.
A MAC is counted as two FLOPs (whitepaper Appendix A.4 assumption 4), and
`bytes_per_element` is what a memory-bound operator actually pays.

| Name | Cube shape (M×K×N) | MAC/cycle | FLOP/cycle | TFLOPS at 1.4 GHz | bytes/element |
| --- | --- | --- | --- | --- | --- |
| `fp16` | 16×16×16 | 4 096 | 8 192 | 11.469 | 2.0 |
| `fp8` | 16×32×32 | 16 384 | 32 768 | 45.875 | 1.0 |
| `fp4` | 16×64×32 | 32 768 | 65 536 | 91.75 | 0.5 |

The MAC ratio is exactly 1 : 4 : 8. `precision(name)` looks one up and
`PrecisionSpec.compute_intensity_balance()` returns the FLOP/Byte balance point
against a bandwidth (local DRAM by default).

### What the balance point means

A decode-stage GEMV reuses each weight byte once, so its arithmetic intensity is
about `2 × batch` FLOP/Byte (`arithmetic_intensity_decode`). Dividing the balance
point by two gives the batch at which decode stops being memory-bound
(`min_batch_to_escape_memory_bound`):

| Precision | Balance point (FLOP/Byte) | Minimum batch |
| --- | --- | --- |
| `fp16` | 11.469 | 5.73 |
| `fp8` | 45.875 | 22.94 |
| `fp4` | 91.75 | 45.88 |

The design quotes these as about 11.5 / 45.9 / 91.8 and batch 6 / 23 / 46;
`roofline_table()` returns the three `RooflinePoint`s in `fp16`, `fp8`, `fp4`
order. The sharp point of whitepaper §19.2 is that lowering precision helps a
memory-bound operator because it **halves the bytes**, not because it multiplies
the FLOPs — which is why FP8/FP4 accuracy matters more than peak throughput here.

### `AicoreSpec`

`AicoreSpec` summarises one core and exposes two derived figures the design calls
out:

- `local_dram_bytes_per_cycle` ≈ 714.29 B/cycle (1 TB/s ÷ 1.4 GHz).
- `weights_per_cycle_fp16` = `16 × 16` = 256 elements, i.e. 512 B. Against the
  ~714 B/cycle the memory system supplies, Cube and memory bandwidth are the same
  order of magnitude — the whole design point in the weight-used-once regime.
- `vector_elements_per_cycle_fp16` = `256 / 2` = 128 elements, and
  `describe()` reports the corresponding 179.2 G elem/s.

`wse-model report aicore` prints this object directly. For example:

```json
{
  "clock_hz": 1400000000.0,
  "local_dram_bytes": 402653184,
  "local_dram_bytes_per_cycle": 714.29,
  "vector_bytes_per_cycle": 256,
  "fixpipe_bytes_per_cycle": 256,
  "on_chip_buffers": { "L0A": 131072, "L0B": 524288, "L0C": 262144, "L1": 1048576, "UB": 393216 },
  "cube_weights_per_cycle_fp16": 256,
  "vector_elements_per_second_fp16": 179200000000.0
}
```

## `wse_model.core` — the modelled core

### Pipelines and the Calendar ordering rules

[`wse_model.core.pipelines`](../../src/wse_model/core/pipelines.py) models the pipe
set and the two ordering requirements that Calendar turns into correctness rules.
`Pipe` is the set the design names: `PIPE_S`, `PIPE_MTE1`, `PIPE_MTE2`, `PIPE_MTE3`,
`PIPE_MTE4`, `PIPE_M` (Cube), `PIPE_V` (Vector), and `PIPE_FIX` (FixPipe), with
`is_memory` and `is_compute` predicates. `calendar_step_pipes()` returns the
Step0–Step6 mapping as `StepRequirement` objects, each naming the pipes it
`requires` and the pipes it `blocks`.

The load-bearing rule is that `PIPE_MTE3` (send) and `PIPE_MTE4` (receive
accounting) must dispatch, back-pressure, and barrier independently. If an
unsatisfied MTE4 wait could stall scalar issue or block MTE3, every member would
sit waiting for its own receive while nobody sends — the group-wide deadlock
forbidden by invariant `O3`. `INDEPENDENT_FROM_MTE4` is the exemption set,
`(Pipe.SCALAR, Pipe.MTE3)`, and `PipeTracker` enforces it:

- `PipeTracker.issue(pipe)` raises if `mte4_waiting` and the pipe is not exempt;
- `PipeTracker.dispatchable()` returns every pipe normally, and the exemption set
  while an MTE4 wait is outstanding;
- `PipeTracker.check_no_deadlock()` verifies the exemption set still contains
  MTE3 and SCALAR, so the wait leaves a live send path.

`PipeBarrier` models the second rule: a barrier on `PIPE_MTE3` must wait for the
packets to have **actually been sent**, and must not return early merely because
`CalReg[opcode]` has not released them yet. `PipeBarrier.admits_release(sent=...,
queued=...)` returns true only when nothing remains queued, and constructing a
barrier with `waits_for_actual_send=True` on any pipe but MTE3 raises.

### Local DRAM

[`wse_model.core.dram`](../../src/wse_model/core/dram.py) models the private
memory and its 2 KB page rule. `LocalDram` defaults to
`capacity_bytes = LOCAL_DRAM_BYTES`, `bandwidth_bytes_per_sec = 1e12`, and
`page_bytes = 2048`, and exposes:

- `pages_touched(nbytes, aligned=True)` — the pages a transfer spans; an
  unaligned transfer can straddle a page boundary, which is why the design makes
  alignment a layout rule rather than a hint;
- `pages_for_rows(rows, row_bytes, row_stride_bytes)` — the pages a row-blocked
  tensor spans, including the padding the stride costs;
- `read_seconds(nbytes)` — bytes at the per-core bandwidth;
- `bandwidth_efficiency(rows, row_bytes, row_stride_bytes)` — useful over fetched
  bytes, the concrete meaning of "2 KB is the real granularity";
- `expert_capacity(expert_bytes)` — how many whole experts fit, the capacity limit
  of whitepaper §17.3.

`LocalDramLayout` declares how a tensor is blocked (`row_stride_bytes`,
`page_aligned`). `check()` rejects a stride that is not a 2 KB multiple, and
`require_fill_path()` raises `OpenItemError` for open item `Q8`: whether the fill
into L0B is a direct MTE or is staged through L1 has no value in the design
sources, so it must be declared rather than assumed.

### The buffer hierarchy

[`wse_model.core.buffers`](../../src/wse_model/core/buffers.py) turns the capacity
table into a fit model. `BufferKind` is the five levels and
`BUFFER_CAPACITY_BYTES` maps each to its size. A `TileRequirement` names a tile,
its level, its size, and whether it is double buffered; `required_bytes` doubles
the footprint when it is, because double buffering is the cost of overlap, and
`fits` / `occupancy` check it against the level. `fit_check(*requirements)`
returns a `BufferResidency` with `fits`, `overflows`, and `total_for(kind)`.

`BufferResidency.arena_placement()` raises `OpenItemError` for open item `Q7`
(whitepaper) / `S-2` (Calendar): whether the collective arena lives in UB or L1
decides the tile's address-space qualifier and the double-buffer budget, so it
must be declared rather than assumed.

### Cube and Vector timing

[`wse_model.core.cube`](../../src/wse_model/core/cube.py) turns a tile shape into
cycles, weight bytes, and a roofline verdict. `MatmulShape(m, k, n)` exposes
`macs`, `flops` (two per MAC), and `is_gemv` (`m == 1`). `matmul_timing(shape,
precision_name=..., fetched_weight_bytes=...)` returns a `MatmulTiming` with:

- `cube_cycles` — `ceil(m/M) × ceil(n/N) × ceil(k/K)` against the precision's
  per-cycle Cube shape;
- `ideal_weight_bytes` (`k × n × bytes_per_element`) and `weight_bytes` (the
  fetched figure when a padded layout is declared);
- `compute_seconds` and `fetch_seconds`, and `is_memory_bound` as their
  comparison;
- `arithmetic_intensity` (FLOP per fetched weight byte), `balance_point`, and
  `roofline_seconds` (the slower of compute and fetch).

`VectorTiming` models the 256 B/cycle Vector with `cycles(nbytes)`,
`seconds(nbytes)`, and `elements_per_second(bytes_per_element=2)`.
`vector_timing()` builds one and `precision_shapes()` reports each precision's
per-cycle shape.

#### Two roofline verdicts, and why both are reported

The tile-accurate Cube and the whitepaper's first-order balance point **disagree**
at small batch. Rather than pick one and hide the other, `MatmulTiming` reports
both, named so they cannot be confused, and a `verdicts_agree` flag. This is
[decision 0006](../decisions/0006-two-roofline-verdicts.md).

- `first_order_is_memory_bound` is the whitepaper §1 view, using
  `first_order_intensity = 2 × batch` FLOP per weight **element**. This is what
  yields the published minimum batches 6 / 23 / 46, and
  `wse_model.analysis.roofline` remains its authority. Its balance point is
  `balance_point` (the Cube FLOP/s over the memory bandwidth).
- `is_memory_bound` is tile-accurate: it compares `fetch_seconds` with
  `compute_seconds`, where the compute leg charges for the Cube's fixed row block
  through `m_utilization` and `effective_macs_per_cycle`. `m_utilization` is
  `m / (m_steps × M)`, so a 16-row Cube at `batch = 1` runs at 1/16 of its row
  capacity. `arithmetic_intensity` is the physically exact FLOP per fetched weight
  **byte**, which at FP16 differs from the first-order figure by the two bytes an
  element occupies.

For the canonical batch-1 GEMV `[1, 4096] × [4096, 4096]`:

| Precision | Effective MACs/cycle | Compute | Fetch | Tile-accurate (`is_memory_bound`) | First-order (`first_order_is_memory_bound`) |
| --- | --- | --- | --- | --- | --- |
| FP16 | 256 | 46.8 µs | 33.6 µs | compute | memory |
| FP8 | 1024 | 11.7 µs | 16.8 µs | memory | memory |
| FP4 | 2048 | 5.9 µs | 8.4 µs | memory | memory |

The design's headline claim — decode is weight-bandwidth-bound — holds at FP8 and
FP4 batch 1, and at FP16 once the batch fills the Cube's row block. At FP16 batch 1
the idle rows, not the memory system, are the binding constraint. That is a
statement about the Cube's shape, not a defect in the bandwidth argument, and it
is exactly the kind of effect a model exists to surface.

Two obligations follow. First, **any "memory-bound" or "compute-bound" label must
say which verdict it means**; the CLI reports `bound_by` and
`first_order_bound_by` separately, with `verdicts_agree`. Second, the published
minimum batches (6 / 23 / 46) stay pinned by
`tests/golden/test_golden_vectors.py` and must not move. The golden test that
freezes both verdicts is
`tests/golden/test_golden_vectors.py::test_the_two_roofline_verdicts_are_frozen`.

`wse-model report matmul` prints one `MatmulTiming`. For the FP16 case above it
reports `"m_utilization": 0.0625`, `"effective_macs_per_cycle": 256.0`,
`"bound_by": "compute"`, `"first_order_bound_by": "memory"`, and
`"verdicts_agree": false`. `--m/--k/--n`, `--precision`, and
`--fetched-weight-bytes` set the shape and the layout.

## What is not modelled

- **A cycle-accurate core.** `PipeTracker` is a small ordering machine that can
  prove the `O3` deadlock does not occur; it has no latencies, queue depths, or
  resource contention, and `PipeBarrier` is a predicate rather than a scheduler.
- **Real DMA and MTE descriptors.** The payload path is modelled as logical rows
  and segments, not as MTE1/MTE2 descriptors or `TASSIGN` bindings.
- **Weight layout and prefetch.** `LocalDramLayout` exposes the choice and refuses
  to invent it (`Q8`); no layout is chosen for you.
- **Buffer allocation.** `fit_check` verifies a declared residency; nothing
  allocates the buffers, and the arena's level is open (`Q7`/`S-2`).
- **Operator graphs.** No FFN or attention operator is lowered; the arithmetic and
  the collective exist separately, and nothing joins them into a layer.
- **SPR state.** `block_id_cost` reports the cost difference between the SPR and
  argument paths, but the model does not simulate a register file.

## Open items that gate a fuller AICORE model

| Item | What it blocks |
| --- | --- |
| `Q5` | target model dimensions (`H`, `I`, expert count, top-k, head count) — without them no concrete partition or core-level latency figure exists |
| `Q6` | the MoE load-imbalance policy under invariant `E1` (member cores must not conditionally skip a round) |
| `Q7` / `S-2` | whether the collective arena is in UB or L1, which decides the tile address-space qualifier and the double-buffer budget |
| `Q8` | weight layout in local DRAM and whether the prefetch path to L0B stages through L1 |
| `Q11` | production weight precision and mixed-precision acceptability, which fixes the byte counts the roofline depends on |
| `S-1` | operand widths and units for `expVal` / `capacity` / `epoch` and the reused operand slots |

All of these are reported by `wse-model open-items`. See
[Open items](../reference/open-items.md) and the [roadmap](../roadmap.md).

## See also

- [Batcher and UB bus](batcher-ub.md) — the other half of the external path.
- [Calendar and NoC](calendar-noc.md) — the closure that runs on these cores.
- [Decision 0003](../decisions/0003-keep-open-items-explicit.md) — why open
  values fail closed.
