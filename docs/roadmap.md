# Roadmap

This page is the model's honest status report. It separates what is implemented
and tested from what is declared but not modelled, and it names the open items
that gate each future stage. The design sources are frozen at the v0.1 whitepaper
set dated 2026-09-17; progress is measured against those documents, not against a
schedule.

## Status at a glance

| Area | Status | Evidence |
| --- | --- | --- |
| Calendar encoding | **Implemented and tested** | `src/wse_model/calendar/`, `tests/unit/test_route_bits.py`, `tests/unit/test_calendar_semantics.py` |
| Calendar structural validation | **Implemented and tested** | `src/wse_model/calendar/validate.py`, `tests/unit/test_validate.py` |
| NoC topology, flit format, forwarding | **Implemented and tested** | `src/wse_model/topology.py`, `src/wse_model/noc/`, `tests/unit/test_noc.py` |
| `CalReg` residency and atomic install | **Implemented and tested** | `src/wse_model/noc/calreg.py`, `tests/unit/test_noc.py` |
| FFN two-phase AllGather closure | **Implemented and tested** | `src/wse_model/collective.py`, `tests/integration/test_ffn_allgather.py` |
| AICORE: pipes, local DRAM, buffers, Cube/Vector timing | **Implemented and tested** | `src/wse_model/core/`, `tests/unit/test_core.py` |
| Batcher and UB bus | **Implemented and tested** | `src/wse_model/host/ub_bus.py`, `src/wse_model/host/batcher.py`, `tests/unit/test_host.py` |
| Runtime and loading | **Implemented and tested (ordering and state, not transport)** | `src/wse_model/host/runtime.py`, `tests/unit/test_host.py` |
| Compiled-product self-checks F1/F2/F3 and package assembly | **Implemented and tested** | `src/wse_model/compiler/`, `tests/unit/test_compiler_selfcheck.py`, `tests/unit/test_compiler_package.py` |
| Closed-form analysis (roofline, bandwidth, latency, D-cache) | **Implemented and tested; latency total deliberately blocked** | `src/wse_model/analysis/`, `tests/unit/test_analysis.py` |
| Route-table and kernel-object schemas | **Implemented, frozen** | `schemas/calendar-route-table.schema.json`, `schemas/kernel-object.schema.json`, `tests/contracts/test_table_schema.py` |
| Open-item registry and gate | **Implemented and tested** | `src/wse_model/open_items.py`, `tests/unit/test_analysis.py` |
| Runnable examples | **Implemented, run in CI** | `examples/`, `tests/integration/test_examples.py` |
| Compiler frontend (IR, group recognition, lowering, emission) | **Not modelled** — only the product checks and package assembly exist | This page |
| Reduce / AllReduce / ReduceScatter closure | **Deliberately refused** pending reduction semantics | `run_allgather` raises; `tests/integration/test_ffn_allgather.py::test_the_closure_refuses_to_model_reduce` |
| 48-node emitted route table | **Deliberately refused** pending `Q1` | `CalendarRouteEntry.to_bytes` raises |
| ACIR layer (`wse_model.acir`) | Present and importable; tests are opt-in | `src/wse_model/acir/`, `tests/acir/`; `make acir` needs the native ACIR tools |

The repository `README.md` lists `acir/` in its layout table. The package exists
and imports, but its tests require the `agentic_circuit` frontend and the native
ACIR tools, so they are opt-in and outside the default gate. Treat the semantic
core as the authority and the ACIR layer as in progress; see
[decision 0002](decisions/0002-two-layer-model.md).

## Stage 0 — Calendar/NoC closure (done)

The first stage is the part of the design that the rest of the system depends on:
the encoding and the collective closure. It is complete for AllGather and is
proven by the golden lane, the unit suite, and the integration suite.

Delivered:

- `routeBits` codec with the fixed bit order and the §2.2.1 golden vector
  (80 bit / 10 B at 40 nodes, 96 bit / 12 B at 48).
- The 16 B `CalendarRouteEntry` and its `rbLo` / `rbHi` register-pair view.
- `keyId`, `opcode`, `redOp`, `RouteKey`, `CalendarKeyRef`, and the `O1` registry
  discipline.
- Per-`opcode` `collectionEpoch` accounting with drain-before-wrap.
- Symmetric addressing, `selfOff`, `A1`/`A2`/`A3`, and the `expVal` identity.
- The seven `expVal` contracts, the §2.7.2 structural check set, and the table
  budget checks.
- Stateless forwarding, `CalReg` residency, atomic install, and the drained-die
  requirement.
- The FFN two-phase AllGather closure, the route-table JSON schema, and the
  runnable examples.

The requirements are enumerated in
[Calendar closure requirements](requirements/calendar-closure.md).

## Stage 1 — The platform the closure runs on (done)

The closure used to run on a topological abstraction. Stage 1 adds the machine it
interacts with, at the level the design sources actually specify.

### 1a. AICORE — `wse_model.core` (done)

- **Pipelines.** `Pipe` names the pipe set and `calendar_step_pipes()` maps
  Step0–Step6 onto it. `PipeTracker` proves that an unsatisfied `PIPE_MTE4` wait
  leaves `SCALAR` and `PIPE_MTE3` dispatchable, which is the `O3` deadlock
  avoidance rule; `PipeBarrier` models the "MTE3 barrier waits for the actual
  send" requirement.
- **Local DRAM.** `LocalDram` models 384 MB at 1 TB/s with a 2 KB page, with page
  arithmetic, bandwidth efficiency, and expert capacity.
- **Buffers.** `BufferKind`, `TileRequirement`, `BufferResidency`, and `fit_check`
  model the L0A/L0B/L0C/L1/UB hierarchy with double-buffer footprints.
- **Cube and Vector.** `MatmulShape` and `matmul_timing()` turn a tile into
  cycles, weight bytes, and a memory-bound verdict; `VectorTiming` models the
  256 B/cycle Vector.
- **Open-item gates.** The L0B fill path (`Q8`) and the arena level (`Q7`/`S-2`)
  fail closed rather than assume a value.

### 1b. Batcher and UB bus — `wse_model.host` (done)

- **Bus.** `UbLane`, `UbBus`, the 8 + 1 = 9 lane budget, and the
  `local_dram_over_fabric_ratio()` of about 4.46 that makes weights reside.
- **Dispatch.** `BatcherResponsibility`, `DispatchFrequency`, and
  `dispatch_paths()` model the four responsibilities at three frequencies.
- **Cold misses.** `RefillAccount` and `BatcherMem` model the split between
  requests, `Batcher.mem`-served fills, and DDR-backed fills.
- **Open-item gates.** `BatcherSpec`'s four `Q3` parameters default to `None` and
  `require()` fails closed.

### 1c. Runtime and loading — `wse_model.host.runtime` (done)

- `RuntimeTier`, the four `DispatchChain`s and `dispatch_chains()`, and the fact
  that `CalReg` is the only chain that bypasses the Batcher.
- `VersionSet.check` and `CalendarRouteTable.check_versions` for the three-version
  fault.
- `InstallState` and `Loader` for install kernel / weights / `CalReg`, version
  check, kickstart, launch, and steady-state dispatch bytes.
- `LaunchConstraints` and `Scheduler` for the four §12.3 constraints, including
  the `SW-1` phase barrier, and `block_id_cost` for the `C-7` trade-off.

What remains outside the model is the transport itself: there is no PCIe, no task
queue, and no device. Gating open items for that are `C-5`, `C-6`, `C-7`,
`Q12`/`C-11`, `S-3`, `S-4`, and `S-5`; see
[Runtime and loading](architecture/runtime.md).

### 1d. Compiled-product checks and package assembly — `wse_model.compiler` (partial)

`check_compiled_product` implements F1/F2/F3 over a declared symbol manifest:
F1 rejects writable Calendar static state, F2 rejects a materialised
`CalendarKeyRef`, and F3 checks the `kCalendarRoute` section, 64 B alignment,
exact size, and read-only-ness. The manifest schema is
`wse-model/kernel-object/1`.

`wse_model.compiler.package` assembles the compiler's outputs into a
`DeploymentPackage` and validates it as a whole: the five artifacts of whitepaper
§13.3, the per-call-site immediates of Calendar §2.7.3 step 4, the route-table and
F1/F2/F3 checks, artifact version agreement, the same-`opcode` concurrency rule
(`check_opcode_domains`), weight-shard page alignment, and `.rodata` alignment.
The FFN package reports 26 distinct checks, and `wse-model check package
--concurrent` proves the phase-split rule by failing.

This is still **not** a compiler. The frontend the whitepaper describes is absent:
there is no IR, no group/collective recognition, no lowering, no immediate
materialisation, and no `.rodata` emission. The package models the shape of the
outputs and the checks a real compiler would run.

## Stage 2 — Compiler frontend

The model is a consumer of compiled artifacts, not a compiler: Calendar §2.7 is
explicit that software must not rewrite the NoC's routing algorithm, so route
bitmaps arrive from the NoC provider or a fixture and are validated rather than
generated. A compiler-frontend model would add the pieces the whitepaper puts in
PyPTO:

- group, collective, and inter-collective concurrency recognition from an IR;
- the five compile-time steps of Calendar §2.7.3;
- immediate materialisation (`keyId` / `opcode` / `expVal` / `capacity` /
  `selfOff`) and `.rodata` emission;
- phase splitting so that two collectives sharing an `opcode` never fly or align
  concurrently.

The F1/F2/F3 self-checks of Calendar §3.10 are already modelled and would become
the acceptance gate for that frontend.

Gating open items:

- `Q5` — target model dimensions (`H`, `I`, expert count, top-k, head count);
  without them no concrete partitioning or latency figure can be produced.
- `Q6` — the MoE load-imbalance policy under invariant `E1` (members must not
  conditionally skip a round).
- `C-1` — the send-side 80 bit operand encoding (scheme A versus scheme B).
- `C-3` — the reduction element type field, which must be fixed before the flit
  header format freezes.
- `C-8` — the static table shape for per-row routing in ReduceScatter / Scatter
  (a third dimension multiplies DDR footprint and per-core residency by
  `shardCount`).
- `C-9` — the table layout, assumed key-major but with the node-major variant
  modelled ([decision 0005](decisions/0005-static-table-layout.md)).
- `C-12` — the D-cache strategy for the `.rodata` table and whether
  `keyCount <= 16` suffices.
- `Q7` / `S-2` — the arena address space, which changes the tile type in the
  lowered code.
- `Q12` / `C-11` — topology isomorphism, which decides whether the emitted table is
  a link-time constant or a load-time buffer.
- `S-5` — two small semantics (send `sid` handling and the report instruction's
  pipe operand) that decide whether a barrier before Step4 can be elided.
- `S-6` / `HW-15` — segment identity de-duplication; there is no software-side
  substitute, and without it `expVal` can be met early.

## Stage 3 — Reduction family and the 48-node reading

Two closures that the design describes but the model deliberately does not fake.

### 3a. Reduce / AllReduce / ReduceScatter

`opcode` 2 is reserved for `Reduce` and the first phase is documented as
implementing `AllGather` and `Reduce`, but the model only closes AllGather. The
blocker is the definition of reduction under `{P, L}`: merge buffer depth,
out-of-order merge timing, and `redOp` overflow/saturation.

Gating open items:

- `C-10` — the complete definition of reduction semantics under `{P, L}`.
- `C-3` — the 3 bit reduction element type; `redOp` alone cannot determine the
  machine operation (`f32` SUM and `s32` SUM differ).

The model already refuses rather than approximates:
`wse_model.noc.network.allgather_geometry_check` and
`wse_model.collective.run_allgather` raise when asked for a non-AllGather
collective, and `tests/integration/test_ffn_allgather.py::test_the_closure_refuses_to_model_reduce`
proves it.

### 3b. The 48-node topology

All three readings of `Q1` are first-class profiles today
(`calendar-40`, `whitepaper-48`, `whitepaper-48-40c`), and the flit header cost is
computed for both node counts (12 B / 18.75% at 40, 14 B / 21.88% at 48). What
cannot be done at 48 nodes is emitting a route table: `routeBits` alone is 12 B,
so an entry needs 18 B and no longer fits the one-GPR-pair layout.
`CalendarRouteEntry.to_bytes` and `validate_entry_layout` raise rather than widen
the entry.

Gating open item:

- `Q1` — whether the die has 40 nodes (5×8) or 48 (6×8), and if 48, whether all 48
  positions carry an AICORE or 8 are I/O. A decision changes `routeBits` width, the
  flit header size, the entry layout, and every collective member set.

## Stage 4 — ACIR layer (in progress)

The ACIR layer is present and importable (`src/wse_model/acir/`, with tests under
`tests/acir/`), but it is **not yet verified by the default gate**: its tests need
the `agentic_circuit` frontend and the native ACIR tools, so they run only under
`make acir` or the opt-in `acir` CI job. The infrastructure is in place:
`tools/build-acir-tools.sh`, the `make acir` target, and the `acir` job gated on
the `WSE_MODEL_ACIR_CI` repository variable.

Gating conditions:

- The core must be stable enough to mirror; the ACIR layer must not disagree with
  it ([decision 0002](decisions/0002-two-layer-model.md)).
- The pyCircuit revision must be pinned, and the `agentic_circuit` native tools
  built. `agentic-circuit` is not on PyPI; see
  [Getting started](development/getting-started.md).
- Any rule whose value is still open must stay behind `require_resolved`; the ACIR
  layer does not get to assume what the core refuses to assume.

## Not planned until an item is decided

These are explicitly out of scope while the listed items remain open:

| Capability | Blocker |
| --- | --- |
| A total latency figure for a coprocessor call | `Q3`, `Q9` |
| A concrete FFN or attention partition | `Q5` |
| A load-imbalance policy for MoE | `Q6` |
| A named reduction element type | `C-3` |
| Any reduction collective closure | `C-10` |
| A 48-node emitted route table | `Q1` |
| A per-shard route table | `C-8` |
| A topology-degradation (B-class) table path | `Q12`, `C-11` |
| A chosen weight layout or L0B fill path | `Q8` |
| A chosen arena level (UB or L1) | `Q7`, `S-2` |
| Batcher timing parameters | `Q3` |
